#!/usr/bin/env bash
set -euo pipefail

: "${TELNYX_API_KEY:?set TELNYX_API_KEY}"
: "${APP_ID:?set APP_ID (Call Control app id)}"
: "${PHONE_NUMBER:?set PHONE_NUMBER like +15551234567}"

BASE="https://api.telnyx.com/v2"
NUM_DIGITS="${PHONE_NUMBER#+}"         # strip leading +
ENC_PLUS="%2B${NUM_DIGITS}"            # +E.164 url-encoded

fetch() { curl -sS -H "Authorization: Bearer $TELNYX_API_KEY" "$1"; }

echo "Looking up Telnyx id for $PHONE_NUMBER ..."

# Try digits-only filter
PN_JSON="$(fetch "$BASE/phone_numbers?filter%5Bphone_number%5D=$NUM_DIGITS")"
# If no data, try +E164 filter
if ! printf '%s' "$PN_JSON" | grep -q '"data"'; then
  PN_JSON="$(fetch "$BASE/phone_numbers?filter%5Bphone_number%5D=$ENC_PLUS")"
fi
# If still no data, list and match locally
if ! printf '%s' "$PN_JSON" | grep -q '"data"'; then
  PN_JSON="$(fetch "$BASE/phone_numbers?page[size]=200")"
fi

PN_ID="$(
python - "$PHONE_NUMBER" <<'PY' 2>/dev/null
import json, sys, os
needle=sys.argv[1]
try:
    d=json.load(sys.stdin)
    for it in d.get("data", []):
        if it.get("phone_number")==needle:
            print(it.get("id",""))
            sys.exit(0)
except Exception:
    pass
sys.exit(1)
PY
)" || true

if [ -z "${PN_ID:-}" ]; then
  echo "ERROR: Could not find id for $PHONE_NUMBER" >&2
  printf '%s\n' "$PN_JSON" | head -c 1000 >&2; echo >&2
  exit 1
fi

echo "Found PN_ID=$PN_ID for $PHONE_NUMBER"
echo "Patching connection_id -> $APP_ID ..."
curl -sS -X PATCH "$BASE/phone_numbers/$PN_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"connection_id":"'"$APP_ID"'","messaging_profile_id":null}' \
  | tee .last_telnyx_patch.json >/dev/null

echo "Verify linkage:"
curl -sS "$BASE/phone_numbers/$PN_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  | grep -E '"phone_number"|"connection_id"|"connection_name"'
