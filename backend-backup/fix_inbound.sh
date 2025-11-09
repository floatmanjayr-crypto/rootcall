. "$(dirname "$0")/env.require.sh" TELNYX_API_KEY
#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
RETELL_API_KEY="key_d85a3f8b8ac5f3a37c4c15e3e31a"
EXISTING_CONNECTION="2700292207562195984"

echo "Step 1: Add Retell FQDN to existing connection..."
FQDN_ADD=$(curl -s -X POST "https://api.telnyx.com/v2/fqdns" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_id\": \"$EXISTING_CONNECTION\",
    \"fqdn\": \"sip.retellai.com\",
    \"dns_record_type\": \"srv\"
  }")

echo $FQDN_ADD | python -m json.tool

echo ""
echo "Step 2: Reassign phone number to connection..."
curl -s -X PATCH "https://api.telnyx.com/v2/phone_numbers/2691045353678963984" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\": \"$EXISTING_CONNECTION\"}" | python -m json.tool

echo ""
echo "Step 3: Update Retell number configuration..."
curl -s -X PATCH "https://api.retellai.com/update-phone-number/+18135478530" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inbound_agent_id": "agent_cde1ba4c8efa2aba5665a77b91"
  }' | python -m json.tool

echo ""
echo "✅ Done! Test inbound by calling: +18135478530"
