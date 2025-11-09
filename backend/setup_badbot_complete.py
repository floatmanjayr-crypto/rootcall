#!/usr/bin/env python3
import os, sys, requests, json
from time import sleep

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
TELNYX_NUMBER = "+18135478218"
CLIENT_CELL = "+17543314009"
CLIENT_NAME = "Primary Senior Client"
RETELL_BASE = "https://api.retellai.com"

def retell_request(method, endpoint, data=None):
    url = f"{RETELL_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {RETELL_API_KEY}", "Content-Type": "application/json"}
    if method == "GET": 
        r = requests.get(url, headers=headers)
    elif method == "POST": 
        r = requests.post(url, headers=headers, json=data)
    elif method == "DELETE": 
        r = requests.delete(url, headers=headers)
    else: 
        raise ValueError(f"Unknown method: {method}")
    if r.status_code >= 400: 
        print(f"Error {r.status_code}: {r.text}")
        return None
    return r.json() if r.text else {}

print("="*60)
print("BADBOT COMPLETE SETUP")
print("="*60)
print()

print("Step 1: Removing +18135478218 from Retell...")
print("-" * 60)
phone_numbers = retell_request("GET", "/list-phone-numbers")
if phone_numbers:
    for phone in phone_numbers:
        if phone.get("phone_number") == TELNYX_NUMBER:
            phone_number_id = phone.get("phone_number_id")
            print(f"Found: {TELNYX_NUMBER} (ID: {phone_number_id})")
            result = retell_request("DELETE", f"/delete-phone-number/{phone_number_id}")
            if result is not None: 
                print(f"Deleted {TELNYX_NUMBER}")
            break
else:
    print("Could not fetch phone numbers or number not found")
sleep(2)
print()

print("Step 2: Creating BadBot LLM with fraud detection...")
print("-" * 60)

BADBOT_PROMPT = f"""You are BadBot, a protective AI assistant for {CLIENT_NAME}, a senior citizen.

GREETING: "Hello, this is {CLIENT_NAME}'s assistant. Who's calling please?"

FRAUD RED FLAGS - Hang up immediately if caller:
- Requests SSN, bank account, passwords, credit card numbers
- Demands urgent payment via gift cards or wire transfer
- Claims to be IRS/police with arrest threats
- Says family member is in jail needing bail money
- Offers tech support for fake virus
- Says you won a prize but need to pay fees first

LEGITIMATE CALLERS - Transfer to {CLIENT_CELL}:
- Healthcare providers (doctors, pharmacy)
- Known businesses the client uses
- Verified family members

YOUR RESPONSES:
For legitimate callers: "Thank you for calling. Let me connect you now." Then transfer.
For fraud/scam: "I cannot help with that request. Goodbye." Then hang up.
For unclear: Ask verification questions. Take message if unsure.

CRITICAL RULES:
- NEVER give out personal information
- NEVER confirm addresses or account details
- When in doubt, take a message instead of transferring
- Better to miss a legitimate call than let a scammer through
"""

llm_data = {
    "general_prompt": BADBOT_PROMPT,
    "general_tools": [
        {
            "type": "end_call",
            "name": "end_call",
            "description": "End call when fraud is detected"
        },
        {
            "type": "transfer_call",
            "name": "transfer_to_client",
            "description": f"Transfer legitimate callers to {CLIENT_NAME}",
            "number": CLIENT_CELL
        }
    ],
    "states": [],
    "starting_state": "default",
    "model": "gpt-4o",
    "temperature": 0.3,
    "max_tokens": 300
}

llm_response = retell_request("POST", "/create-retell-llm", llm_data)
if llm_response and "llm_id" in llm_response:
    llm_id = llm_response["llm_id"]
    print(f"Created BadBot LLM: {llm_id}")
else:
    print("Failed to create LLM")
    sys.exit(1)
sleep(2)
print()

print("Step 3: Creating BadBot Agent...")
print("-" * 60)

agent_data = {
    "agent_name": f"BadBot Guard for {CLIENT_NAME}",
    "llm_websocket_url": f"wss://api.retellai.com/llm-websocket/{llm_id}",
    "voice_id": "11labs-Adrian",
    "language": "en-US",
    "response_engine": {
        "type": "retell-llm",
        "llm_id": llm_id
    },
    "interruption_sensitivity": 0.5,
    "enable_backchannel": True,
    "backchannel_frequency": 0.8
}

