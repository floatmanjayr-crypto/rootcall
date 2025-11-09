# -*- coding: utf-8 -*-
"""
Complete Retell + Telnyx BadBot Setup with Transfer Call Tool
Using Retell's pre-built transfer_call function
"""
import os
import requests

# Load API keys
with open('.env', 'r') as f:
    for line in f:
        if 'RETELL_API_KEY=' in line:
            RETELL_API_KEY = line.split('=', 1)[1].strip()

AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"
CLIENT_CELL = "+17543670370"

print("="*60)
print("COMPLETE RETELL BADBOT AUTOMATION")
print("="*60)

# Step 1: Update agent to add transfer_call as a general tool
print("\n1. Adding transfer_call tool to Retell agent...")

agent_update = {
    "agent_name": "BadBot - Fraud Protection",
    "general_prompt": """You are a call screener. Ask: "Who is calling?"

IF LEGITIMATE (doctor, pharmacy, family member):
Say "One moment please" then use transfer_call tool.

IF SCAM (IRS, tech support, threats):
Say "I cannot help with that" then use end_call tool.

Always use the tools.""",
    "general_tools": [
        {
            "type": "end_call",
            "name": "end_call",
            "description": "End call for scammers"
        },
        {
            "type": "transfer_call",
            "name": "transfer_call",
            "description": "Transfer to client",
            "number": CLIENT_CELL
        }
    ]
}

response = requests.patch(
    f"https://api.retellai.com/update-agent/{AGENT_ID}",
    headers={
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    },
    json=agent_update
)

if response.status_code == 200:
    print("SUCCESS! Agent configured!")
    print(f"Transfer to: {CLIENT_CELL}")
    print("\nTEST: Call +18135478530")
else:
    print(f"Failed: {response.status_code}")
    print(response.text)

print("="*60)
