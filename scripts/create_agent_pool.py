# -*- coding: utf-8 -*-
"""
Create a pool of pre-configured Retell agents
"""
import os
import requests

def create_agent_without_transfer(agent_name):
    """Create agent via API (without transfer tool)"""
    
    with open('.env', 'r') as f:
        for line in f:
            if 'RETELL_API_KEY=' in line:
                RETELL_API_KEY = line.split('=', 1)[1].strip()
                break
    
    # Create LLM with only end_call tool
    llm_payload = {
        "model": "gpt-4o",
        "general_prompt": """You are a call screener.

Ask: "Who is calling?"

IF LEGITIMATE (doctor, pharmacy, family):
Say "Transferring now" then use transfer_call tool.

IF SCAM (IRS, tech support, threats):
Say "Goodbye" then use end_call tool.

Keep responses short.""",
        "begin_message": "Hello, who is calling?",
        "general_tools": [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End call"
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
        print(f"Failed to create LLM: {response.text}")
        return None
    
    llm = response.json()
    llm_id = llm.get('llm_id')
    
    # Create Agent
    agent_payload = {
        "agent_name": agent_name,
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
        print(f"Failed to create agent: {response.text}")
        return None
    
    agent = response.json()
    return {
        "agent_id": agent.get('agent_id'),
        "llm_id": llm_id,
        "agent_name": agent_name
    }


def create_agent_pool(count=10):
    """Create multiple agents for the pool"""
    
    print("="*60)
    print(f"CREATING {count} BADBOT AGENTS")
    print("="*60)
    
    agents = []
    for i in range(1, count + 1):
        print(f"\nCreating agent {i}/{count}...")
        result = create_agent_without_transfer(f"BadBot Agent #{i}")
        
        if result:
            agents.append(result)
            print(f"  Created: {result['agent_id']}")
        else:
            print(f"  Failed")
    
    print(f"\n{len(agents)} agents created!")
    
    # Save to file
    with open('agent_pool.txt', 'w') as f:
        f.write("AGENTS TO CONFIGURE\n")
        f.write("="*60 + "\n\n")
        f.write("For each agent:\n")
        f.write("1. Go to: https://app.retellai.com\n")
        f.write("2. Find agent by name\n")
        f.write("3. Add Transfer Call tool\n")
        f.write("4. Leave number blank (will be dynamic per client)\n")
        f.write("5. Save\n\n")
        f.write("="*60 + "\n\n")
        
        for agent in agents:
            f.write(f"Name: {agent['agent_name']}\n")
            f.write(f"ID: {agent['agent_id']}\n")
            f.write(f"LLM: {agent['llm_id']}\n\n")
    
    print("\nSaved to: agent_pool.txt")
    print("\nNext: Manually configure each agent in Retell Dashboard")
    
    return agents


if __name__ == "__main__":
    agents = create_agent_pool(10)
    print(f"\nDone! Created {len(agents)} agents")

