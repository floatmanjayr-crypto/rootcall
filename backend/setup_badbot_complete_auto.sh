#!/usr/bin/env bash
set -euo pipefail
export TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
export PHONE_NUMBER="+18135478218"
# Get RETELL_API_KEY from .env
export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)
echo "============================================"
echo "BADBOT COMPLETE AUTOMATED SETUP"
echo "============================================"
echo ""
# STEP 1: Generate random SIP credentials (alphanumeric only)
echo "Step 1: Generating SIP credentials..."
echo "------------------------------------------------------------"
TIMESTAMP=$(date +%s)
SIP_USER="retell${TIMESTAMP}$(openssl rand -hex 4)"
SIP_PASS=$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-32)
TRUNK_NAME="Retell AI SIP Trunk ${TIMESTAMP}"
echo "[OK] Generated credentials"
echo "     Username: $SIP_USER"
echo "     Password: ${SIP_PASS:0:8}***"
echo ""
# STEP 2: Create FQDN-based Elastic SIP Trunk with credentials
echo "Step 2: Creating FQDN-based Elastic SIP Trunk for Retell..."
echo "------------------------------------------------------------"
CREATE_TRUNK=$(curl -s -X POST "https://api.telnyx.com/v2/fqdn_connections" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_name": "'"$TRUNK_NAME"'",
    "user_name": "'"$SIP_USER"'",
    "password": "'"$SIP_PASS"'",
    "transport_protocol": "TCP",
    "default_on_hold_comfort_noise_enabled": false,
    "dtmf_type": "RFC 2833",
    "encode_contact_header_enabled": false,
    "inbound": {
      "codecs": ["G722", "G729", "OPUS"],
      "channel_limit": null,
      "generate_ringback_tone": true,
      "sip_subdomain_receive_settings": "only_my_connections",
      "shaken_stir_enabled": false
    },
    "outbound": {
      "channel_limit": null,
      "outbound_voice_profile_id": "",
      "fqdn_authentication_method": "credential-authentication"
    }
  }')
TRUNK_ID=$(echo "$CREATE_TRUNK" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'data' in data:
        print(data['data']['id'])
    else:
        print('')
except:
    print('')
")
if [ -z "$TRUNK_ID" ]; then
    echo "[ERROR] Failed to create trunk"
    echo "$CREATE_TRUNK" | python -m json.tool 2>/dev/null || echo "$CREATE_TRUNK"
    exit 1
fi
echo "[OK] Created FQDN-based SIP Trunk: $TRUNK_ID"
echo "     Name: $TRUNK_NAME"
echo "     Credentials: Embedded"
echo ""
# STEP 3: Add Retell FQDN to trunk (SRV record without port)
echo "Step 3: Adding sip.retellai.com to trunk..."
echo "------------------------------------------------------------"
CREATE_FQDN=$(curl -s -X POST "https://api.telnyx.com/v2/fqdns" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "'"$TRUNK_ID"'",
    "fqdn": "sip.retellai.com",
    "dns_record_type": "srv"
  }')
echo "$CREATE_FQDN" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'data' in data:
        print('[OK] Added FQDN: sip.retellai.com (SRV)')
    elif 'errors' in data:
        print('[ERROR] FQDN add failed:', data['errors'][0].get('detail', 'Unknown error'))
        sys.exit(1)
    else:
        print('[INFO]', json.dumps(data))
except Exception as e:
    print('[ERROR] Failed to parse response:', str(e))
    sys.exit(1)
"
echo ""
# STEP 4: Find and assign phone number
echo "Step 4: Finding phone number..."
echo "------------------------------------------------------------"
# URL encode the + sign as %2B
PN_RESPONSE=$(curl -s "https://api.telnyx.com/v2/phone_numbers?filter%5Bphone_number%5D=%2B18135478218" \
  -H "Authorization: Bearer $TELNYX_API_KEY")

PN_ID=$(echo "$PN_RESPONSE" | python -c "
import sys, json
try:
    response = json.load(sys.stdin)
    data = response.get('data', [])
    if data and len(data) > 0:
        print(data[0]['id'])
    else:
        print('')
except Exception as e:
    print('', file=sys.stderr)
" 2>/dev/null)

if [ -z "$PN_ID" ]; then
    echo "[ERROR] Phone number not found"
    echo "Trying to list all numbers..."
    curl -s "https://api.telnyx.com/v2/phone_numbers" \
      -H "Authorization: Bearer $TELNYX_API_KEY" | python -m json.tool | head -20
    exit 1
fi
echo "[OK] Found phone number ID: $PN_ID"
echo ""
echo "Step 5: Assigning +18135478218 to SIP trunk..."
echo "------------------------------------------------------------"
ASSIGN=$(curl -s -X PATCH "https://api.telnyx.com/v2/phone_numbers/$PN_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\":\"$TRUNK_ID\"}")
echo "$ASSIGN" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)['data']
    print('[OK] Assigned to SIP trunk')
    print('     Phone:', data['phone_number'])
    print('     Connection:', data.get('connection_name', 'N/A'))
except Exception as e:
    print('[WARN]', str(e))
"
echo ""
# STEP 6: Import to Retell
echo "Step 6: Importing number to Retell..."
echo "------------------------------------------------------------"
IMPORT=$(curl -s -X POST "https://api.retellai.com/import-phone-number" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"$PHONE_NUMBER\",
    \"termination_uri\": \"sip.telnyx.com\",
    \"sip_trunk_auth\": {
      \"username\": \"$SIP_USER\",
      \"password\": \"$SIP_PASS\"
    },
    \"inbound_agent_id\": \"agent_cde1ba4c8efa2aba5665a77b91\",
    \"outbound_agent_id\": \"agent_cde1ba4c8efa2aba5665a77b91\",
    \"nickname\": \"BadBot Line - Primary Client\"
  }")
