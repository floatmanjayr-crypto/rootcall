# -*- coding: utf-8 -*-
import os
import requests
import json

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"
AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"

print("="*60)
print("CONFIGURING AGENT TRANSFER VIA API")
print("="*60)

# Step 1: Get current agent configuration
print("\n1. Getting current agent...")
response = requests.get(
    f"{RETELL_BASE}/get-agent/{AGENT_ID}",
    headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
)

if response.status_code != 200:
    print(f"Error getting agent: {response.text}")
    exit(1)

agent = response.json()
print(f"Current agent: {agent.get('agent_name')}")

# Step 2: Update agent with transfer tool
print("\n2. Adding transfer tool to agent...")

# According to Retell docs, tools are configured at agent level
agent_update = {
    "agent_name": "BadBot - Fraud Protection",
    "voice_id": "11labs-Adrian",
    "language": "en-US",
    "general_prompt": """You are a call screener. Ask: "Who's calling?"

LEGITIMATE (use transfer_call tool):
- Doctor, pharmacy, hospital
- Family member by name
- Expected business calls

SCAM (use end_call tool):
- IRS, police, government threats
- Tech support, virus warnings
- Gift card or wire transfer requests
- Won't identify themselves

Keep responses under 5 words. Always use the tools.""",
    "begin_message": None,
    "general_tools": [
        {
            "type": "end_call",
            "name": "end_call",
            "description": "End the call for scams"
        },
        {
            "type": "transfer_call",
            "name": "transfer_call",
            "description": "Transfer legitimate callers",
            "transfer_option": {
                "transfer_destination": {
                    "type": "number",
                    "number": "+17543670370"
                },
                "transfer_mode": "cold_transfer",
                "caller_id_setting": {
                    "type": "user_number"
                }
            }
        }
    ],
    "responsiveness": 1,
    "interruption_sensitivity": 1,
    "enable_backchannel": True,
    "backchannel_frequency": 0.8
}

response = requests.patch(
    f"{RETELL_BASE}/update-agent/{AGENT_ID}",
    headers={
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    },
    json=agent_update
)

if response.status_code == 200:
    print("SUCCESS! Transfer tool configured!")
    print("\nConfiguration:")
    print("  Transfer to: +17543670370")
    print("  Type: Cold Transfer")
    print("  Caller ID: User's Number")
    print("\n" + "="*60)
    print("TEST NOW:")
    print("="*60)
    print("1. Call: +18135478530")
    print("2. BadBot: 'Who's calling?'")
    print("3. Say: 'Dr. Smith's office'")
    print("4. BadBot: 'One moment please'")
    print("5. Should transfer to: +17543670370")
    print("="*60)
else:
    print(f"\nError {response.status_code}:")
    print(response.text)
    print("\nTrying alternative format...")
    
    # Try simpler format
    agent_update["general_tools"][1] = {
        "type": "transfer_call",
        "name": "transfer_call", 
        "description": "Transfer to client",
        "number": "+17543670370"
    }
    
    response = requests.patch(
        f"{RETELL_BASE}/update-agent/{AGENT_ID}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=agent_update
    )
    
    if response.status_code == 200:
        print("SUCCESS with alternative format!")
    else:
        print(f"Still failed: {response.text}")
