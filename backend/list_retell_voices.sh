#!/usr/bin/env bash
set -euo pipefail
: "${RETELL_API_KEY:?RETELL_API_KEY not set}"

echo "Trying /list-voices ..."
curl -sS -X GET "https://api.retellai.com/list-voices" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  | python - <<'PY' || true
import sys, json
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("Could not parse /list-voices response:", e)
    raise
voices = d.get("voices") or d.get("data") or []
print(f"Found {len(voices)} voices on /list-voices")
for v in voices[:10]:
    vid = v.get("voice_id") or v.get("id")
    name = v.get("name")
    print(f"- voice_id={vid}  name={name}")
PY

echo
echo "Trying /voices ..."
curl -sS -X GET "https://api.retellai.com/voices" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  | python - <<'PY' || true
import sys, json
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("Could not parse /voices response:", e)
    raise
voices = d.get("voices") or d.get("data") or []
print(f"Found {len(voices)} voices on /voices")
for v in voices[:10]:
    vid = v.get("voice_id") or v.get("id")
    name = v.get("name")
    print(f"- voice_id={vid}  name={name}")
PY
