#!/usr/bin/env bash
set -euo pipefail

# --- config from env ---
: "${RETELL_API_KEY:?RETELL_API_KEY not set}"
: "${RETELL_AUDIT_NUMBER:?RETELL_AUDIT_NUMBER not set}"

# --- fill the transfer DID directly into JSON (avoid jq) ---
tmp_json=".tmp_badbot_llm.json"
python - "$RETELL_AUDIT_NUMBER" < badbot_llm.json > "$tmp_json" <<'PY'
import json, sys
did = sys.argv[1]
data = json.load(sys.stdin)
# replace the placeholder in general_tools[0].transfer_destination.number
for t in data.get("general_tools", []):
    if t.get("type")=="transfer_call":
        dest = t.get("transfer_destination") or {}
        if dest.get("number") == "REPLACE_ME_WITH_RETELL_AUDIT_NUMBER":
            dest["number"] = did
            t["transfer_destination"] = dest
print(json.dumps(data, ensure_ascii=False))
PY

echo "Injected RETELL_AUDIT_NUMBER into payload."

# --- try primary endpoint; fall back to /v2 if needed ---
PRIMARY_URL="https://api.retellai.com/create-retell-llm"
ALT_URL="https://api.retellai.com/v2/create-retell-llm"

resp_primary=".last_badbot_llm_response.json"
resp_alt=".last_badbot_llm_response_alt.json"

echo "POST $PRIMARY_URL"
code=$(curl -sS -X POST "$PRIMARY_URL" \
  -H "Authorization: Bearer $RETELL_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @"$tmp_json" \
  -o "$resp_primary" -w "%{http_code}")

echo "HTTP $code (primary)"
if [ "$code" != "201" ]; then
  echo "Primary failed, trying $ALT_URL ..."
  code2=$(curl -sS -X POST "$ALT_URL" \
    -H "Authorization: Bearer $RETELL_API_KEY" \
    -H "Content-Type: application/json" \
    --data-binary @"$tmp_json" \
    -o "$resp_alt" -w "%{http_code}")
  echo "HTTP $code2 (alt)"
fi

# --- extract llm_id with Python (no jq needed) ---
LLM_ID=$(python - <<'PY'
import json, sys
for p in (".last_badbot_llm_response.json", ".last_badbot_llm_response_alt.json"):
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if "llm_id" in d and d["llm_id"]:
            print(d["llm_id"]); sys.exit(0)
        if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict) and "llm_id" in d["data"]:
            print(d["data"]["llm_id"]); sys.exit(0)
    except Exception:
        pass
sys.exit(1)
PY
) || true

if [ -z "${LLM_ID:-}" ]; then
  echo "ERROR: Could not extract llm_id. See $resp_primary and $resp_alt"
  exit 1
fi

echo "Created Retell LLM: $LLM_ID"

# --- persist to .env (create if missing) ---
if [ -f .env ]; then
  if grep -q '^RETELL_LLM_ID=' .env; then
    # in-place edit (macOS/BSD sed compatibility)
    sed -i.bak 's/^RETELL_LLM_ID=.*/RETELL_LLM_ID='"$LLM_ID"'/' .env || true
  else
    printf "\nRETELL_LLM_ID=%s\n" "$LLM_ID" >> .env
  fi
else
  printf "RETELL_LLM_ID=%s\n" "$LLM_ID" > .env
fi
echo "Updated .env with RETELL_LLM_ID=$LLM_ID"
