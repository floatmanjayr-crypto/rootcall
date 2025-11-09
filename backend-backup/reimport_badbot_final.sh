#!/usr/bin/env bash
set -euo pipefail

export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

echo "============================================"
echo "RE-IMPORTING +18135478218 TO RETELL"
echo "============================================"
echo ""

# Step 1: Delete from Retell
echo "Step 1: Deleting old import..."
curl -s -X DELETE "https://api.retellai.com/delete-phone-number/+18135478218" \
  -H "Authorization: Bearer $RETELL_API_KEY" 

echo ""
sleep 2

# Step 2: Re-import with correct trunk
echo "Step 2: Re-importing with BadBot agent..."
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
    "outbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91",
    "nickname": "BadBot Primary Line"
  }' | python -m json.tool

echo ""
echo "============================================"
echo "DONE - TEST BY CALLING +18135478218"
echo "============================================"
