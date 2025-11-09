import os
import requests

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
PHONE_NUMBER = "+18135478530"
NEW_WEBHOOK = "https://declinatory-gonidioid-elise.ngrok-free.dev/api/v1/telnyx/badbot/webhook"

print("Updating Telnyx webhook for", PHONE_NUMBER)

# Step 1: Find the phone number ID
response = requests.get(
    "https://api.telnyx.com/v2/phone_numbers",
    headers={"Authorization": f"Bearer {TELNYX_API_KEY}"}
)

if response.status_code != 200:
    print(f"Error getting phone numbers: {response.text}")
    exit(1)

numbers = response.json().get('data', [])
phone = None
for num in numbers:
    if num.get('phone_number') == PHONE_NUMBER:
        phone = num
        break

if not phone:
    print(f"Phone number {PHONE_NUMBER} not found!")
    exit(1)

phone_id = phone.get('id')
connection_id = phone.get('connection_id')

print(f"Found phone: {phone_id}")
print(f"Connection ID: {connection_id}")

# Step 2: Update the connection's webhook
if connection_id:
    response = requests.patch(
        f"https://api.telnyx.com/v2/telephony_credentials/{connection_id}",
        headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
        json={
            "webhook_event_url": NEW_WEBHOOK,
            "webhook_event_failover_url": ""
        }
    )
    
    if response.status_code in [200, 202]:
        print(f"SUCCESS! Webhook updated to: {NEW_WEBHOOK}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
else:
    print("No connection_id found. Trying messaging profile...")
    
    # Alternative: Update messaging profile
    profile_id = phone.get('messaging_profile_id')
    if profile_id:
        response = requests.patch(
            f"https://api.telnyx.com/v2/messaging_profiles/{profile_id}",
            headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
            json={
                "webhook_url": NEW_WEBHOOK
            }
        )
        
        if response.status_code in [200, 202]:
            print(f"SUCCESS! Webhook updated via messaging profile")
        else:
            print(f"Error: {response.text}")

print("\nNow call +18135478530 to test!")
