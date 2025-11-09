# -*- coding: utf-8 -*-
import os
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"
AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"
LLM_ID = "llm_ae6101e4ce21dd1aa4b4d92f0f91"

print("Fixing transfer with correct API format...")

llm_update = {
    "general_prompt": """Brief screener. Ask: Who is calling?

Doctor/pharmacy/family: Say One moment and use transfer_to_client.
IRS/scam: Say Cannot help and use end_call.

Use tools immediately.""",
    "general_tools": [
        {
            "type": "end_call",
            "name": "end_call",
            "description": "End scam calls"
        },
        {
            "type": "transfer_call",
            "name": "transfer_to_client",
            "description": "Transfer to client",
            "transfer_destination": {
                "type": "number",
                "number": "+17543670370"
            }
        }
    ]
}

response = requests.patch(
    f"{RETELL_BASE}/update-retell-llm/{LLM_ID}",
    headers={
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    },
    json=llm_update
)

if response.status_code == 200:
    print("Transfer configured correctly!")
    print("TEST: Call +18135478530")
    print("Say: Doctors office")
    print("Should transfer to: +17543670370")
else:
    print(f"Error {response.status_code}:")
    print(response.text)