agent_response = retell_request("POST", "/create-agent", agent_data)
if agent_response and "agent_id" in agent_response:
    agent_id = agent_response["agent_id"]
    print(f"Created BadBot Agent: {agent_id}")
else:
    print("Failed to create agent")
    sys.exit(1)
sleep(2)
print()

print("Step 4: Getting Telnyx SIP credentials...")
print("-" * 60)
print("Go to: https://portal.telnyx.com/#/app/connections")
print("Find your SIP trunk (probably 'voip5') and copy the credentials")
print()

sip_username = input("Enter SIP Username: ").strip()
sip_password = input("Enter SIP Password: ").strip()

if not sip_username or not sip_password:
    print("SIP credentials are required")
    sys.exit(1)
print()

print("Step 5: Importing +18135478218 to Retell...")
print("-" * 60)

import_data = {
    "phone_number": TELNYX_NUMBER,
    "termination_uri": "sip.telnyx.com",
    "sip_trunk_auth": {
        "username": sip_username,
        "password": sip_password
    },
    "inbound_agent_id": agent_id,
    "outbound_agent_id": agent_id,
    "nickname": f"BadBot Line - {CLIENT_NAME}"
}

import_response = retell_request("POST", "/import-phone-number", import_data)
if import_response and "phone_number" in import_response:
    print(f"Successfully imported {TELNYX_NUMBER} to Retell")
else:
    print("Failed to import number")
    print("Make sure the number is assigned to your Telnyx SIP trunk")
    sys.exit(1)
print()

print("Step 6: Updating backend configuration...")
print("-" * 60)

config_content = f"""from typing import Dict, List, Optional

CLIENT_LINES: Dict[str, Dict] = {{}}

def get_client_config(telnyx_number: str) -> Optional[Dict]:
    normalized = telnyx_number.strip()
    if not normalized.startswith("+"):
        normalized = f"+{{normalized}}"
    return CLIENT_LINES.get(normalized)

# BadBot Client Configuration
CLIENT_LINES["{TELNYX_NUMBER}"] = {{
    "client_cell": "{CLIENT_CELL}",
    "client_name": "{CLIENT_NAME}",
    "retell_agent_id": "{agent_id}",
    "retell_did": "{TELNYX_NUMBER}",
    "trusted_contacts": [
        # Add trusted numbers here, e.g.:
        # "+17545551234",  # Family member
    ],
    "caregiver_cell": ""
}}
"""

with open("app/services/client_config.py", "w") as f:
    f.write(config_content)

print("Updated app/services/client_config.py")
print()

print("="*60)
print("BADBOT SETUP COMPLETE!")
print("="*60)
print()
print("Configuration Summary:")
print(f"  Telnyx Number:  {TELNYX_NUMBER}")
print(f"  Client Cell:    {CLIENT_CELL}")
print(f"  BadBot LLM:     {llm_id}")
print(f"  BadBot Agent:   {agent_id}")
print()
print("="*60)
print("CLIENT SETUP INSTRUCTIONS")
print("="*60)
print()
print(f"Have your client forward calls to: {TELNYX_NUMBER}")
print()
print("AT&T/VERIZON:")
print(f"  1. Dial *72")
print(f"  2. Enter: {TELNYX_NUMBER.replace('+', '')}")
print(f"  3. Wait for confirmation")
print()
print("T-MOBILE:")
print(f"  Dial: **21*{TELNYX_NUMBER.replace('+', '')}#")
print()
print("="*60)
print("TEST THE SETUP")
print("="*60)
print()
print(f"1. Call {TELNYX_NUMBER} from your phone")
print("2. BadBot should answer: 'Hello, who's calling please?'")
print()
print("3. Test fraud detection:")
print("   Say: 'This is the IRS, you owe back taxes'")
print("   BadBot should hang up immediately")
print()
print("4. Test legitimate transfer:")
print("   Call again and say: 'This is Dr. Smith's office'")
print("   BadBot should offer to transfer you")
print()
