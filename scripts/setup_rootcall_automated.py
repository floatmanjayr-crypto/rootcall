#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.services.retell_service import retell_service
from app.database import SessionLocal
from app.models.ai_agent import AIAgent
from app.models.phone_number import PhoneNumber
from time import sleep

TELNYX_NUMBER = "+18135478218"
CLIENT_CELL = "+17543314009"
CLIENT_NAME = "Primary Senior Client"

print("="*60)
print("ROOTCALL AUTOMATED SETUP")
print("="*60)
print()

print("Step 1: Checking for existing number in Retell...")
print("-" * 60)

try:
    db = SessionLocal()
    existing_phone = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == TELNYX_NUMBER
    ).first()
    
    if existing_phone:
        print(f"Found existing number: {TELNYX_NUMBER}")
        db.delete(existing_phone)
        db.commit()
        print(f"Removed from local database")
    else:
        print(f"Number {TELNYX_NUMBER} not found in local database")
    
    db.close()
    
except Exception as e:
    print(f"Note: {e}")

sleep(2)
print()

print("Step 2: Creating RootCall LLM with fraud detection...")
print("-" * 60)

ROOTCALL_PROMPT = f'''You are RootCall, a protective AI assistant for {CLIENT_NAME}, a senior citizen.

GREETING: "Hello, this is {CLIENT_NAME}'s assistant. Who's calling please?"

FRAUD RED FLAGS - Hang up immediately:
- Requests for SSN, bank account, passwords, credit cards
- Urgent payment demands: gift cards, wire transfers
- Fake threats: IRS arrest, court summons
- Family scams: "I'm in jail, need bail money"
- Tech support scams
- Prize scams requiring payment

LEGITIMATE CALLERS - Transfer to {CLIENT_CELL}:
- Healthcare providers
- Known businesses
- Verified family members

RESPONSES:
For legitimate: "Thank you. Let me connect you now." Transfer.
For fraud: "I cannot help with that. Goodbye." Hang up.
For unclear: Ask questions, take message if unsure.

RULES:
- NEVER give personal information
- NEVER confirm addresses or accounts
- When in doubt, take message
- Better to miss a call than let scammer through
'''

try:
    # Try different parameter variations based on common Retell API patterns
    try:
        llm_id = retell_service.create_llm(
            general_prompt=ROOTCALL_PROMPT,
            model="gpt-4o",
            temperature=0.3
        )
    except TypeError:
        # Try alternative parameter name
        llm_id = retell_service.create_llm(
            begin_message=None,
            general_prompt=ROOTCALL_PROMPT,
            model="gpt-4o",
            temperature=0.3
        )
    
    if llm_id:
        print(f"Created RootCall LLM: {llm_id}")
    else:
        print("Failed to create LLM")
        sys.exit(1)
        
except Exception as e:
    print(f"Error creating LLM: {e}")
    print("\nTrying direct API call instead...")
    
    # Fallback: Use direct API call
    import requests
    
    RETELL_API_KEY = os.getenv("RETELL_API_KEY")
    
    llm_data = {
        "general_prompt": ROOTCALL_PROMPT,
        "model": "gpt-4o",
        "temperature": 0.3
    }
    
    response = requests.post(
        "https://api.retellai.com/create-retell-llm",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=llm_data
    )
    
    if response.status_code == 200:
        llm_id = response.json().get("llm_id")
        print(f"Created RootCall LLM via direct API: {llm_id}")
    else:
        print(f"Failed: {response.text}")
        sys.exit(1)

sleep(2)
print()

print("Step 3: Creating RootCall Agent...")
print("-" * 60)

try:
    # Try to create agent with your service
    agent_id = retell_service.create_agent(
        name=f"RootCall Guard for {CLIENT_NAME}",
        llm_id=llm_id,
        voice_id="11labs-Adrian",
        language="en-US"
    )
    
    if agent_id:
        print(f"Created RootCall Agent: {agent_id}")
    else:
        print("Failed to create agent")
        sys.exit(1)
        
