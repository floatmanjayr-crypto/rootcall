#!/usr/bin/env bash
set -euo pipefail
: "${WEBHOOK_AUTH_TOKEN:?Run:  ./load_webhook_token.sh  first}"

curl -sS -X POST "http://localhost:8000/telnyx/badbot/webhook" \
  -H "X-Webhook-Token: $WEBHOOK_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "data": {
    "event_type": "call.initiated",
    "payload": {
      "call_control_id": "TEST123",
      "from": { "phone_number": "+13055550123" },
      "to":   { "phone_number": "+18135478218" }
    }
  }
}
JSON
echo
