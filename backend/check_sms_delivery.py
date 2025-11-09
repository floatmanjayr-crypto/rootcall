# -*- coding: utf-8 -*-
"""
Check recent SMS message delivery status
"""
import requests
from datetime import datetime, timedelta

with open('.env', 'r') as f:
    for line in f:
        if 'TELNYX_API_KEY=' in line:
            TELNYX_API_KEY = line.split('=', 1)[1].strip()

print("="*60)
print("RECENT SMS MESSAGES")
print("="*60)

# Get messages from last hour
response = requests.get(
    "https://api.telnyx.com/v2/messages",
    headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
    params={
        "filter[from]": "+18135478530",
        "page[size]": 20
    }
)

if response.status_code == 200:
    messages = response.json().get('data', [])
    print(f"\nFound {len(messages)} recent messages from +18135478530\n")
    
    for msg in messages[:5]:  # Show last 5
        print(f"To: {msg['to'][0]['phone_number']}")
        print(f"Status: {msg['to'][0]['status']}")
        print(f"Text: {msg['text'][:50]}...")
        print(f"Sent: {msg.get('sent_at', 'pending')}")
        
        if 'errors' in msg and msg['errors']:
            print(f"ERRORS: {msg['errors']}")
        
        print("-"*60)
    
    # Check if any failed
    failed = [m for m in messages if m['to'][0]['status'] != 'delivered']
    if failed:
        print(f"\n{len(failed)} messages NOT delivered!")
        for msg in failed[:3]:
            print(f"  To: {msg['to'][0]['phone_number']} - Status: {msg['to'][0]['status']}")
    else:
        print("\nAll messages delivered successfully!")
        print("Check James's phone - messages should be there!")
else:
    print(f"Failed: {response.status_code}")
    print(response.text)

print("="*60)

