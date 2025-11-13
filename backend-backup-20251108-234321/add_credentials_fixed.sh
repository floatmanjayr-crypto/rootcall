. "$(dirname "$0")/env.require.sh" TELNYX_API_KEY
#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
CONNECTION_ID="2812968115544000352"

echo "Adding SIP credentials..."

# Generate alphanumeric only credentials
USERNAME="retell$(date +%s)"
PASSWORD=$(openssl rand -base64 16 | tr -d '=+/-_')

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
echo "✅ Done! Call +18135478530 now"
