import os
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"
AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"

print("="*60)
print("FIXING RETELL AGENT TRANSFER")
print("="*60)

# Get current agent
print("\n1. Getting agent configuration...")
response = requests.get(
    f"{RETELL_BASE}/get-agent/{AGENT_ID}",
    headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
)

agent = response.json()
print(f"✓ Agent: {agent.get('agent_name')}")
print(f"✓ Response Engine: {agent.get('response_engine', {}).get('type')}")

# Update agent with proper transfer configuration
print("\n2. Updating agent with transfer tool...")

# Simple prompt that forces tool usage
agent_update = {
    "agent_name": "BadBot - Smart Transfer",
    "voice_id": "11labs-Adrian",
    "response_engine": {
        "type": "retell-llm",
        "llm_id": None  # Use built-in
    },
    "general_prompt": """Screen calls briefly.

Ask: "Who's calling?"

TRANSFER immediately if:
- Doctor, pharmacy, hospital
- Family member by name
- Expected business

HANG UP if:
- IRS, police, government threats
- Tech support, virus warnings
- Gift cards, wire transfers
- Won't identify themselves

Use the tools - transfer_to_client or end_call.""",
    "general_tools": [
        {
            "type": "end_call",
            "name": "end_call",
            "description": "Hang up on scam calls"
        },
        {
            "type": "transfer_call", 
            "name": "transfer_to_client",
            "description": "Transfer legitimate calls",
            "number": "+17543670370"
        }
    ],
    "begin_message": None,
    "language": "en-US",
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
    print("✓ Agent updated successfully!")
    print("\n" + "="*60)
    print("TEST THE TRANSFER:")
    print("="*60)
    print("\n1. Call: +18135478530")
    print("2. BadBot: 'Who's calling?'")
    print("3. You say: 'Dr. Smith's office'")
    print("4. BadBot should transfer to: +17543670370")
    print("\nOR")
    print("\n1. Call: +18135478530")
    print("2. BadBot: 'Who's calling?'")
    print("3. You say: 'This is Sarah, his daughter'")
    print("4. BadBot should transfer immediately")
    print("="*60)
else:
    print(f"✗ Error: {response.status_code}")
    print(response.text)