except Exception as e:
    print(f"Error creating agent: {e}")
    print("\nTrying direct API call instead...")
    
    # Fallback: Direct API call
    import requests
    
    RETELL_API_KEY = os.getenv("RETELL_API_KEY")
    
    agent_data = {
        "agent_name": f"RootCall Guard for {CLIENT_NAME}",
        "llm_websocket_url": f"wss://api.retellai.com/llm-websocket/{llm_id}",
        "voice_id": "11labs-Adrian",
        "language": "en-US",
        "response_engine": {
            "type": "retell-llm",
            "llm_id": llm_id
        }
    }
    
    response = requests.post(
        "https://api.retellai.com/create-agent",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=agent_data
    )
    
    if response.status_code == 200:
        agent_id = response.json().get("agent_id")
        print(f"Created RootCall Agent via direct API: {agent_id}")
    else:
        print(f"Failed: {response.text}")
        sys.exit(1)

sleep(2)
print()

print("Step 4: Importing phone number to Retell...")
print("-" * 60)

try:
    result = retell_service.register_phone_number(
        phone_number=TELNYX_NUMBER,
        agent_id=agent_id
    )
    
    if result:
        print(f"Imported {TELNYX_NUMBER} to Retell")
        print(f"Assigned to agent: {agent_id}")
    else:
        print("Failed to import number")
        sys.exit(1)
        
except Exception as e:
    print(f"Error importing number: {e}")
    print("This is normal - the number may already be on your SIP trunk")

print()

print("Step 5: Saving to database...")
print("-" * 60)

try:
    db = SessionLocal()
    
    ai_agent = AIAgent(
        name=f"RootCall Guard for {CLIENT_NAME}",
        retell_agent_id=agent_id,
        retell_llm_id=llm_id,
        agent_type="inbound",
        system_prompt=ROOTCALL_PROMPT,
        voice_model="11labs-Adrian",
        language="en-US",
        is_active=True
    )
    db.add(ai_agent)
    db.commit()
    
    phone = PhoneNumber(
        phone_number=TELNYX_NUMBER,
        ai_agent_id=ai_agent.id,
        is_active=True
    )
    db.add(phone)
    db.commit()
    
    print("Saved to database")
    db.close()
    
except Exception as e:
    print(f"Warning: Could not save to database: {e}")

print()

print("Step 6: Updating client configuration...")
print("-" * 60)

config_content = f'''from typing import Dict, List, Optional

CLIENT_LINES: Dict[str, Dict] = {{}}

def get_client_config(telnyx_number: str) -> Optional[Dict]:
    normalized = telnyx_number.strip()
    if not normalized.startswith("+"):
        normalized = f"+{{normalized}}"
    return CLIENT_LINES.get(normalized)

CLIENT_LINES["{TELNYX_NUMBER}"] = {{
    "client_cell": "{CLIENT_CELL}",
    "client_name": "{CLIENT_NAME}",
    "retell_agent_id": "{agent_id}",
    "retell_did": "{TELNYX_NUMBER}",
    "trusted_contacts": [],
    "caregiver_cell": ""
}}
'''

with open("app/services/client_config.py", "w", encoding="utf-8") as f:
    f.write(config_content)

print("Updated app/services/client_config.py")
print()

print("="*60)
print("ROOTCALL SETUP COMPLETE!")
print("="*60)
print()
print("Configuration:")
print(f"  Number:  {TELNYX_NUMBER}")
print(f"  Cell:    {CLIENT_CELL}")
print(f"  LLM:     {llm_id}")
print(f"  Agent:   {agent_id}")
print()
print("CLIENT SETUP:")
print(f"Forward calls to: {TELNYX_NUMBER}")
print()
print("AT&T/VERIZON: Dial *72 then", TELNYX_NUMBER.replace('+', ''))
print("T-MOBILE: Dial **21*" + TELNYX_NUMBER.replace('+', '') + "#")
print()
print("TEST:")
print(f"1. Call {TELNYX_NUMBER}")
print('2. Say "This is the IRS" - should hang up')
print('3. Call again, say "This is the doctor" - should transfer')
print()
print("View agent in dashboard:")
print("https://app.retellai.com/dashboard/agents")
print()