echo "$IMPORT" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'phone_number' in data:
        print('[OK] Number imported to Retell')
        print('     Phone:', data['phone_number'])
        print('     Agent:', data.get('inbound_agent_id', 'N/A'))
    else:
        print('[ERROR] Import failed')
        print(json.dumps(data, indent=2))
except Exception as e:
    print('[ERROR]', str(e))
"
echo ""
# STEP 7: Update client config
echo "Step 7: Updating backend configuration..."
echo "------------------------------------------------------------"
cat > app/services/client_config.py << 'PYCONFIG'
from typing import Dict, List, Optional
CLIENT_LINES: Dict[str, Dict] = {}
def get_client_config(telnyx_number: str) -> Optional[Dict]:
    normalized = telnyx_number.strip()
    if not normalized.startswith("+"):
        normalized = f"+{normalized}"
    return CLIENT_LINES.get(normalized)
# BadBot Client Configuration
CLIENT_LINES["+18135478218"] = {
    "client_cell": "+17543314009",
    "client_name": "Primary Senior Client",
    "retell_agent_id": "agent_cde1ba4c8efa2aba5665a77b91",
    "retell_did": "+18135478218",
    "trusted_contacts": [
        # Add trusted numbers here, e.g.:
        # "+17545551234",  # Family member
        # "+18005551234",  # Doctor's office
    ],
    "caregiver_cell": ""  # Optional: receives SMS alerts
}
PYCONFIG
echo "[OK] Updated app/services/client_config.py"
echo ""
# STEP 8: Save credentials
cat > .retell_sip_credentials << EOF
TRUNK_ID=$TRUNK_ID
SIP_USERNAME=$SIP_USER
SIP_PASSWORD=$SIP_PASS
PHONE_NUMBER=$PHONE_NUMBER
TRUNK_NAME=$TRUNK_NAME
TRUNK_TYPE=FQDN
EOF
echo "[OK] Saved credentials to .retell_sip_credentials"
echo ""
# Summary
echo "============================================"
echo "SUCCESS - BADBOT FULLY CONFIGURED"
echo "============================================"
echo ""
echo "Configuration Summary:"
echo "  Phone Number:  +18135478218"
echo "  Client Cell:   +17543314009"
echo "  SIP Trunk ID:  $TRUNK_ID"
echo "  Trunk Type:    FQDN-based"
echo "  FQDN:          sip.retellai.com (SRV)"
echo "  SIP Username:  $SIP_USER"
echo "  Trunk Name:    $TRUNK_NAME"
echo "  Agent:         agent_cde1ba4c8efa2aba5665a77b91"
echo ""
echo "Call Flow:"
echo "  Incoming call -> Telnyx +18135478218"
echo "  -> FQDN-based SIP Trunk"
echo "  -> Forwards to sip.retellai.com"
echo "  -> Retell authenticates with credentials"
echo "  -> Retell Agent (BadBot) answers"
echo "  -> Screens for fraud"
echo ""
echo "============================================"
echo "TEST NOW"
echo "============================================"
echo ""
echo "Call: +18135478218"
echo ""
echo "Expected response:"
echo '  "Hello, this is Primary Senior Client'"'"'s assistant.'
echo '   Who'"'"'s calling please?"'
echo ""
echo "Test fraud detection:"
echo '  Say: "This is the IRS, you owe taxes"'
echo "  BadBot should hang up immediately"
echo ""
echo "Test legitimate transfer:"
echo '  Say: "This is Dr. Smith'"'"'s office"'
echo "  BadBot should offer to transfer"
echo ""
echo "View in dashboard:"
echo "  https://app.retellai.com/dashboard/calls"
echo ""
