# -*- coding: utf-8 -*-
"""
Test BadBot Portal API
"""
import requests
import json

API = "http://localhost:8000/api/badbot"
CLIENT_ID = 1

print("="*60)
print("TESTING BADBOT PORTAL API")
print("="*60)

# Test 1: Get Stats
print("\n1. Testing GET /stats...")
try:
    r = requests.get(f"{API}/stats/{CLIENT_ID}")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Data: {json.dumps(r.json(), indent=2)}")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   Failed: {e}")

# Test 2: Get Config
print("\n2. Testing GET /config...")
try:
    r = requests.get(f"{API}/config/{CLIENT_ID}")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   Client: {data.get('client_name')}")
        print(f"   SMS Alerts: {data.get('sms_alerts_enabled')}")
        print(f"   Trusted Contacts: {len(data.get('trusted_contacts', []))}")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   Failed: {e}")

# Test 3: Update Settings
print("\n3. Testing PATCH /config...")
try:
    r = requests.patch(
        f"{API}/config/{CLIENT_ID}",
        json={"sms_alerts_enabled": True, "alert_on_spam": True}
    )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Success: Settings updated")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   Failed: {e}")

# Test 4: Add Trusted Contact
print("\n4. Testing POST /trusted-contacts...")
try:
    r = requests.post(
        f"{API}/trusted-contacts/{CLIENT_ID}",
        json={"phone_number": "+15555551111", "name": "Test Contact"}
    )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Success: Contact added")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   Failed: {e}")

# Test 5: Get Recent Calls
print("\n5. Testing GET /calls...")
try:
    r = requests.get(f"{API}/calls/{CLIENT_ID}")
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   Calls: {len(r.json())}")
    else:
        print(f"   Error: {r.text}")
except Exception as e:
    print(f"   Failed: {e}")

print("\n" + "="*60)
print("If all tests passed, portal is ready!")
print("Open: http://localhost:8000/static/badbot-portal.html")
print("="*60)

