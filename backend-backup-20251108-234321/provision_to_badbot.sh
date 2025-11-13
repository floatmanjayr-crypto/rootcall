#!/usr/bin/env bash
set -euo pipefail
: "${TELNYX_API_KEY:?TELNYX_API_KEY not set}"
APP_ID="${APP_ID:?APP_ID (BadBot Call Control App id) not set}"
E164="${1:?Usage: ./provision_to_badbot.sh +1XXXXXXXXXX}"

num_digits="$(echo "$E164" | tr -d '+')"
PN_ID="$(
  curl -sS "https://api.telnyx.com/v2/phone_numbers?filter[phone_number]=$num_digits" \
    -H "Authorization: Bearer $TELNYX_API_KEY" \
  | python - <<'PY'
import sys, json
d=json.load(sys.stdin)
print(d['data'][0]['id'])
PY
)"

curl -sS -X PATCH "https://api.telnyx.com/v2/phone_numbers/$PN_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"connection_id":"'"$APP_ID"'"}'

echo
echo "OK: Provisioned $E164 (id=$PN_ID) -> BadBot app (connection_id=$APP_ID)."
