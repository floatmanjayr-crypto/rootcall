# -*- coding: utf-8 -*-
"""
Check Telnyx messaging configuration
"""
import requests

with open('.env', 'r') as f:
    for line in f:
        if 'TELNYX_API_KEY=' in line:
            TELNYX_API_KEY = line.split('=', 1)[1].strip()

print("="*60)
print("CHECKING TELNYX MESSAGING SETUP")
print("="*60)

# Check messaging profiles
response = requests.get(
    "https://api.telnyx.com/v2/messaging_profiles",
    headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}
)

if response.status_code == 200:
    profiles = response.json().get('data', [])
    print(f"\nFound {len(profiles)} messaging profiles")
    
    for profile in profiles:
        print(f"\nProfile: {profile.get('name')}")
        print(f"  ID: {profile.get('id')}")
        print(f"  Enabled: {profile.get('enabled')}")
        
        # Check if +18135478530 is assigned to this profile
        print(f"  Checking numbers in this profile...")
else:
    print(f"Failed: {response.status_code}")
    print(response.text)

# Check if the number has SMS enabled
print("\n" + "="*60)
print("CHECKING NUMBER +18135478530")
print("="*60)

response = requests.get(
    "https://api.telnyx.com/v2/phone_numbers?filter[phone_number]=+18135478530",
    headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}
)

if response.status_code == 200:
    numbers = response.json().get('data', [])
    if numbers:
        num = numbers[0]
        print(f"Number found: {num.get('phone_number')}")
        print(f"Messaging Profile ID: {num.get('messaging_profile_id')}")
        print(f"Connection ID: {num.get('connection_id')}")
        
        if not num.get('messaging_profile_id'):
            print("\nWARNING: No messaging profile assigned!")
            print("This is why SMS isn't being delivered.")
            print("\nFIX: Assign a messaging profile in Telnyx Portal")
    else:
        print("Number not found")
else:
    print(f"Failed: {response.status_code}")

print("="*60)

