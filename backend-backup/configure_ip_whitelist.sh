#!/usr/bin/env bash
set -euo pipefail

: "${TELNYX_API_KEY:?set TELNYX_API_KEY}"

echo "============================================"
echo "SWITCHING TO IP-BASED AUTHENTICATION"
echo "============================================"
echo ""
echo "This will allow Retell to connect without credentials"
echo "based on their IP addresses."
echo ""

# Update trunk to IP authentication
curl -s -X PATCH "https://api.telnyx.com/v2/fqdn_connections/2814978110787684283" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "outbound": {
      "fqdn_authentication_method": "ip-authentication"
    }
  }' | python -c "import sys, json; d=json.load(sys.stdin)['data']; print('✓ Trunk updated to IP authentication'); print('  Method:', d['outbound']['fqdn_authentication_method'])"

echo ""
echo "============================================"
echo "TRUNK NOW USES IP AUTHENTICATION"
echo "============================================"
echo ""
echo "Retell will connect using their IP addresses"
echo "No username/password needed"
echo ""
echo "Wait 30 seconds then test: +18135478218"
echo "============================================"
