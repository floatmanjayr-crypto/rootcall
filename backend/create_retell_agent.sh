#!/usr/bin/env bash
set -euo pipefail

# --- config ---
: "${RETELL_API_KEY:?RETELL_API_KEY not set}"
RETELL_LLM_ID="$(grep -m1 '^RETELL_LLM_ID=' .env | cut -d= -f2)"
: "${RETELL_LLM_ID:?RETELL_LLM_ID not set in .env}"
: "${RETELL_VOICE_ID:?RETELL_VOICE_ID not set (export RETELL_VOICE_ID=...)}"

# minimal, schema-safe payload: voice + LLM response engine
cat > .tmp_agent.json <<JSON
{
  "name": "BadBot Agent",
  "voice_id": "${RETELL_VOICE_ID}",
  "response_engine": { "type": "retell-llm", "llm_id": "${RETELL_LLM_ID}" },
  "begin_message": "Hello, this line screens incoming calls."
}
JSON

echo "Creating agent with voice_id=${RETELL_VOICE_ID} and llm_id=${RETELL_LLM_ID} ..."
HTTP_CODE=$(curl -sS -w "%{http_code}" -o .retell_agent_raw.json \
  -X POST "https://api.retellai.com/create-agent" \
  -H "Authorization: Bearer ${RETELL_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary @.tmp_agent.json)

echo "HTTP_CODE=${HTTP_CODE}"
cat .retell_agent_raw.json; echo

if [ "${HTTP_CODE}" != "201" ] && [ "${HTTP_CODE}" != "200" ]; then
  echo "ERROR: create-agent failed. See .retell_agent_raw.json" >&2
  exit 1
fi

# pull agent_id from response without jq
AGENT_ID=$(python - <<'PY'
import json,sys
d=json.load(open(".retell_agent_raw.json","r",encoding="utf-8"))
print(d.get("agent_id",""))
PY
)

if [ -z "${AGENT_ID}" ]; then
  echo "ERROR: could not extract agent_id. Inspect .retell_agent_raw.json." >&2
  exit 1
fi

# write to .env (add or replace)
if grep -q '^RETELL_AGENT_ID=' .env 2>/dev/null; then
  sed -i.bak -E "s|^RETELL_AGENT_ID=.*$|RETELL_AGENT_ID=${AGENT_ID}|g" .env
else
  printf "\nRETELL_AGENT_ID=%s\n" "${AGENT_ID}" >> .env
fi

echo "RETELL_AGENT_ID=${AGENT_ID}"
echo "Updated .env with RETELL_AGENT_ID."
