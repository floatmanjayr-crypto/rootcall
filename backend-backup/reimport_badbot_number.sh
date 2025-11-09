#!/usr/bin/env bash
set -euo pipefail

export TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
export RETELL_API_KEY=$(grep '^RETELL_API_KEY=' .env | cut -d= -f2)

# Get the latest trunk info
LATEST_TRUNK=$(curl -s "https://api.telnyx.com/v2/fqdn_connections" \
  -H "Authorization: Bearer $TELNYX_API_KEY" | python -c "
import sys, json
data = json.load(sys.stdin)['data']
# Get the most recent trunk with 'Retell AI SIP Trunk' in name
retell_trunks = [t for t in data if 'Retell AI SIP Trunk' in t['connection_name']]
if retell_trunks:
    latest = sorted(retell_trunks, key=lambda x: x['created_at'], reverse=True)[0]
    print(json.dumps(latest))
")

TRUNK_ID=$(echo "$LATEST_TRUNK" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
SIP_USERNAME=$(echo "$LATEST_TRUNK" | python -c "import sys, json; print(json.load(sys.stdin)['user_name'] or '')")
SIP_PASSWORD=$(echo "$LATEST_TRUNK" | python -c "import sys, json; print(json.load(sys.stdin)['password'] or '')")

echo "============================================"
echo "RE-IMPORTING BADBOT NUMBER TO RETELL"
echo "============================================"
echo ""
echo "Using trunk: $TRUNK_ID"
echo "Username: $SIP_USERNAME"
echo ""

# STEP 1: Delete existing number from Retell
echo "Step 1: Deleting old number from Retell..."
echo "------------------------------------------------------------"
DELETE=$(curl -s -X DELETE "https://api.retellai.com/delete-phone-number/+18135478218" \
  -H "Authorization: Bearer $RETELL_API_KEY")

echo "$DELETE" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('deleted'):
        print('[OK] Deleted old number from Retell')
    else:
        print('[INFO]', json.dumps(data))
except:
    print('[OK] Proceeding with import...')
"
echo ""

# STEP 2: Re-import with correct credentials and agent
echo "Step 2: Importing number with new trunk credentials..."
echo "------------------------------------------------------------"
IMPORT=$(curl -s -X POST "https://api.retellai.com/import-phone-number" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone_number\": \"+18135478218\",
    \"termination_uri\": \"sip.telnyx.com\",
    \"sip_trunk_auth\": {
      \"username\": \"$SIP_USERNAME\",
      \"password\": \"$SIP_PASSWORD\"
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
        print('     Inbound Agent:', data.get('inbound_agent_id', 'N/A'))
        print('     Outbound Agent:', data.get('outbound_agent_id', 'N/A'))
        if 'sip_outbound_trunk_config' in data:
            print('     SIP Username:', data['sip_outbound_trunk_config'].get('auth_username', 'N/A'))
    else:
        print('[ERROR] Import failed')
        print(json.dumps(data, indent=2))
        sys.exit(1)
except Exception as e:
    print('[ERROR]', str(e))
    sys.exit(1)
"
echo ""

echo "============================================"
echo "SUCCESS - NUMBER RE-IMPORTED"
echo "============================================"
echo ""
echo "Test now by calling: +18135478218"
echo ""
