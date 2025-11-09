#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
RETELL_API_KEY="key_d85a3f8b8ac5f3a37c4c15e3e31a"

echo "Creating FQDN Connection for Retell..."

# Create FQDN connection with correct format
RESPONSE=$(curl -s -X POST "https://api.telnyx.com/v2/fqdn_connections" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_name": "Retell AI SIP Trunk",
    "active": true,
    "transport_protocol": "TCP",
    "inbound": {
      "ani_number_format": "+e164",
      "dnis_number_format": "+e164",
      "codecs": ["G722", "PCMU", "PCMA"],
      "default_routing_method": "sequential",
      "channel_limit": 10,
      "generate_ringback_tone": true,
      "sip_region": "US"
    },
    "outbound": {
      "channel_limit": 10,
      "localization": "US",
      "outbound_voice_profile_id": "2700292199316194319"
    }
  }')

echo "$RESPONSE" | python -m json.tool

# Extract connection ID
CONNECTION_ID=$(echo "$RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)

if [ -z "$CONNECTION_ID" ]; then
  echo "‚ùå Failed to create connection"
  exit 1
fi

echo ""
echo "‚úÖ Connection created: $CONNECTION_ID"

# Add Retell FQDN
echo "Adding sip.retellai.com..."
curl -s -X POST "https://api.telnyx.com/v2/fqdns" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_id\": \"$CONNECTION_ID\",
    \"fqdn\": \"sip.retellai.com\",
    \"dns_record_type\": \"srv\"
  }" | python -m json.tool

# Assign phone number
echo ""
echo "Assigning +18135478530..."
curl -s -X PATCH "https://api.telnyx.com/v2/phone_numbers/2691045353678963984" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\": \"$CONNECTION_ID\"}" | python -m json.tool

echo ""
echo "Ìæâ Inbound calling configured!"
echo "Test: Call +18135478530"
