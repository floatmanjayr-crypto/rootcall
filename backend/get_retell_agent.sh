#!/bin/bash

# Helper script to find Retell agent ID for a number

if [ -z "$RETELL_API_KEY" ]; then
    echo "Error: RETELL_API_KEY not set"
    echo "Run: export RETELL_API_KEY='your_key_here'"
    exit 1
fi

echo "Searching for phone number: +18135551234"
echo ""

# List all phone numbers
curl -s "https://api.retellai.com/v2/list-phone-numbers" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  | python -c "
import sys, json
data = json.load(sys.stdin)
for num in data:
    if '8135551234' in num.get('phone_number', ''):
        print(f\"✅ Found: {num['phone_number']}\")
        print(f\"   Agent ID: {num.get('agent_id', 'N/A')}\")
        print(f\"   Inbound Agent: {num.get('inbound_agent_id', 'N/A')}\")
        print(f\"   Outbound Agent: {num.get('outbound_agent_id', 'N/A')}\")
        break
else:
    print('❌ Number not found in Retell')
    print('Listing all agents:')
    print('')
"

# Also list all agents
echo ""
echo "All Retell agents:"
curl -s "https://api.retellai.com/v2/list-agents" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  | python -c "
import sys, json
data = json.load(sys.stdin)
for agent in data:
    print(f\"  • {agent.get('agent_name', 'N/A')} → agent_id: {agent.get('agent_id', 'N/A')}\")
"
