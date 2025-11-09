import os
import requests

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_BASE = "https://api.retellai.com"
AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"

# Simple, smart prompt
SMART_PROMPT = """You are a call screener. Be brief.

GREETING: "Who's calling?"

IF OBVIOUS LEGITIMATE (transfer immediately):
- Doctor, pharmacy, hospital by name
- "I'm [name], his son/daughter/wife"
- Expected business ("Amazon delivery", "plumber")
Response: "One moment" → TRANSFER

IF HIGH RISK (ask callback number):
- Government (IRS, police, Medicare)
- Prize/sweepstakes
- Tech support
- Urgent payment requests
- Won't say name clearly
Ask: "Callback number?" 
If refuses or fake → "Can't help. Goodbye" → END CALL
If gives real number → "What's this about?"
Then decide: transfer or hang up

IF UNSURE (ask one question):
"What's this regarding?"
Then decide based on answer.

ALWAYS SCAM (hang up immediately):
- IRS/police threats
- Gift card payments
- "Your computer has virus"
- "You owe money, pay now"
- SSN/password requests
Response: "Can't help" → END CALL

Be direct. Max 5 words per response.

CRITICAL: When you decide to transfer, you MUST call the transfer_to_client function."""

print(f"Updating agent {AGENT_ID} with smart screening...")

# Get agent
response = requests.get(
    f"{RETELL_BASE}/get-agent/{AGENT_ID}",
    headers={"Authorization": f"Bearer {RETELL_API_KEY}"}
)

agent = response.json()
llm_url = agent.get("llm_websocket_url", "")

if "llm-websocket/" in llm_url:
    llm_id = llm_url.split("llm-websocket/")[-1]
    
    # Update LLM
    update = {
        "general_prompt": SMART_PROMPT,
        "general_tools": [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End the call for scams"
            },
            {
                "type": "transfer_call",
                "name": "transfer_to_client",
                "description": "Transfer legitimate calls to client",
                "number": "+17543670370"
            }
        ],
        "model": "gpt-4o",  # Using gpt-4o for better tool usage
        "temperature": 0.2,
        "max_tokens": 100
    }
    
    response = requests.patch(
        f"{RETELL_BASE}/update-retell-llm/{llm_id}",
        headers={"Authorization": f"Bearer {RETELL_API_KEY}"},
        json=update
    )
    
    if response.status_code == 200:
        print("✅ Smart agent updated!")
        print("\n��� Test Scenarios:\n")
        print("SCENARIO 1 - Obvious legitimate (quick transfer):")
        print("  BadBot: 'Who's calling?'")
        print("  You: 'Dr. Smith's office'")
        print("  BadBot: 'One moment' [TRANSFERS]\n")
        
        print("SCENARIO 2 - Family (quick transfer):")
        print("  BadBot: 'Who's calling?'")
        print("  You: 'I'm Sarah, his daughter'")
        print("  BadBot: 'One moment' [TRANSFERS]\n")
        
        print("SCENARIO 3 - High risk (asks callback):")
        print("  BadBot: 'Who's calling?'")
        print("  You: 'Medicare department'")
        print("  BadBot: 'Callback number?'")
        print("  You: 'Uh, I'll call back' [refuses]")
        print("  BadBot: 'Can't help' [HANGS UP]\n")
        
        print("SCENARIO 4 - Obvious scam (instant hang up):")
        print("  BadBot: 'Who's calling?'")
        print("  You: 'IRS, you owe taxes'")
        print("  BadBot: 'Can't help' [HANGS UP]\n")
    else:
        print(f"Error: {response.text}")
else:
    print("Could not find LLM ID")
