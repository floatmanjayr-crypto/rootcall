. "$(dirname "$0")/env.require.sh" TELNYX_API_KEY
#!/bin/bash

# Automated Telnyx + Retell Inbound Setup
TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
RETELL_API_KEY="key_d85a3f8b8ac5f3a37c4c15e3e31a"

# Step 1: Create FQDN Connection
echo "Creating FQDN connection..."
FQDN_RESPONSE=$(curl -s -X POST "https://api.telnyx.com/v2/fqdn_connections" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_name": "Retell AI Inbound",
    "active": true,
    "anchorsite_override": "Latency",
    "transport_protocol": "TCP",
    "inbound": {
      "ani_number_format": "+E.164",
      "dnis_number_format": "+E.164",
      "codecs": ["G722", "PCMU", "PCMA"],
      "default_routing_method": "sequential",
      "channel_limit": 10,
      "sip_region": "US"
    }
  }')

CONNECTION_ID=$(echo $FQDN_RESPONSE | python -m json.tool | grep '"id"' | head -1 | cut -d'"' -f4)
echo "âœ… FQDN Connection created: $CONNECTION_ID"

# Step 2: Add Retell FQDN
echo "Adding Retell FQDN..."
curl -s -X POST "https://api.telnyx.com/security/fqdns" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_id\": \"$CONNECTION_ID\",
    \"fqdn\": \"sip.retellai.com\",
    \"dns_record_type\": \"srv\"
  }"

echo "âœ… Retell FQDN added"

# Step 3: Configure outbound auth
echo "Configuring outbound authentication..."
USERNAME="retell_$(date +%s)"
PASSWORD=$(openssl rand -base64 16)

curl -s -X POST "https://api.telnyx.com/security/connections/$CONNECTION_ID/fqdn_authentication" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_name\": \"$USERNAME\",
    \"password\": \"$PASSWORD\",
    \"fqdn_outbound_authentication\": \"credential-authentication\"
  }"

echo "âœ… Credentials: $USERNAME / $PASSWORD"

# Step 4: Assign phone number to new connection
echo "Assigning phone number..."
curl -s -X PATCH "https://api.telnyx.com/v2/phone_numbers/2691045353678963984" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\": \"$CONNECTION_ID\"}"

echo "âœ… Phone number assigned"

# Step 5: Import to Retell
echo "Importing to Retell..."
curl -s -X POST "https://api.retellai.com/import-phone-number" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"+18135478530\",
    \"inbound_agent_id\": \"agent_cde1ba4c8efa2aba5665a77b91\",
    \"termination_uri\": \"sip.telnyx.com\",
    \"telephony_provider\": \"telnyx\",
    \"sip_trunk_auth\": {
      \"username\": \"$USERNAME\",
      \"password\": \"$PASSWORD\"
    }
  }"

echo ""
echo "í¾‰ Setup complete! Inbound calling is now enabled."
echo "Test by calling: +18135478530"
