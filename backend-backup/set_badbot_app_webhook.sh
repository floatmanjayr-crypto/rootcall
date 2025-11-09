#!/usr/bin/env bash
set -euo pipefail

: "${TELNYX_API_KEY:?TELNYX_API_KEY not set}"
: "${BADBOT_WEBHOOK:?BADBOT_WEBHOOK not set, e.g. https://your-domain/telnyx/badbot/webhook}"
: "${WEBHOOK_AUTH_TOKEN:?WEBHOOK_AUTH_TOKEN not set}"

# Find the Call Control App by name (BadBot Connection) or use APP_ID if provided
APP_ID="${APP_ID:-}"

if [ -z "${APP_ID}" ]; then
  APP_ID="$(
    curl -sS -H "Authorization: Bearer $TELNYX_API_KEY" \
      "https://api.telnyx.com/v2/call_control_applications" \
    | python - <<'PY'
import sys, json
d=json.load(sys.stdin)
for item in d.get("data", []):
    if item.get("application_name")=="BadBot Connection":
        print(item["id"]); break
PY
  )"
fi

[ -n "$APP_ID" ] || { echo "ERROR: Could not resolve APP_ID. Set APP_ID or create the app first."; exit 1; }

curl -sS -X PATCH "https://api.telnyx.com/v2/call_control_applications/$APP_ID" \
  -H "Authorization: Bearer $TELNYX_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "webhook_event_url": "$BADBOT_WEBHOOK",
  "webhook_api_version": "2",
  "webhook_timeout_secs": 10,
  "webhook_headers": { "X-Webhook-Token": "$WEBHOOK_AUTH_TOKEN" }
}
JSON

echo "OK: Updated Call Control App $APP_ID to $BADBOT_WEBHOOK with X-Webhook-Token."
