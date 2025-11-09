#!/bin/bash

TELNYX_API_KEY="KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq"
CONNECTION_ID="2812968115544000352"

echo "Setting format to +e164 (lowercase)..."

curl -X PATCH "https://api.telnyx.com/v2/fqdn_connections/$CONNECTION_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inbound": {
      "ani_number_format": "+e164",
      "dnis_number_format": "+e164",
      "sip_region": "US"
    }
  }' | python -m json.tool

echo ""
echo "✅ Done! Test now: Call +18135478530"
