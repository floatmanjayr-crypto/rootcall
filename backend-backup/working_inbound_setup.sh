. "$(dirname "$0")/env.require.sh" TELNYX_API_KEY
#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"

echo "Creating FQDN Connection (correct format)..."

# Using exact LiveKit/Telnyx working example
curl -X POST 'https://api.telnyx.com/v2/fqdn_connections' \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "connection_name": "Retell AI Trunk",
    "transport_protocol": "TCP",
    "inbound": {
      "sip_region": "US"
    },
    "outbound": {
      "outbound_voice_profile_id": "2812737864519911048"
    }
  }' > /tmp/create_result.json

cat /tmp/create_result.json | python -m json.tool

CONNECTION_ID=$(cat /tmp/create_result.json | python -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)

if [ ! -z "$CONNECTION_ID" ]; then
  echo ""
  echo "‚úÖ Connection created: $CONNECTION_ID"
  
  # Add FQDN
  echo "Adding sip.retellai.com..."
  curl -X POST "https://api.telnyx.com/v2/fqdns" \
    -H "Authorization: Bearer $TELNYX_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"connection_id\": \"$CONNECTION_ID\", \"fqdn\": \"sip.retellai.com\", \"dns_record_type\": \"srv\"}" | python -m json.tool
  
  # Assign number
  echo ""
  echo "Assigning phone number..."
  curl -X PATCH "https://api.telnyx.com/v2/phone_numbers/2691045353678963984" \
    -H "Authorization: Bearer $TELNYX_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"connection_id\": \"$CONNECTION_ID\"}" | python -m json.tool
  
  echo ""
  echo "Ìæâ Inbound calling configured!"
  echo "Test now: Call +18135478530"
else
  echo "‚ùå Failed to create connection"
  cat /tmp/create_result.json
fi
