#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
CONNECTION_ID="2812968115544000352"

echo "Adding SIP credentials for Retell..."

# Generate credentials
USERNAME="retell_$(date +%s)"
PASSWORD=$(openssl rand -base64 16 | tr -d '=+/')

echo "Username: $USERNAME"
echo "Password: $PASSWORD"

# Set credentials on the FQDN connection
curl -X PATCH "https://api.telnyx.com/v2/fqdn_connections/$CONNECTION_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_name\": \"$USERNAME\",
    \"password\": \"$PASSWORD\"
  }" | python -m json.tool

echo ""
echo "âœ… Credentials added!"
echo ""
echo "Now update Retell with these credentials..."
echo ""

# Update Retell with the credentials
curl -X PATCH "https://api.retellai.com/update-phone-number/+18135478530" \
  -H "Authorization: Bearer key_d85a3f8b8ac5f3a37c4c15e3e31a" \
  -H "Content-Type: application/json" \
  -d "{
    \"inbound_agent_id\": \"agent_cde1ba4c8efa2aba5665a77b91\",
    \"sip_trunk_auth\": {
      \"username\": \"$USERNAME\",
      \"password\": \"$PASSWORD\"
    }
  }" | python -m json.tool

echo ""
echo "í¾‰ Setup complete! Wait 30 seconds then call +18135478530"
