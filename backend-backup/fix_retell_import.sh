#!/usr/bin/env bash
set -euo pipefail

export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

echo "Deleting number..."
curl -s -X DELETE "https://api.retellai.com/delete-phone-number/+18135478218" \
  -H "Authorization: Bearer $RETELL_API_KEY"

echo ""
echo "Waiting 3 seconds..."
sleep 3

echo "Re-importing with credentials..."
curl -s -X POST "https://api.retellai.com/import-phone-number" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+18135478218",
    "termination_uri": "sip.telnyx.com",
    "sip_trunk_auth": {
      "username": "retell1761517139394aba3b",
      "password": "qHhi996QUXr7wJnFQWh6Tp1Arr1GZW"
    },
    "inbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91",
    "outbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91"
  }' | python -m json.tool

echo ""
echo "Verifying import..."
sleep 2
curl -s "https://api.retellai.com/list-phone-numbers" \
  -H "Authorization: Bearer $RETELL_API_KEY" | python -c "
import sys, json
numbers = json.load(sys.stdin)
for num in numbers:
    if num['phone_number'] == '+18135478218':
        print('Phone:', num['phone_number'])
        print('Agent:', num.get('inbound_agent_id'))
        print('Username:', num.get('sip_outbound_trunk_config', {}).get('auth_username'))
        if num.get('sip_outbound_trunk_config', {}).get('auth_username'):
            print('✓ Credentials saved!')
        else:
            print('✗ Credentials NOT saved - Retell API issue')
"
