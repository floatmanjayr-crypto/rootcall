# -*- coding: utf-8 -*-
import os
import requests

def create_badbot_agent_for_client(client_name, client_cell):
    """Create a Retell agent for a new BadBot client"""
    
    with open('.env', 'r') as f:
        for line in f:
            if 'RETELL_API_KEY=' in line:
                RETELL_API_KEY = line.split('=', 1)[1].strip()
                break
    
    prompt = f"""You are a call screener protecting {client_name}.

Ask: "Who is calling?"

IF LEGITIMATE (doctor, pharmacy, family):
Say "Transferring now" then use transfer_call tool.

IF SCAM (IRS, tech support, threats):
Say "Goodbye" then use end_call tool.

Keep responses short."""
    
    print(f"\nCreating agent for {client_name}...")
    
    # Correct format based on transfer call doc
    llm_payload = {
        "model": "gpt-4o",
        "general_prompt": prompt,
        "begin_message": "Hello, who is calling?",
        "general_tools": [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End call"
            },
            {
                "type": "transfer_call",
                "name": "transfer_call",
                "description": f"Transfer to {client_name}",
                "transfer_option": {
                    "transfer_destination": {
                        "type": "number",
                        "number": client_cell
                    },
                    "transfer_mode": "cold_transfer"
                }
            }
        ]
    }
    
    response = requests.post(
        "https://api.retellai.com/create-retell-llm",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=llm_payload
    )
    
    if response.status_code not in [200, 201]:
        print(f"Failed: {response.status_code}")
        print(response.text)
        return None
    
    llm = response.json()
    llm_id = llm.get('llm_id')
    print(f"LLM created: {llm_id}")
    
    # Create Agent
    agent_payload = {
        "agent_name": f"BadBot - {client_name}",
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
        json=agent_payload
    )
    
    if response.status_code not in [200, 201]:
        print(f"Failed: {response.status_code}")
        print(response.text)
        return None
    
    agent = response.json()
    agent_id = agent.get('agent_id')
    print(f"Agent created: {agent_id}")
    
    return {"agent_id": agent_id, "llm_id": llm_id}


if __name__ == "__main__":
    print("="*60)
    print("BADBOT AGENT CREATION TEST")
    print("="*60)
    
    result = create_badbot_agent_for_client("Test Client", "+15555551234")
    
    if result:
        print(f"\nSUCCESS!")
        print(f"Agent: {result['agent_id']}")
        print(f"LLM: {result['llm_id']}")
        print("\nClients can now get auto-configured agents!")
    else:
        print("\nFailed")

