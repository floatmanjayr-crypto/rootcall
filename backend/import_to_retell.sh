#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .retell_sip_credentials ]; then
    echo "Error: .retell_sip_credentials not found"
    echo "Please run ./create_retell_sip_trunk.sh first"
    exit 1
fi

source .retell_sip_credentials

export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

echo "============================================"
echo "IMPORTING +18135478218 TO RETELL"
echo "============================================"
echo ""
echo "Using credentials:"
echo "  Phone: $PHONE_NUMBER"
echo "  SIP User: $SIP_USERNAME"
echo "  Termination: sip.telnyx.com"
echo ""

IMPORT_RESPONSE=$(curl -s -X POST "https://api.retellai.com/import-phone-number" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"$PHONE_NUMBER\",
    \"termination_uri\": \"sip.telnyx.com\",
    \"sip_trunk_auth\": {
      \"username\": \"$SIP_USERNAME\",
      \"password\": \"$SIP_PASSWORD\"
    },
    \"inbound_agent_id\": \"agent_cde1ba4c8efa2aba5665a77b91\",
    \"outbound_agent_id\": \"agent_cde1ba4c8efa2aba5665a77b91\",
    \"nickname\": \"BadBot Line - Primary Client\"
  }")

echo "$IMPORT_RESPONSE" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'phone_number' in data:
        print('[SUCCESS] Number imported to Retell')
        print('  Phone:', data['phone_number'])
        print('  Agent:', data.get('inbound_agent_id', 'N/A'))
        print('')
        print('Call flow is now active:')
        print('  Incoming call -> Telnyx +18135478218')
        print('  -> SIP Trunk -> sip.retellai.com')
        print('  -> Retell Agent answers with BadBot')
    else:
        print('[ERROR] Import failed')
        print(json.dumps(data, indent=2))
except Exception as e:
    print('[ERROR]', str(e))
    print('Raw response:', sys.stdin.read())
"

echo ""
echo "============================================"
echo "TEST THE SETUP"
echo "============================================"
echo ""
echo "Call: +18135478218"
echo ""
echo "Expected: BadBot answers and says:"
echo "  'Hello, this is Primary Senior Client's assistant."
echo "   Who's calling please?'"
echo ""
echo "Test fraud detection by saying:"
echo "  'This is the IRS, you owe taxes'"
echo ""
echo "BadBot should hang up immediately!"
echo ""
