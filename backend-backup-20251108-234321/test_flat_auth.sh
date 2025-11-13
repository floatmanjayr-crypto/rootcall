#!/usr/bin/env bash
set -euo pipefail

export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

# Delete
curl -s -X DELETE "https://api.retellai.com/delete-phone-number/+18135478218" \
  -H "Authorization: Bearer $RETELL_API_KEY"

sleep 2

# Try with flat structure (username/password at top level)
curl -s -X POST "https://api.retellai.com/import-phone-number" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+18135478218",
    "termination_uri": "sip.telnyx.com",
    "transport": "TCP",
    "username": "retell1761517139394aba3b",
    "password": "qHhi996QUXr7wJnFQWh6Tp1Arr1GZW",
    "inbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91",
    "outbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91"
  }' | python -m json.tool

sleep 2

# Verify
curl -s "https://api.retellai.com/get-phone-number/+18135478218" \
  -H "Authorization: Bearer $RETELL_API_KEY" | python -c "
import sys, json
d = json.load(sys.stdin)
print('Auth Username:', d.get('sip_outbound_trunk_config', {}).get('auth_username', 'EMPTY'))
if d.get('sip_outbound_trunk_config', {}).get('auth_username'):
    print('✓ SUCCESS - Credentials saved!')
else:
    print('✗ FAILED - Still empty')
"
