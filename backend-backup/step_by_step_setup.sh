#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"

echo "Step 1: Create basic FQDN connection..."

curl -X POST 'https://api.telnyx.com/v2/fqdn_connections' \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "connection_name": "Retell Inbound Trunk",
    "transport_protocol": "TCP"
  }' > /tmp/conn.json

cat /tmp/conn.json | python -m json.tool

CONNECTION_ID=$(cat /tmp/conn.json | python -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)

if [ -z "$CONNECTION_ID" ]; then
  echo "‚ùå Failed"
  exit 1
fi

echo ""
echo "‚úÖ Connection: $CONNECTION_ID"

echo ""
echo "Step 2: Add FQDN sip.retellai.com..."
curl -X POST "https://api.telnyx.com/v2/fqdns" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\": \"$CONNECTION_ID\", \"fqdn\": \"sip.retellai.com\", \"dns_record_type\": \"srv\"}" | python -m json.tool

echo ""
echo "Step 3: Update connection with outbound profile..."
curl -X PATCH "https://api.telnyx.com/v2/fqdn_connections/$CONNECTION_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "outbound": {
      "outbound_voice_profile_id": "2812737864519911048"
    },
    "inbound": {
      "sip_region": "US"
    }
  }' | python -m json.tool

echo ""
echo "Step 4: Assign phone number..."
curl -X PATCH "https://api.telnyx.com/v2/phone_numbers/2691045353678963984" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\": \"$CONNECTION_ID\"}" | python -m json.tool

echo ""
echo "Ìæâ Done! Call +18135478530 to test inbound"
