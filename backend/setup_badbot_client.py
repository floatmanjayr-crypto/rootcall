#!/usr/bin/env python3
"""
BadBot Multi-Client Provisioning Script with Auto-Generated SIP
Usage: python setup_badbot_client.py --name "John Doe" --cell "+19545551234" --number "+18135559999"
"""
import os, sys, requests, json, argparse, secrets
from time import sleep

RETELL_BASE = "https://api.retellai.com"

def retell_request(method, endpoint, data=None):
    """Make Retell API request"""
    RETELL_API_KEY = os.getenv("RETELL_API_KEY")
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

def generate_sip_credentials(client_name):
    """Generate unique SIP credentials based on client name"""
    # Create username from client name (lowercase, no spaces)
    name_parts = client_name.lower().replace(" ", "").replace("'", "")
    
    # Extract first and last name
    words = client_name.split()
    if len(words) >= 2:
        username_base = f"{words[0].lower()}{words[-1].lower()}"
    else:
        username_base = words[0].lower()
    
    # Add random suffix for uniqueness (8 chars)
    random_suffix = secrets.token_hex(4)
    sip_username = f"{username_base}_{random_suffix}"
    
    # Generate secure random password (20 characters, alphanumeric + symbols)
    sip_password = secrets.token_urlsafe(20)
    
    return sip_username, sip_password

