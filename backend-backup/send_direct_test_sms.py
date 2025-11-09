# -*- coding: utf-8 -*-
"""
Send one direct test SMS right now
"""
import requests
import time

with open('.env', 'r') as f:
    for line in f:
        if 'TELNYX_API_KEY=' in line:
            TELNYX_API_KEY = line.split('=', 1)[1].strip()

print("="*60)
print("SENDING TEST SMS NOW")
print("="*60)

response = requests.post(
    "https://api.telnyx.com/v2/messages",
    headers={
        "Authorization": f"Bearer {TELNYX_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "from": "+18135478530",
        "to": "+17543670370",
        "text": f"[BadBot TEST {time.time()}] If you see this, SMS is working! Reply YES"
    }
)

print(f"\nResponse: {response.status_code}")

if response.status_code in [200, 201, 202]:
    data = response.json()
    print(f"Message ID: {data['data']['id']}")
    print(f"Status: {data['data']['to'][0]['status']}")
    print(f"\nSUCCESS! Check James's phone RIGHT NOW!")
    print("Phone: +17543670370")
    print("\nIf message doesn't arrive in 30 seconds:")
    print("1. Phone might be blocking shortcode/messages")
    print("2. Carrier might be filtering")
    print("3. Number needs A2P registration")
else:
    print(f"FAILED!")
    print(response.text)

print("="*60)

