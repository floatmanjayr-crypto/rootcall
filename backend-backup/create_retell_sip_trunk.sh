#!/usr/bin/env bash
set -euo pipefail

export TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
export PHONE_NUMBER="+18135478218"

echo "============================================"
echo "CREATING RETELL ELASTIC SIP TRUNK"
echo "============================================"
echo ""

# Step 1: Create Elastic SIP Trunk with correct Retell settings
echo "Step 1: Creating Elastic SIP Trunk for Retell..."

CREATE_TRUNK=$(curl -s -X POST "https://api.telnyx.com/v2/credential_connections" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_name": "Retell AI SIP Trunk",
    "transport_protocol": "TCP",
    "default_on_hold_comfort_noise_enabled": false,
    "dtmf_type": "RFC 2833",
    "encode_contact_header_enabled": false,
    "encrypted_media": "SRTP",
    "inbound": {
      "ani_override": null,
      "ani_override_type": "always",
      "dnis_override": null,
      "dnis_override_type": "always",
      "codecs": ["G722", "G729", "OPUS"],
      "default_routing_method": "sequential",
      "channel_limit": null,
      "generate_ringback_tone": true,
      "isup_headers_enabled": false,
      "prack_enabled": false,
      "privacy_zone_enabled": false,
      "sip_compact_headers_enabled": false,
      "sip_region": "ashburn-va",
      "sip_subdomain": null,
      "sip_subdomain_receive_settings": "only_my_connections",
      "timeout_1xx_secs": 3,
      "timeout_2xx_secs": 90,
      "shaken_stir_enabled": false,
      "inbound_number_format": "+E.164"
    },
    "outbound": {
      "ani_override": null,
      "ani_override_type": "always",
      "call_parking_enabled": false,
      "channel_limit": null,
      "generate_ringback_tone": true,
      "instant_ringback_enabled": false,
      "ip_authentication_method": "credential",
      "ip_authentication_token": null,
      "localization": null,
      "outbound_voice_profile_id": null,
      "t38_reinvite_source": "customer"
    },
    "rtcp_settings": {
      "port": "rtp+1",
      "capture_enabled": false,
      "report_enabled": true,
      "report_frequency_secs": 5
    }
  }')

echo "$CREATE_TRUNK" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'data' in data:
        print('[OK] Created SIP Trunk:', data['data']['id'])
        print('     Name:', data['data']['connection_name'])
        print(data['data']['id'])
    else:
        print('[ERROR]', json.dumps(data))
        print('')
except Exception as e:
    print('[ERROR]', str(e))
    print('')
" > /tmp/trunk_result.txt

TRUNK_ID=$(tail -1 /tmp/trunk_result.txt)
cat /tmp/trunk_result.txt | head -n -1

if [ -z "$TRUNK_ID" ] || [[ "$TRUNK_ID" == "["* ]]; then
    echo "Failed to create trunk. Full response:"
    echo "$CREATE_TRUNK"
    exit 1
fi

echo ""
echo "Step 2: Creating SIP credentials for Retell..."

# Generate random username and password
SIP_USER="retell_$(date +%s)"
SIP_PASS=$(openssl rand -hex 16)

CREATE_CRED=$(curl -s -X POST "https://api.telnyx.com/v2/credential_connections/$TRUNK_ID/credentials" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Retell Outbound Auth\",
    \"user_name\": \"$SIP_USER\",
    \"password\": \"$SIP_PASS\",
    \"sip_username\": \"$SIP_USER\"
  }")

echo "$CREATE_CRED" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'data' in data:
        print('[OK] Created SIP credentials')
        print('     Username:', data['data']['user_name'])
    else:
        print('[WARN] Credentials response:', json.dumps(data))
except:
    pass
"

echo ""
echo "Step 3: Adding Retell SIP URI to trunk..."

CREATE_URI=$(curl -s -X POST "https://api.telnyx.com/v2/credential_connections/$TRUNK_ID/fqdns" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "'"$TRUNK_ID"'",
    "fqdn": "sip.retellai.com",
    "dns_record_type": "srv",
    "port": 5060
  }')

echo "$CREATE_URI" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'data' in data:
        print('[OK] Added FQDN:', data['data']['fqdn'])
    else:
        print('[INFO]', json.dumps(data))
except:
    pass
"

echo ""
echo "Step 4: Finding phone number ID..."

PHONE_DATA=$(curl -s "https://api.telnyx.com/v2/phone_numbers?filter[phone_number]=8135478218" \
  -H "Authorization: Bearer $TELNYX_API_KEY")

PN_ID=$(echo "$PHONE_DATA" | python -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
if data:
    print(data[0]['id'])
else:
    print('')
")

if [ -z "$PN_ID" ]; then
    echo "[ERROR] Could not find phone number"
    exit 1
fi

echo "[OK] Found phone number ID: $PN_ID"
echo ""

echo "Step 5: Assigning +18135478218 to Retell SIP trunk..."

ASSIGN=$(curl -s -X PATCH "https://api.telnyx.com/v2/phone_numbers/$PN_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\":\"$TRUNK_ID\"}")

echo "$ASSIGN" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)['data']
    print('[OK] Successfully assigned to SIP trunk')
    print('     Phone:', data['phone_number'])
    print('     Connection:', data.get('connection_name', 'N/A'))
except Exception as e:
    print('[ERROR]', str(e))
"

echo ""
echo "============================================"
echo "SUCCESS - RETELL SIP TRUNK CREATED"
echo "============================================"
echo ""
echo "Trunk Configuration:"
echo "  Trunk ID: $TRUNK_ID"
echo "  Transport: TCP"
echo "  Codecs: G722, G729, OPUS"
echo "  Number Format: +E.164"
echo "  SIP Region: ashburn-va"
echo "  Destination: sip.retellai.com"
echo ""
echo "SIP Credentials (for Retell import):"
echo "  Username: $SIP_USER"
echo "  Password: $SIP_PASS"
echo ""
echo "Phone Number:"
echo "  +18135478218 assigned to trunk"
echo ""
echo "============================================"
echo "NEXT STEP: IMPORT TO RETELL"
echo "============================================"
echo ""
echo "Run the automated import now:"
echo ""

# Create automated import script
cat > import_to_retell.sh <<'IMPORTSCRIPT'
#!/usr/bin/env bash
set -euo pipefail

source .retell_sip_credentials

export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

echo "Importing +18135478218 to Retell..."

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
    \"nickname\": \"BadBot Line - Primary Client\"
  }")

echo "$IMPORT_RESPONSE" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'phone_number' in data:
        print('[OK] Number imported to Retell')
        print('     Phone:', data['phone_number'])
        print('     Agent:', data.get('inbound_agent_id', 'N/A'))
    else:
        print('[ERROR]', json.dumps(data))
except Exception as e:
    print('[ERROR]', str(e))
"

echo ""
echo "TEST: Call +18135478218"
echo "Should hear: 'Hello, who's calling please?'"
IMPORTSCRIPT

chmod +x import_to_retell.sh

# Save credentials
cat > .retell_sip_credentials <<EOF
TRUNK_ID=$TRUNK_ID
SIP_USERNAME=$SIP_USER
SIP_PASSWORD=$SIP_PASS
PHONE_NUMBER=+18135478218
EOF

echo "  ./import_to_retell.sh"
echo ""
echo "Credentials saved to: .retell_sip_credentials"
echo ""
