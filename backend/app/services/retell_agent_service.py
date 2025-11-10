"""
Shared Retell Agent Service
ONE agent, customized per client dynamically
"""
import os
import requests
import logging

log = logging.getLogger(__name__)

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"

# Shared agent ID (set this after creating the agent once)
SHARED_AGENT_ID = os.getenv("RETELL_SHARED_AGENT_ID", None)
SHARED_LLM_ID = os.getenv("RETELL_SHARED_LLM_ID", None)


def get_or_create_shared_agent():
    """Get existing shared agent or create one if doesn't exist"""
    
    if SHARED_AGENT_ID and SHARED_LLM_ID:
        log.info(f"‚úÖ Using existing shared agent: {SHARED_AGENT_ID}")
        return {
            "agent_id": SHARED_AGENT_ID,
            "llm_id": SHARED_LLM_ID
        }
    
    # Create shared agent on first run
    log.info("Ì∂ï Creating shared RootCall agent (first time setup)...")
    
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Create shared LLM with dynamic prompt
    llm_prompt = """You are RootCall AI, a professional call screening assistant.

Your mission is to protect your client from phone scams and unwanted calls.

IMPORTANT: The client's name will be provided at the start of each call. Use it naturally.

GREETING:
"Hello, you've reached [CLIENT_NAME]'s RootCall protection line. May I ask who's calling and the reason for your call?"

SCREENING PROCESS:
1. Politely ask caller to identify themselves
2. Listen for scam indicators
3. Make decision: TRANSFER or BLOCK

RED FLAGS (Auto-block):
- IRS/tax threats
- Tech support scams
- Prize/lottery scams
- Grandparent scams
- Requests for personal info (SSN, credit card, passwords)
- Robocalls or pre-recorded messages
- Threatening or intimidating language

GREEN FLAGS (Transfer):
- Family members and friends
- Expected business calls
- Medical professionals
- Delivery notifications
- Scheduled appointments

BLOCKING SCAMS:
"I'm sorry, this appears to be a fraudulent call. [CLIENT_NAME] does not wish to receive these calls. Goodbye."

TRANSFERRING LEGITIMATE CALLS:
"Thank you. One moment while I connect you to [CLIENT_NAME]."

TONE: Professional, polite, firm with scammers, helpful with legitimate callers.
DURATION: Keep calls under 30 seconds."""

    # Create LLM
    llm_response = requests.post(
        f"{RETELL_BASE}/create-retell-llm",
        headers=headers,
        json={
            "general_prompt": llm_prompt,
            "model": "gpt-4o-mini"
        }
    )
    
    if llm_response.status_code not in [200, 201]:
        raise Exception(f"Failed to create shared LLM: {llm_response.text}")
    
    llm_id = llm_response.json()["llm_id"]
    
    # Create Agent
    agent_response = requests.post(
        f"{RETELL_BASE}/create-agent",
        headers=headers,
        json={
            "agent_name": "RootCall Shared Screening Agent",
            "llm_id": llm_id,
            "voice_id": "11labs-Adrian",
            "responsiveness": 1,
            "enable_backchannel": True,
            "language": "en-US"
        }
    )
    
    if agent_response.status_code not in [200, 201]:
        raise Exception(f"Failed to create shared agent: {agent_response.text}")
    
    agent_id = agent_response.json()["agent_id"]
    
    log.info(f"‚úÖ Shared agent created!")
    log.info(f"   Agent ID: {agent_id}")
    log.info(f"   LLM ID: {llm_id}")
    log.info(f"‚ö†Ô∏è  Add to Render environment variables:")
    log.info(f"   RETELL_SHARED_AGENT_ID={agent_id}")
    log.info(f"   RETELL_SHARED_LLM_ID={llm_id}")
    
    return {
        "agent_id": agent_id,
        "llm_id": llm_id
    }


def customize_for_call(client_name: str, caller_number: str = None):
    """
    Generate call-specific context to inject into the shared agent
    This customizes the agent's behavior for each client
    """
    context = {
        "client_name": client_name,
        "caller_number": caller_number,
        "custom_greeting": f"Hello, you've reached {client_name}'s RootCall protection line. May I ask who's calling?",
        "variables": {
            "CLIENT_NAME": client_name
        }
    }
    
    return context
