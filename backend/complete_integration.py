# -*- coding: utf-8 -*-
"""
Complete BadBot Integration - Final Features
"""

print("="*60)
print("COMPLETING BADBOT INTEGRATION")
print("="*60)

# Feature 1: Add call history table to portal
print("\n[1/4] Adding call history table to portal...")

with open('static/james-portal.html', 'r') as f:
    html = f.read()

# Add call history section before closing </div>
call_history = '''
        <div class="bg-white rounded shadow p-6 mt-6">
            <h2 class="text-2xl font-bold mb-4">Recent Call Activity</h2>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead class="bg-gray-100">
                        <tr>
                            <th class="px-4 py-2 text-left">Time</th>
                            <th class="px-4 py-2 text-left">From</th>
                            <th class="px-4 py-2 text-left">Caller ID</th>
                            <th class="px-4 py-2 text-left">Action</th>
                            <th class="px-4 py-2 text-left">Status</th>
                        </tr>
                    </thead>
                    <tbody id="call-history"></tbody>
                </table>
            </div>
        </div>
'''

if 'call-history' not in html:
    html = html.replace('</body>', call_history + '\n</body>')

# Add call history loading to loadData function
call_history_js = '''
                // Load call history
                const callsRes = await fetch(`${API}/calls/${CLIENT_ID}`);
                if (callsRes.ok) {
                    const calls = await callsRes.json();
                    const tbody = document.getElementById('call-history');
                    tbody.innerHTML = '';
                    
                    calls.forEach(call => {
                        const tr = document.createElement('tr');
                        tr.className = 'border-t hover:bg-gray-50';
                        
                        const statusColors = {
                            'blocked': 'bg-red-100 text-red-800',
                            'screening': 'bg-yellow-100 text-yellow-800',
                            'answered': 'bg-green-100 text-green-800'
                        };
                        
                        tr.innerHTML = `
                            <td class="px-4 py-3">${new Date(call.timestamp).toLocaleString()}</td>
                            <td class="px-4 py-3 font-medium">${call.from_number}</td>
                            <td class="px-4 py-3">${call.caller_name}</td>
                            <td class="px-4 py-3">${call.action.replace('_', ' ')}</td>
                            <td class="px-4 py-3">
                                <span class="px-2 py-1 rounded text-xs ${statusColors[call.status] || 'bg-gray-100'}">
                                    ${call.status}
                                </span>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                    
                    if (calls.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">No calls yet</td></tr>';
                    }
                }
'''

if 'call-history' in html and 'Load call history' not in html:
    html = html.replace(
        '// Load config',
        call_history_js + '\n                // Load config'
    )

with open('static/james-portal.html', 'w') as f:
    f.write(html)

print("   OK: Call history table added")

# Feature 2: Add auto-refresh
print("\n[2/4] Adding auto-refresh...")

if 'setInterval' not in html:
    html = html.replace(
        'loadData();',
        'loadData();\n        setInterval(loadData, 30000); // Refresh every 30 seconds'
    )
    with open('static/james-portal.html', 'w') as f:
        f.write(html)
    print("   OK: Auto-refresh enabled (30s)")

# Feature 3: Add export functionality
print("\n[3/4] Adding data export...")

export_api = '''
@router.get("/api/badbot/export/{client_id}")
async def export_calls(client_id: int, db: Session = Depends(get_db)):
    """Export call logs as CSV"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        raise HTTPException(status_code=404, detail="No calls found")
    
    logs = db.query(BadBotCallLog).filter(
        BadBotCallLog.phone_number_id.in_(phone_ids)
    ).order_by(BadBotCallLog.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'From Number', 'Caller Name', 'Action', 'Status'])
    
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat(),
            log.from_number,
            log.caller_name or 'Unknown',
            log.action,
            log.status
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=badbot_calls.csv"}
    )
'''

with open('app/routers/badbot_portal.py', 'r') as f:
    portal = f.read()

if 'export_calls' not in portal:
    # Add at the end before the last function
    portal = portal.rstrip() + '\n\n' + export_api
    with open('app/routers/badbot_portal.py', 'w') as f:
        f.write(portal)
    print("   OK: CSV export added")

# Feature 4: Add phone number update to portal
print("\n[4/4] Adding phone number editor...")

phone_editor = '''
            <div class="mb-4 p-4 bg-blue-50 rounded-lg">
                <label class="block text-sm font-semibold mb-2">Alert Phone Number:</label>
                <p class="text-xs text-gray-600 mb-2">SMS alerts will be sent to this number</p>
                <div class="flex gap-2">
                    <input type="tel" id="client-cell" class="flex-1 px-4 py-2 border rounded-lg" placeholder="+17543670370">
                    <button onclick="updatePhoneNumber()" class="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                        Update Number
                    </button>
                </div>
            </div>
'''

update_phone_js = '''
        async function updatePhoneNumber() {
            const newNumber = document.getElementById('client-cell').value;
            if (!newNumber || !newNumber.startsWith('+')) {
                alert('Please enter a valid phone number with country code (e.g., +17543670370)');
                return;
            }
            try {
                await fetch(`${API}/config/${CLIENT_ID}`, {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ client_cell: newNumber })
                });
                alert('Phone number updated successfully!');
                loadData();
            } catch (e) {
                alert('Error updating number: ' + e.message);
            }
        }
'''

with open('static/james-portal.html', 'r') as f:
    html = f.read()

if 'updatePhoneNumber' not in html:
    # Add phone editor before alert settings
    html = html.replace(
        '<h2 class="text-2xl font-bold mb-4">Alert Settings</h2>',
        phone_editor + '\n            <h2 class="text-2xl font-bold mb-4">Alert Settings</h2>'
    )
    
    # Add the function
    html = html.replace(
        'async function saveSettings() {',
        update_phone_js + '\n        async function saveSettings() {'
    )
    
    # Load current phone number
    html = html.replace(
        "document.getElementById('sms-alerts').checked = config.sms_alerts_enabled;",
        "document.getElementById('sms-alerts').checked = config.sms_alerts_enabled;\n                    document.getElementById('client-cell').value = config.client_cell || '';"
    )
    
    with open('static/james-portal.html', 'w') as f:
        f.write(html)
    print("   OK: Phone number editor added")

print("\n" + "="*60)
print("INTEGRATION COMPLETE!")
print("="*60)
print("\nNEW FEATURES:")
print("  - Call history table with timestamps")
print("  - Auto-refresh every 30 seconds")
print("  - CSV export endpoint")
print("  - Phone number update in portal")
print("\nOPEN PORTAL:")
print("  http://localhost:8000/static/james-portal.html")
print("\nEXPORT CALLS:")
print("  http://localhost:8000/api/badbot/export/1")
print("="*60)

