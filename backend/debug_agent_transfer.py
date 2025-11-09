import os
import requests
import json

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"
AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"

print("="*60)
print("DEBUGGING AGENT TRANSFER")
print("="*60)

# Step 1: Check current agent config
print("\n1. Getting current agent configuration...")
response = requests.get(
    f"{RETELL_BASE}/get-agent/{AGENT_ID}",
    headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
)

if response.status_code == 200:
    agent = response.json()
    print(f"✓ Agent Name: {agent.get('agent_name')}")
    print(f"✓ Voice: {agent.get('voice_id')}")
    print(f"✓ LLM URL: {agent.get('llm_websocket_url')}")
    
    # Check if using custom LLM or agent config
    response_engine = agent.get('response_engine', {})
    print(f"✓ Response Engine Type: {response_engine.get('type')}")
    
    llm_url = agent.get("llm_websocket_url", "")
    if "llm-websocket/" in llm_url:
        llm_id = llm_url.split("llm-websocket/")[-1]
        print(f"✓ LLM ID: {llm_id}")
    else:
        print("✗ No LLM ID found")
        llm_id = None
else:
    print(f"✗ Error getting agent: {response.text}")
    exit(1)

# Step 2: Check if agent has the transfer tool
print("\n2. Checking agent tools...")

# For custom LLM, check the LLM config
if llm_id:
    response = requests.get(
        f"{RETELL_BASE}/get-retell-llm/{llm_id}",
        headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
    )
    
    if response.status_code == 200:
        llm = response.json()
        tools = llm.get('general_tools', [])
        print(f"✓ LLM has {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.get('type')}: {tool.get('name')}")
            if tool.get('type') == 'transfer_call':
                print(f"    → Transfer to: {tool.get('number')}")
    else:
        print(f"✗ Error getting LLM: {response.text}")

# Step 3: Create a NEW simpler prompt that FORCES transfer
print("\n3. Creating EXPLICIT transfer prompt...")

FORCE_TRANSFER_PROMPT = """You screen calls briefly.

Ask: "Who's calling?"

If they say doctor, pharmacy, family name, or business:
YOU MUST immediately use the transfer_to_client tool. This is required.

If they say IRS, police, tech support, or refuse to identify:
Use end_call tool.

Always use the tools. Never just talk - use the tools."""

if llm_id:
    update = {
        "general_prompt": FORCE_TRANSFER_PROMPT,
        "general_tools": [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End this call immediately"
            },
            {
                "type": "transfer_call",
                "name": "transfer_to_client",
                "description": "YOU MUST USE THIS to transfer legitimate calls",
                "number": "+17543670370"
            }
        ],
        "model": "gpt-4o",
        "temperature": 0.1
    }
    
    response = requests.patch(
        f"{RETELL_BASE}/update-retell-llm/{llm_id}",
        headers={"Authorization": f"Bearer {RETELL_API_KEY}"},
        json=update
    )
    
    if response.status_code == 200:
        print("✓ LLM updated with explicit transfer instructions")
    else:
        print(f"✗ Error: {response.text}")

# Step 4: Test by making a call
print("\n4. Making test call to verify transfer...")
print("   This will call James's number directly to test")

test_call = {
    "from_number": "+18135478530",
    "to_number": "+17543670370",
    "override_agent_id": AGENT_ID
}

response = requests.post(
    f"{RETELL_BASE}/create-phone-call",
    headers={"Authorization": f"Bearer {RETELL_API_KEY}"},
    json=test_call
)

if response.status_code in [200, 201]:
    call_data = response.json()
    print(f"✓ Test call created: {call_data.get('call_id')}")
    print(f"  Status: {call_data.get('call_status')}")
    print("\n  James's phone should ring now!")
else:
    print(f"✗ Error creating test call: {response.text}")

print("\n" + "="*60)
print("NEXT STEPS:")
print("="*60)
print("1. Wait for James's phone to ring from test call")
print("2. If it rings: Transfer works!")
print("3. If not: Check Retell dashboard for errors")
print("4. Then try calling +18135478530 and say 'doctor's office'")
print("="*60)
