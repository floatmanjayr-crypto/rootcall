# -*- coding: utf-8 -*-
import os
import requests

# Load API key
with open('.env', 'r') as f:
    for line in f:
        if 'RETELL_API_KEY=' in line:
            RETELL_API_KEY = line.split('=', 1)[1].strip()

AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"
CLIENT_CELL = "+17543670370"

print("="*60)
print("RETELL AGENT TRANSFER SETUP")
print("="*60)

# Correct endpoint format
url = f"https://api.retellai.com/v2/agent/{AGENT_ID}"

agent_update = {
    "general_tools": [
        {
            "type": "end_call",
            "name": "end_call",
            "description": "End call"
        },
        {
            "type": "transfer_call",
            "name": "transfer_call",
            "description": "Transfer to client",
            "number": CLIENT_CELL
        }
    ]
}

print(f"\nUpdating agent: {AGENT_ID}")
print(f"Transfer to: {CLIENT_CELL}")

response = requests.patch(
    url,
    headers={
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    },
    json=agent_update
)

print(f"\nResponse: {response.status_code}")
print(response.text)

if response.status_code in [200, 201]:
    print("\nSUCCESS! Call +18135478530 to test!")
else:
    print("\nFailed - manual setup required in Retell Dashboard")
    print("Go to: https://app.retellai.com")
    print(f"Edit agent: {AGENT_ID}")
    print("Add Transfer Call tool")
    print(f"Set number: {CLIENT_CELL}")
