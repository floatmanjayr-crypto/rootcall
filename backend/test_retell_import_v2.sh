#!/usr/bin/env bash
set -euo pipefail

export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

echo "Testing Retell import with explicit transport..."

# Delete first
curl -s -X DELETE "https://api.retellai.com/delete-phone-number/+18135478218" \
  -H "Authorization: Bearer $RETELL_API_KEY"

sleep 3

# Try with explicit transport parameter
curl -v -X POST "https://api.retellai.com/import-phone-number" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+18135478218",
    "termination_uri": "sip.telnyx.com",
    "transport": "TCP",
    "sip_trunk_auth": {
      "username": "retell1761517139394aba3b",
      "password": "qHhi996QUXr7wJnFQWh6Tp1Arr1GZW"
    },
    "inbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91",
    "outbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91"
  }' 2>&1 | tee /tmp/retell_import_debug.log

echo ""
echo "Response saved to /tmp/retell_import_debug.log"
echo ""

# Verify
sleep 2
curl -s "https://api.retellai.com/get-phone-number/+18135478218" \
  -H "Authorization: Bearer $RETELL_API_KEY" | python -m json.tool

