#!/usr/bin/env bash
set -euo pipefail

: "${TELNYX_API_KEY:?set TELNYX_API_KEY}"
export PHONE_NUMBER="+18135478218"

echo "============================================"
echo "MOVING +18135478218 TO RETELL SIP TRUNK"
echo "============================================"
echo ""

# Step 1: Find the phone number ID
echo "Step 1: Finding phone number ID..."
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
    echo "Error: Could not find phone number +18135478218"
    exit 1
fi

echo "Found phone number ID: $PN_ID"

# Check current connection
CURRENT_CONN=$(echo "$PHONE_DATA" | python -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
if data:
    d = data[0]
    print(f\"Current connection: {d.get('connection_name', 'None')}\")
    print(f\"Connection ID: {d.get('connection_id', 'None')}\")
")

echo "$CURRENT_CONN"
echo ""

# Step 2: Check existing SIP trunks
echo "Step 2: Checking existing SIP trunks..."
EXISTING_TRUNKS=$(curl -s "https://api.telnyx.com/v2/texml_applications" \
  -H "Authorization: Bearer $TELNYX_API_KEY")

TRUNK_ID=$(echo "$EXISTING_TRUNKS" | python -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
for trunk in data:
    name = trunk.get('friendly_name', '')
    print(f\"Found: {name} (ID: {trunk['id']})\")
    if 'voip' in name.lower() or 'retell' in name.lower():
        print(f\"Using this trunk: {trunk['id']}\")
        print(trunk['id'])
        exit(0)
" 2>&1 | tail -1)

if [ -z "$TRUNK_ID" ] || [ "$TRUNK_ID" = "None" ]; then
    echo ""
    echo "No suitable SIP trunk found. Creating new one..."
    
    CREATE_RESPONSE=$(curl -s -X POST "https://api.telnyx.com/v2/texml_applications" \
      -H "Authorization: Bearer $TELNYX_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "friendly_name": "Retell AI SIP Trunk",
        "voice_url": "sip:sip.retellai.com;transport=tcp",
        "voice_method": "POST"
      }')
    
    TRUNK_ID=$(echo "$CREATE_RESPONSE" | python -c "
import sys, json
try:
    print(json.load(sys.stdin)['data']['id'])
except Exception as e:
    print('')
" 2>/dev/null)
    
    if [ -n "$TRUNK_ID" ]; then
        echo "✅ Created new SIP trunk: $TRUNK_ID"
    else
        echo "❌ Failed to create trunk"
        echo "$CREATE_RESPONSE"
        exit 1
    fi
else
    echo "✅ Using existing SIP trunk: $TRUNK_ID"
fi

echo ""
echo "Step 3: Assigning +18135478218 to SIP trunk..."

ASSIGN_RESPONSE=$(curl -s -X PATCH "https://api.telnyx.com/v2/phone_numbers/$PN_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"connection_id\":\"$TRUNK_ID\"}")

echo "$ASSIGN_RESPONSE" | python -c "
import sys, json
try:
    d = json.load(sys.stdin)['data']
    print(f\"✅ Successfully assigned to SIP trunk\")
    print(f\"   Phone: {d['phone_number']}\")
    print(f\"   Connection: {d.get('connection_name', 'N/A')}\")
    print(f\"   Connection ID: {d.get('connection_id', 'N/A')}\")
except Exception as e:
    print(f\"Response: {sys.stdin.read()}\")
"

echo ""
echo "============================================"
echo "✅ COMPLETE!"
echo "============================================"
echo ""
echo "+18135478218 is now on SIP trunk → Retell"
echo ""
echo "Call flow:"
echo "  1. Incoming call → Telnyx +18135478218"
echo "  2. Routes via SIP → sip.retellai.com"
echo "  3. Retell Agent answers with BadBot prompt"
echo ""
echo "��� TEST NOW:"
echo "  Call +18135478218 from your phone"
echo "  Should hear: 'Hello, who's calling please?'"
echo ""
