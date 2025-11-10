# -*- coding: utf-8 -*-
"""
Setup SMS alerts for RootCall clients
"""
import os
import requests

def send_telnyx_sms(to_number, from_number, message):
    """Send SMS via Telnyx"""
    
    with open('.env', 'r') as f:
        for line in f:
            if 'TELNYX_API_KEY=' in line:
                TELNYX_API_KEY = line.split('=', 1)[1].strip()
                break
    
    url = "https://api.telnyx.com/v2/messages"
    
    payload = {
        "from": from_number,
        "to": to_number,
        "text": message
    }
    
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    
    if response.status_code in [200, 201, 202]:
        print(f"SMS sent to {to_number}")
        return True
    else:
        print(f"SMS failed: {response.status_code}")
        print(response.text)
        return False


print("="*60)
print("SMS ALERT SYSTEM TEST")
print("="*60)

# Test SMS to James
result = send_telnyx_sms(
    to_number="+17543670370",
    from_number="+18135478530",
    message="[RootCall] Test: SMS alerts are working!"
)

if result:
    print("\nSUCCESS! Check James phone for test message")
else:
    print("\nFailed - check Telnyx messaging configuration")

print("="*60)

