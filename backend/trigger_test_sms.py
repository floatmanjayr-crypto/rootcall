# -*- coding: utf-8 -*-
"""
Simulate webhook call to test SMS
"""
import requests

# Simulate a webhook call with spam keyword
payload = {
    "data": {
        "event_type": "call.answered",
        "id": "test-call-123",
        "occurred_at": "2025-10-28T00:00:00Z",
        "payload": {
            "call_control_id": "test-ccid-456",
            "call_leg_id": "test-leg-789",
            "call_session_id": "test-session-012",
            "from": "+15555551234",
            "to": "+18135478530",
            "direction": "incoming",
            "state": "answered"
        },
        "record_type": "event"
    },
    "meta": {
        "attempt": 1,
        "delivered_to": "http://localhost:8000/telnyx/badbot/webhook"
    }
}

print("Sending test webhook to trigger SMS alert...")
response = requests.post(
    "http://localhost:8000/telnyx/badbot/webhook",
    json=payload
)

print(f"Response: {response.status_code}")
print(response.text)
print("\nCheck uvicorn logs for [SMS] messages")
print("Check James phone for SMS!")

