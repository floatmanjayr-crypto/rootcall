#!/usr/bin/env bash
set -euo pipefail

# --- config ---
: "${RETELL_API_KEY:?RETELL_API_KEY not set}"
RETELL_LLM_ID="$(grep '^RETELL_LLM_ID=' .env | cut -d= -f2)"
: "${RETELL_LLM_ID:?RETELL_LLM_ID not set in .env}"

# minimal, schema-safe payload
cat > .tmp_agent.json <<JSON
{
  "name": "BadBot Agent",
  "response_engine": { "type": "retell-llm", "llm_id": "${RETELL_LLM_ID}" },
  "start_speaker": "user",
  "begin_message": ""
}
JSON

# call Retell, keep raw response
set +e
HTTP_CODE=$(curl -sS -o .retell_agent_raw.json -w "%{http_code}" \
  -X POST "https://api.retellai.com/create-agent" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  -d @.tmp_agent.json)
CURL_RC=$?
set -e

echo "CURL_RC=$CURL_RC"
echo "HTTP_CODE=$HTTP_CODE"
echo "----- RAW -----"
cat .retell_agent_raw.json || true
echo "---------------"

# show helpful error and exit if not success
if [ "$CURL_RC" -ne 0 ] || { [ "$HTTP_CODE" != "201" ] && [ "$HTTP_CODE" != "200" ]; }; then
  echo "ERROR: create-agent failed. See .retell_agent_raw.json" >&2
  exit 1
fi

# extract agent_id without jq
python - <<'PY'
import json, sys
d=json.load(open(".retell_agent_raw.json","r",encoding="utf-8"))
agent_id = d.get("agent_id") or d.get("data",{}).get("agent_id")
if not agent_id:
    print("ERROR: agent_id not found in response.", file=sys.stderr)
    sys.exit(1)
# update .env
envp=".env"
try:
    lines=open(envp,"r",encoding="utf-8").read().splitlines()
except FileNotFoundError:
    lines=[]
for i,ln in enumerate(lines):
    if ln.startswith("RETELL_AGENT_ID="):
        lines[i]=f"RETELL_AGENT_ID={agent_id}"
        break
else:
    lines.append(f"RETELL_AGENT_ID={agent_id}")
open(envp,"w",encoding="utf-8").write("\n".join(lines)+("\n" if lines else ""))
print("RETELL_AGENT_ID:", agent_id)
print("Updated .env with RETELL_AGENT_ID.")
PY

grep -E 'RETELL_(LLM|AGENT)_ID' .env || true