def provision_badbot_client(client_name, client_cell, telnyx_number, user_id=1, shared_agent=None):
    """Provision BadBot for a new client"""
    
    print("="*60)
    print(f"BADBOT PROVISIONING: {client_name}")
    print("="*60)
    print(f"Client Cell:    {client_cell}")
    print(f"Telnyx Number:  {telnyx_number}")
    print(f"User ID:        {user_id}")
    if shared_agent:
        print(f"Using Shared Agent: {shared_agent}")
    else:
        print(f"Creating Dedicated Agent")
    print("="*60)
    print()
    
    # Generate SIP credentials
    sip_username, sip_password = generate_sip_credentials(client_name)
    print(f"Generated SIP Credentials:")
    print(f"  Username: {sip_username}")
    print(f"  Password: {sip_password}")
    print(f"  (These will be saved to config file)")
    print()
    
    # Option 1: Use shared agent (faster, cheaper)
    if shared_agent:
        agent_id = shared_agent
        llm_id = None
        print("Using shared BadBot agent")
        print()
    
    # Option 2: Create dedicated agent (personalized)
    else:
        print("Step 1: Creating dedicated BadBot LLM...")
        print("-" * 60)
        
        BADBOT_PROMPT = f"""You are BadBot, a protective AI assistant for {client_name}. 

GREETING: "Hello, this is {client_name}'s assistant. Who's calling please?"

FRAUD RED FLAGS - Hang up immediately if caller:
- Requests SSN, bank account, passwords, credit card numbers
- Demands urgent payment via gift cards or wire transfer
- Claims to be IRS/police with arrest threats
- Says family member is in jail needing bail money
- Offers tech support for fake virus
- Says you won a prize but need to pay fees first

LEGITIMATE CALLERS - Transfer to {client_cell}:
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
                    "description": f"Transfer legitimate callers to {client_name}",
                    "number": client_cell
                }
            ],
            "states": [],
            "starting_state": "default",
            "model": "gpt-4o-mini",
            "temperature": 0.3,
            "max_tokens": 300
        }
        
        llm_response = retell_request("POST", "/create-retell-llm", llm_data)
        if llm_response and "llm_id" in llm_response:
            llm_id = llm_response["llm_id"]
            print(f"Created LLM: {llm_id}")
        else:
            print("Failed to create LLM")
            return None
        sleep(1)
        print()
        
        print("Step 2: Creating dedicated BadBot Agent...")
        print("-" * 60)
        
        agent_data = {
            "agent_name": f"BadBot - {client_name}",
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
            print(f"Created Agent: {agent_id}")
        else:
            print("Failed to create agent")
            return None
        sleep(1)
        print()
    
    # Step 3: Import number to Retell
    print(f"Step 3: Importing {telnyx_number} to Retell...")
    print("-" * 60)
    
    import_data = {
        "phone_number": telnyx_number,
        "termination_uri": "sip.telnyx.com",
        "sip_trunk_auth": {
            "username": sip_username,
            "password": sip_password
        },
        "inbound_agent_id": agent_id,
        "outbound_agent_id": agent_id,
        "nickname": f"BadBot - {client_name}"
    }
    
    import_response = retell_request("POST", "/import-phone-number", import_data)
    if import_response and "phone_number" in import_response:
        print(f"Successfully imported {telnyx_number}")
    else:
        print("Warning: Import may have failed or number already imported")
        print("Continuing with provisioning...")
    print()
    
    # Step 4: Create database records
    print("Step 4: Creating database records...")
    print("-" * 60)
    
    try:
        from app.database import SessionLocal
        from app.models.phone_number import PhoneNumber
        from app.models.rootcall_config import BadBotConfig
        from app.models.ai_agent import AIAgent
        
        db = SessionLocal()
        
        # Check if phone exists
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == telnyx_number
        ).first()
        
        if not phone:
            phone = PhoneNumber(
                user_id=user_id,
                phone_number=telnyx_number,
                friendly_name=f"BadBot - {client_name}",
                country_code="US",
                is_active=True,
                monthly_cost=2.0
            )
            db.add(phone)
            db.flush()
            print(f"Created PhoneNumber: {phone.id}")
        else:
            print(f"Using existing PhoneNumber: {phone.id}")
        
        # Create/update AIAgent if dedicated
        if not shared_agent and llm_id:
            agent_record = AIAgent(
                user_id=user_id,
                name=f"BadBot - {client_name}",
                retell_agent_id=agent_id,
                retell_llm_id=llm_id,
                is_active=True
            )
            db.add(agent_record)
            db.flush()
            phone.ai_agent_id = agent_record.id
            print(f"Created AIAgent: {agent_record.id}")
        
        # Check if config exists
        config = db.query(BadBotConfig).filter(
            BadBotConfig.phone_number_id == phone.id
        ).first()
        
        if config:
            print("Updating existing BadBotConfig...")
            config.client_name = client_name
            config.client_cell = client_cell
            config.retell_agent_id = agent_id
            config.is_active = True
        else:
            config = BadBotConfig(
                phone_number_id=phone.id,
                user_id=user_id,
                client_name=client_name,
                client_cell=client_cell,
                retell_agent_id=agent_id,
                retell_did=telnyx_number,
                trusted_contacts=[],
                caregiver_cell="",
                sms_alerts_enabled=True,
                alert_on_spam=True,
                auto_block_spam=True,
                is_active=True
            )
            db.add(config)
            print("Created BadBotConfig")
        
        db.commit()
        print("Database saved successfully!")
        db.close()
        
    except Exception as e:
        print(f"Database error: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    print()
    print("="*60)
    print("PROVISIONING COMPLETE!")
    print("="*60)
    print()
    print("Summary:")
    print(f"  Client:        {client_name}")
    print(f"  BadBot Number: {telnyx_number}")
    print(f"  Client Cell:   {client_cell}")
    print(f"  Agent ID:      {agent_id}")
    if llm_id:
        print(f"  LLM ID:        {llm_id}")
    print()
    print("SIP Credentials (SAVE THESE):")
    print(f"  Username: {sip_username}")
    print(f"  Password: {sip_password}")
    print()
    print("Portal Access:")
    print("  /api/v1/badbot/portal/dashboard")
    print("  /api/v1/badbot/portal/trusted-contacts")
    print()
    
    return {
        "success": True,
        "client_name": client_name,
        "telnyx_number": telnyx_number,
        "client_cell": client_cell,
        "agent_id": agent_id,
        "llm_id": llm_id,
        "sip_username": sip_username,
        "sip_password": sip_password
    }

def main():
    parser = argparse.ArgumentParser(description="Provision BadBot for client")
    parser.add_argument("--name", required=True, help="Client name")
    parser.add_argument("--cell", required=True, help="Client cell (+1234567890)")
    parser.add_argument("--number", required=True, help="Telnyx number to use (+1234567890)")
    parser.add_argument("--user-id", type=int, default=1, help="Database user ID")
    parser.add_argument("--shared-agent", help="Use shared agent ID (Option 1)")
    
    args = parser.parse_args()
    
    result = provision_badbot_client(
        client_name=args.name,
        client_cell=args.cell,
        telnyx_number=args.number,
        user_id=args.user_id,
        shared_agent=args.shared_agent
    )
    
    if result:
        # Save config to file
        filename = f"badbot_{args.number.replace('+', '')}.json"
        with open(filename, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Config saved to: {filename}")
        print()
        print("IMPORTANT: Add these SIP credentials to your Telnyx trunk!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    if not os.getenv("RETELL_API_KEY"):
        print("ERROR: RETELL_API_KEY not set")
        sys.exit(1)
    
    main()
