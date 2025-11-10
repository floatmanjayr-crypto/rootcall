import os
import requests

# Load API key from .env
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('TELNYX_API_KEY='):
            TELNYX_API_KEY = line.split('=', 1)[1].strip()
            break

CONNECTION_ID = "2812968115544000352"

print("="*60)
print("SETTING UP TELNYX OUTBOUND PROFILE")
print("="*60)

# Step 1: Get or create an outbound voice profile
print("\n1. Getting outbound voice profiles...")
response = requests.get(
    "https://api.telnyx.com/v2/outbound_voice_profiles",
    headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}
)

if response.status_code == 200:
    profiles = response.json().get('data', [])
    print(f"Found {len(profiles)} outbound profiles")
    
    if profiles:
        profile_id = profiles[0]['id']
        print(f"Using existing profile: {profile_id}")
    else:
        print("No profiles found. Creating one...")
        response = requests.post(
            "https://api.telnyx.com/v2/outbound_voice_profiles",
            headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
            json={
                "name": "RootCall Outbound Profile",
                "traffic_type": "conversational",
                "service_plan": "global",
                "concurrent_call_limit": 10
            }
        )
        
        if response.status_code in [200, 201]:
            profile_id = response.json()['data']['id']
            print(f"Created new profile: {profile_id}")
        else:
            print(f"Failed to create profile: {response.text}")
            exit(1)
    
    # Step 2: Assign profile to connection
    print(f"\n2. Assigning profile {profile_id} to connection {CONNECTION_ID}...")
    
    response = requests.patch(
        f"https://api.telnyx.com/v2/connections/{CONNECTION_ID}",
        headers={
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "outbound_voice_profile_id": profile_id
        }
    )
    
    if response.status_code == 200:
        print("✅ SUCCESS! Outbound profile assigned!")
        print("\n" + "="*60)
        print("TEST NOW:")
        print("="*60)
        print("Call: +18135478530")
        print("Should transfer to: +17543670370")
        print("="*60)
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)
else:
    print(f"Failed to get profiles: {response.text}")
