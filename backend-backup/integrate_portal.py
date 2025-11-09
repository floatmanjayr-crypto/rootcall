# -*- coding: utf-8 -*-
"""
Integrate BadBot Portal - Complete Version
"""
import os

# Check if router is already added
with open('app/main.py', 'r') as f:
    content = f.read()

if 'badbot_portal' not in content:
    print("Adding BadBot Portal router to main app...")
    
    # Add import
    if 'from app.routers import' in content:
        content = content.replace(
            'from app.routers import',
            'from app.routers import badbot_portal, ',
            1
        )
    
    # Add router include
    if 'app.include_router(badbot_screen.router)' in content:
        content = content.replace(
            'app.include_router(badbot_screen.router)',
            'app.include_router(badbot_screen.router)\napp.include_router(badbot_portal.router)'
        )
    
    with open('app/main.py', 'w') as f:
        f.write(content)
    
    print("OK: Added BadBot Portal router")
else:
    print("BadBot Portal already integrated")

print("\nCreating HTML portal...")

# Create directory
os.makedirs('static', exist_ok=True)

# Complete HTML portal
html_portal = '''<!DOCTYPE html>
<html>
<head>
    <title>BadBot Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto p-6">
        <h1 class="text-4xl font-bold mb-8">BadBot Protection Portal</h1>
        
        <div class="grid grid-cols-4 gap-4 mb-8">
            <div class="bg-white p-6 rounded shadow">
                <div class="text-sm text-gray-600">Spam Blocked</div>
                <div class="text-3xl font-bold text-red-600" id="spam-blocked">0</div>
            </div>
            <div class="bg-white p-6 rounded shadow">
                <div class="text-sm text-gray-600">Calls Screened</div>
                <div class="text-3xl font-bold text-yellow-600" id="calls-screened">0</div>
            </div>
            <div class="bg-white p-6 rounded shadow">
                <div class="text-sm text-gray-600">Trusted Connected</div>
                <div class="text-3xl font-bold text-green-600" id="trusted-connected">0</div>
            </div>
            <div class="bg-white p-6 rounded shadow">
                <div class="text-sm text-gray-600">Total Calls</div>
                <div class="text-3xl font-bold text-blue-600" id="total-calls">0</div>
            </div>
        </div>

        <div class="bg-white rounded shadow mb-6 p-6">
            <h2 class="text-2xl font-bold mb-4">Settings</h2>
            <div class="space-y-3">
                <label class="flex items-center">
                    <input type="checkbox" id="sms-alerts" class="mr-3">
                    <span>Enable SMS Alerts</span>
                </label>
                <label class="flex items-center">
                    <input type="checkbox" id="alert-spam" class="mr-3">
                    <span>Alert on Spam</span>
                </label>
                <label class="flex items-center">
                    <input type="checkbox" id="alert-unknown" class="mr-3">
                    <span>Alert on Unknown</span>
                </label>
                <button onclick="saveSettings()" class="px-6 py-2 bg-blue-600 text-white rounded">Save</button>
            </div>
        </div>

        <div class="bg-white rounded shadow p-6">
            <h2 class="text-2xl font-bold mb-4">Trusted Contacts</h2>
            <div class="flex gap-2 mb-4">
                <input type="tel" id="new-contact" placeholder="+1234567890" class="flex-1 px-4 py-2 border rounded">
                <input type="text" id="new-contact-name" placeholder="Name" class="flex-1 px-4 py-2 border rounded">
                <button onclick="addContact()" class="px-6 py-2 bg-green-600 text-white rounded">Add</button>
            </div>
            <div id="contacts-list"></div>
        </div>
    </div>

    <script>
        const CLIENT_ID = 1;
        const API = 'http://localhost:8000/api/badbot';

        async function loadData() {
            const stats = await fetch(`${API}/stats/${CLIENT_ID}`).then(r => r.json());
            document.getElementById('spam-blocked').textContent = stats.spam_blocked;
            document.getElementById('calls-screened').textContent = stats.calls_screened;
            document.getElementById('trusted-connected').textContent = stats.trusted_forwarded;
            document.getElementById('total-calls').textContent = stats.total_calls;

            const config = await fetch(`${API}/config/${CLIENT_ID}`).then(r => r.json());
            document.getElementById('sms-alerts').checked = config.sms_alerts_enabled;
            document.getElementById('alert-spam').checked = config.alert_on_spam;
            document.getElementById('alert-unknown').checked = config.alert_on_unknown;

            const list = document.getElementById('contacts-list');
            list.innerHTML = '';
            config.trusted_contacts.forEach(c => {
                const div = document.createElement('div');
                div.className = 'flex justify-between items-center p-3 bg-gray-50 rounded mb-2';
                div.innerHTML = `
                    <div>
                        <div class="font-bold">${c.name || 'Unnamed'}</div>
                        <div class="text-sm text-gray-600">${c.phone_number}</div>
                    </div>
                    <button onclick="removeContact('${c.phone_number}')" class="px-4 py-2 text-red-600">Remove</button>
                `;
                list.appendChild(div);
            });
        }

        async function saveSettings() {
            await fetch(`${API}/config/${CLIENT_ID}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    sms_alerts_enabled: document.getElementById('sms-alerts').checked,
                    alert_on_spam: document.getElementById('alert-spam').checked,
                    alert_on_unknown: document.getElementById('alert-unknown').checked
                })
            });
            alert('Settings saved!');
        }

        async function addContact() {
            const phone = document.getElementById('new-contact').value;
            const name = document.getElementById('new-contact-name').value;
            if (!phone) return;

            await fetch(`${API}/trusted-contacts/${CLIENT_ID}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({phone_number: phone, name: name})
            });

            document.getElementById('new-contact').value = '';
            document.getElementById('new-contact-name').value = '';
            loadData();
        }

        async function removeContact(phone) {
            await fetch(`${API}/trusted-contacts/${CLIENT_ID}/${encodeURIComponent(phone)}`, {
                method: 'DELETE'
            });
            loadData();
        }

        loadData();
    </script>
</body>
</html>
'''

with open('static/badbot-portal.html', 'w') as f:
    f.write(html_portal)

print("OK: Created HTML portal at static/badbot-portal.html")

# Add static file serving to main.py
print("\nAdding static file serving...")

with open('app/main.py', 'r') as f:
    content = f.read()

if 'StaticFiles' not in content:
    content = content.replace(
        'from fastapi import FastAPI',
        'from fastapi import FastAPI\nfrom fastapi.staticfiles import StaticFiles'
    )
    
    content = content.replace(
        'app = FastAPI(',
        'app = FastAPI(\n'
    )
    
    # Add static mount after app creation
    if 'app.mount' not in content:
        content += '\napp.mount("/static", StaticFiles(directory="static"), name="static")\n'
    
    with open('app/main.py', 'w') as f:
        f.write(content)
    
    print("OK: Added static file serving")

print("\n" + "="*60)
print("BADBOT PORTAL READY!")
print("="*60)
print("\n1. Restart uvicorn server")
print("2. Open: http://localhost:8000/static/badbot-portal.html")
print("3. View stats, manage settings, add trusted contacts!")
print("\n" + "="*60)

