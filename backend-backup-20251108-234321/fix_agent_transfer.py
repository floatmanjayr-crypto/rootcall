import os
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"
AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"

# Updated prompt - asks for callback, transfers properly
SCREENING_PROMPT = """You are BadBot. Screen calls with SHORT questions.

STEP 1 - GREETING: "Hello, who's calling?"

STEP 2 - GET CALLBACK: "What's your callback number?"

STEP 3 - PURPOSE: "What's this about?"

SCAM RED FLAGS (say "I can't help with that. Goodbye" and END CALL):
- Won't give callback number
- IRS, police, arrest
- Gift cards, wires
- Tech support
- SSN/password requests
- Prize with fees

LEGITIMATE (say "One moment" and TRANSFER CALL):
- Gives valid callback number
- Doctor, pharmacy, hospital
- Family member by name
- Expected business

Keep responses under 8 words. Ask questions one at a time.

CRITICAL: After determining legitimate, you MUST use the transfer_to_client tool."""

print(f"Updating agent {AGENT_ID}...")

# Get current agent
response = requests.get(
    f"{RETELL_BASE}/get-agent/{AGENT_ID}",
    headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
)

if response.status_code != 200:
    print(f"Error: {response.text}")
    exit(1)

agent = response.json()

# Get LLM websocket URL to extract LLM ID
llm_url = agent.get("llm_websocket_url", "")
if "llm-websocket/" in llm_url:
    llm_id = llm_url.split("llm-websocket/")[-1]
    print(f"Found LLM ID: {llm_id}")
    
    # Update LLM with new prompt
    llm_update = {
        "general_prompt": SCREENING_PROMPT,
        "general_tools": [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "Hang up on scam calls"
            },
            {
                "type": "transfer_call",
                "name": "transfer_to_client",
                "description": "Transfer legitimate callers after screening",
                "number": "+17543670370"
            }
        ],
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 150
    }
    
    response = requests.patch(
        f"{RETELL_BASE}/update-retell-llm/{llm_id}",
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        },
        json=llm_update
    )
    
    if response.status_code == 200:
        print("‚úÖ Agent updated successfully!")
        print("\nNew behavior:")
        print("1. Asks: 'Who's calling?'")
        print("2. Asks: 'What's your callback number?'")
        print("3. Asks: 'What's this about?'")
        print("4. Screens based on answers")
        print("5. Transfers legitimate calls")
        print("6. Hangs up on scams")
        print("\nÌ∑™ Test scenarios:")
        print("\nLEGITIMATE:")
        print("  BadBot: 'Hello, who's calling?'")
        print("  You: 'Dr. Smith's office'")
        print("  BadBot: 'What's your callback number?'")
        print("  You: '954-555-1234'")
        print("  BadBot: 'One moment' [TRANSFERS]")
        print("\nSCAM:")
        print("  BadBot: 'Hello, who's calling?'")
        print("  You: 'IRS department'")
        print("  BadBot: 'I can't help with that. Goodbye' [HANGS UP]")
    else:
        print(f"‚ùå Error updating: {response.text}")
else:
    print("‚ùå Could not find LLM ID in agent config")
