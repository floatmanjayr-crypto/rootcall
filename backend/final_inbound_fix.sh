. "$(dirname "$0")/env.require.sh" TELNYX_API_KEY
#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"

echo "Creating FQDN Connection..."

# Correct format from LiveKit/Telnyx docs
curl -X POST "https://api.telnyx.com/v2/fqdn_connections" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_name": "Retell AI Trunk",
    "transport_protocol": "TCP",
    "inbound": {
      "ani_number_format": "e164",
      "dnis_number_format": "e164",
      "codecs": ["G722", "G711U", "G711A"],
      "sip_region": "US"
    },
    "outbound": {
      "outbound_voice_profile_id": "2700292199316194319"
    }
  }' > /tmp/fqdn_response.json

cat /tmp/fqdn_response.json | python -m json.tool

CONNECTION_ID=$(cat /tmp/fqdn_response.json | python -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)

if [ ! -z "$CONNECTION_ID" ]; then
  echo ""
  echo "âœ… Connection: $CONNECTION_ID"
  
  # Add FQDN
  curl -X POST "https://api.telnyx.com/v2/fqdns" \
    -H "Authorization: Bearer $TELNYX_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"connection_id\": \"$CONNECTION_ID\", \"fqdn\": \"sip.retellai.com\", \"dns_record_type\": \"srv\"}"
  
  echo ""
  
  # Assign number
  curl -X PATCH "https://api.telnyx.com/v2/phone_numbers/2691045353678963984" \
    -H "Authorization: Bearer $TELNYX_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"connection_id\": \"$CONNECTION_ID\"}"
  
  echo ""
  echo "í¾‰ Done! Call +18135478530 to test"
fi
