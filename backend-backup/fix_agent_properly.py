import os
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"
AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"

print("Fixing agent transfer...")

# Get current agent to find LLM ID
response = requests.get(
    f"{RETELL_BASE}/get-agent/{AGENT_ID}",
    headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
)

agent = response.json()
print(f"Agent: {agent.get('agent_name')}")

# Get the response engine config
response_engine = agent.get('response_engine', {})
llm_id = response_engine.get('llm_id')

if llm_id:
    print(f"Found LLM ID: {llm_id}")
    
    # Update just the tools in the LLM
    llm_update = {
        "general_tools": [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End call for scams"
            },
            {
                "type": "transfer_call",
                "name": "transfer_to_client",
                "description": "Transfer legitimate calls",
                "number": "+17543670370"
            }
        ],
        "general_prompt": """Brief call screener.

Ask: "Who's calling?"

If doctor/pharmacy/family: Use transfer_to_client tool immediately.
If IRS/scam: Use end_call tool.

Always use the tools."""
    }
    
    response = requests.patch(
        f"{RETELL_BASE}/update-retell-llm/{llm_id}",
        headers={"Authorization": f"Bearer {RETELL_API_KEY}"},
        json=llm_update
    )
    
    if response.status_code == 200:
        print("✓ Transfer tool configured!")
        print("\nTest: Call +18135478530")
        print("Say: 'Dr Smith's office'")
        print("Should transfer to: +17543670370")
    else:
        print(f"Error: {response.text}")
else:
    print("No LLM ID - need to create one")
    print("\nLet me check the response engine config:")
    print(response_engine)
