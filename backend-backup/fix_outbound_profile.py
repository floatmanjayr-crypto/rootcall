import os
import requests

# Load API key from .env
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('TELNYX_API_KEY='):
            TELNYX_API_KEY = line.split('=', 1)[1].strip()
            break

CONNECTION_ID = "2812968115544000352"
PROFILE_ID = "2812952284193883196"

print("="*60)
print("ASSIGNING OUTBOUND PROFILE TO SIP CONNECTION")
print("="*60)

# Try different endpoints
endpoints = [
    f"https://api.telnyx.com/v2/telephony_credentials/{CONNECTION_ID}",
    f"https://api.telnyx.com/v2/credential_connections/{CONNECTION_ID}",
]

for endpoint in endpoints:
    print(f"\nTrying: {endpoint}")
    
    response = requests.patch(
        endpoint,
        headers={
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "outbound_voice_profile_id": PROFILE_ID
        }
    )
    
    print(f"Response: {response.status_code}")
    
    if response.status_code in [200, 202]:
        print("✅ SUCCESS!")
        print(f"Profile {PROFILE_ID} assigned to connection {CONNECTION_ID}")
        print("\nCall +18135478530 now - it should transfer!")
        exit(0)
    else:
        print(f"Failed: {response.text}")

print("\n" + "="*60)
print("MANUAL SETUP REQUIRED")
print("="*60)
print("Go to: https://portal.telnyx.com/#/app/connections")
print(f"Find connection: {CONNECTION_ID}")
print(f"Set Outbound Voice Profile to: {PROFILE_ID}")
print("="*60)
