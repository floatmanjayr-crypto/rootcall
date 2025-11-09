#!/usr/bin/env bash
set -euo pipefail

# ========= REQUIRED (prefill here or export before running) =========
TELNYX_API_KEY="${TELNYX_API_KEY:-KEY0199F959E7D03882AA4D54B964E0360E_422PzCWuZaAP35VXvVDIlq}"
PHONE_NUMBER="${PHONE_NUMBER:-+18135478218}"          # must be +E.164 (starts with +)
PN_ID="${PN_ID:-2813503814340970131}"                 # optional; if blank we'll look it up

# ========= DEFAULTS (tweak if needed) =========
CONNECTION_NAME="${CONNECTION_NAME:-Retell Inbound Trunk}"
RETELL_SIP_URI="${RETELL_SIP_URI:-sip:sip.retellai.com;transport=tcp}"  # TCP per Retell docs
CODECS_JSON='["G722","G729","OPUS"]'                   # Retell recommends G722, G729, OPUS
TRANSPORT_PROTO="TCP"
BASE="https://api.telnyx.com/v2"

say(){ printf "%b\n" "$*"; }
die(){ printf "ERROR: %s\n" "$*" >&2; exit 1; }

[[ "${TELNYX_API_KEY}" ]] || die "TELNYX_API_KEY not set"
[[ "${PHONE_NUMBER}" =~ ^\+?[0-9]+$ ]] || die "PHONE_NUMBER must be +E.164 (e.g. +15551234567)"

NUM_DIGITS="${PHONE_NUMBER#+}"
ENC_PLUS="%2B${NUM_DIGITS}"

# --- 1) Find existing SIP connection by name ---
say "Looking for Telnyx connection named: ${CONNECTION_NAME}"
ENC_NAME="$(python - <<'PY'
import os, urllib.parse
print(urllib.parse.quote_plus(os.environ["CONNECTION_NAME"]))
PY
)"
LIST_JSON="$(curl -sS -H "Authorization: Bearer ${TELNYX_API_KEY}" \
  "${BASE}/connections?filter[name]=${ENC_NAME}")" || die "Failed to list connections"

CONNECTION_ID="$(
  python - <<'PY' <<<"$LIST_JSON" || true
import os,sys,json
try:
    d=json.load(sys.stdin)
    for item in d.get("data",[]):
        if item.get("connection_name")==os.environ["CONNECTION_NAME"]:
            print(item.get("id","")); break
except Exception: pass
PY
)"

if [[ -z "${CONNECTION_ID}" ]]; then
  say "No existing connection. Creating '${CONNECTION_NAME}' -> ${RETELL_SIP_URI} ..."
  CREATE_PAYLOAD="$(cat <<JSON
{
  "active": true,
  "connection_name": "${CONNECTION_NAME}",
  "connection_type": "sip_trunk",
  "sip_uri": "${RETELL_SIP_URI}",
  "codecs": ${CODECS_JSON},
  "transport_protocol": "${TRANSPORT_PROTO}"
}
JSON
)"
  CREATE_RESP="$(curl -sS -X POST "${BASE}/connections" \
    -H "Authorization: Bearer ${TELNYX_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "${CREATE_PAYLOAD}")" || die "Create connection failed"
  CONNECTION_ID="$(
    python - <<'PY' <<<"$CREATE_RESP" || true
import sys,json
try:
    d=json.load(sys.stdin); print((d.get("data") or {}).get("id",""))
except Exception: pass
PY
  )"
  [[ -n "${CONNECTION_ID}" ]] || { echo "$CREATE_RESP"; die "Create connection returned no id"; }
  say "Created connection id: ${CONNECTION_ID}"
else
  say "Found connection id: ${CONNECTION_ID}"
fi

# --- 2) Ensure we have the phone_number id ---
if [[ -z "${PN_ID}" ]]; then
  say "Looking up Telnyx id for ${PHONE_NUMBER} ..."
  PN_JSON="$(curl -sS -H "Authorization: Bearer ${TELNYX_API_KEY}" \
    "${BASE}/phone_numbers?filter%5Bphone_number%5D=${NUM_DIGITS}")" || die "Lookup failed (digits)"
  PN_ID="$(
    python - <<'PY' <<<"$PN_JSON" || true
import sys,json
try:
    d=json.load(sys.stdin); data=d.get("data",[])
    print(data[0]["id"] if data else "")
except Exception: pass
PY
  )"
  if [[ -z "${PN_ID}" ]]; then
    PN_JSON="$(curl -sS -H "Authorization: Bearer ${TELNYX_API_KEY}" \
      "${BASE}/phone_numbers?filter%5Bphone_number%5D=${ENC_PLUS}")" || die "Lookup failed (+E.164)"
    PN_ID="$(
      python - <<'PY' <<<"$PN_JSON" || true
import sys,json
try:
    d=json.load(sys.stdin); data=d.get("data",[])
    print(data[0]["id"] if data else "")
except Exception: pass
PY
    )"
  fi
  [[ -n "${PN_ID}" ]] || { echo "$PN_JSON"; die "Could not find id for ${PHONE_NUMBER}"; }
  say "Resolved PN_ID=${PN_ID}"
else
  say "Using provided PN_ID=${PN_ID}"
fi

# --- 3) Attach number to the connection ---
say "Attaching ${PHONE_NUMBER} (${PN_ID}) to connection ${CONNECTION_ID} ..."
PATCH_RESP="$(curl -sS -X PATCH "${BASE}/phone_numbers/${PN_ID}" \
  -H "Authorization: Bearer ${TELNYX_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(cat <<JSON
{ "connection_id": "${CONNECTION_ID}" }
JSON
)")" || die "Failed to PATCH phone_number"

# --- 4) Print a clean summary ---
say "----- Summary -----"
python - <<'PY' <<<"$PATCH_RESP" || true
import sys,json
try:
    d=json.load(sys.stdin); data=d.get("data",{})
    out={
        "phone_number": data.get("phone_number"),
        "status": data.get("status"),
        "connection_id": data.get("connection_id"),
        "connection_name": data.get("connection_name"),
    }
    print(json.dumps(out, indent=2))
except Exception:
    print("Raw:", sys.stdin.read())
PY

say "Done. Incoming calls to ${PHONE_NUMBER} will be sent to ${RETELL_SIP_URI} (TCP) with codecs G722/G729/OPUS."
say "If the phone still only rings:"
say "  • In Telnyx portal, confirm the number shows Connection: ${CONNECTION_NAME}"
say "  • Connection is Active, transport=TCP, SIP URI exactly '${RETELL_SIP_URI}'"
say "  • Retell side has an inbound agent/route expecting this trunk call."
