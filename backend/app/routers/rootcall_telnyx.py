import os
import json
import logging
from typing import Dict, Any
import httpx
from fastapi import APIRouter, Request, HTTPException

# Per-line mapping (public DID -> retell DID / cell)
from app.services.client_config import get_client_config

log = logging.getLogger("rootcall")

# --- Minimal inline "RootCall heuristics" (fallbacks) ---
def number_lookup(phone: str) -> Dict[str, Any]:
    # You can replace with your real CNAM/risk lookup later
    return {"number": phone, "cnam": "", "risk": "unknown"}

def is_trusted(phone: str) -> bool:
    # TODO: implement allowlist (customer/doctor/bank numbers)
    return False

def should_block_by_risk(lookup: Dict[str, Any]) -> bool:
    # TODO: implement STIR/SHAKEN, spam score, etc.
    return False

def classify_intent(phone: str) -> str:
    # TODO: detect healthcare/bank intents from history or DB
    return "unknown"

def whitelist(phone: str, tag: str = "") -> None:
    pass

def notify_blocked(frm: str, cnam: str = "") -> None:
    log.info(f"Blocked spam: {frm} {cnam}")

def notify_verified(intent: str) -> None:
    log.info(f"Verified {intent} caller")

# --- Minimal Telnyx Call Control client (inline) ---
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "").strip()
if not TELNYX_API_KEY:
    log.warning("TELNYX_API_KEY is not set. Call Control actions will fail.")

class TelnyxCC:
    BASE = "https://api.telnyx.com/v2"

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json",
        }

    @classmethod
    def _post(cls, ccid: str, action: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = f"{cls.BASE}/call_controls/{ccid}/actions/{action}"
        payload = payload or {}
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, headers=cls._headers(), json=payload)
        if r.status_code // 100 != 2:
            log.error("Telnyx %s failed (%s): %s", action, r.status_code, r.text)
            raise HTTPException(status_code=502, detail=f"Telnyx {action} error")
        return r.json() if r.text else {}

    @classmethod
    def answer(cls, ccid: str):
        return cls._post(ccid, "answer")

    @classmethod
    def hangup(cls, ccid: str):
        return cls._post(ccid, "hangup")

    @classmethod
    def speak(cls, ccid: str, text: str, voice: str = "female_en-US"):
        return cls._post(ccid, "speak", {"payload": {"language": "en-US", "voice": voice, "payload": text}})

    @classmethod
    def transfer_to(cls, ccid: str, destination: str):
        # destination can be E.164 or SIP URI
        return cls._post(ccid, "transfer", {"to": destination})

    @classmethod
    def record_start(cls, ccid: str):
        return cls._post(ccid, "start_recording")

# --- FastAPI router ---
router = APIRouter(prefix="/telnyx/rootcall", tags=["RootCall Telnyx"])
WEBHOOK_AUTH_TOKEN = os.getenv("WEBHOOK_AUTH_TOKEN", "").strip()

def _auth_ok(req: Request) -> bool:
    # Header name must match what you set in Telnyx webhook headers
    if not WEBHOOK_AUTH_TOKEN:
        return True
    return req.headers.get("x-webhook-token") == WEBHOOK_AUTH_TOKEN

@router.post("/webhook")
async def telnyx_webhook(request: Request):
    if not _auth_ok(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    data = (body.get("data") or {})
    evt  = (data.get("event_type") or "").lower()
    p    = data.get("payload") or {}
    ccid = p.get("call_control_id")
    frm  = (p.get("from") or {}).get("phone_number") or p.get("from") or ""
    to   = (p.get("to")   or {}).get("phone_number") or p.get("to")   or ""

    if not ccid:
        raise HTTPException(status_code=400, detail="Missing call_control_id")

    # Fetch per-client routing based on the CALLED number (public RootCall DID)
    cfg = get_client_config(to)
    RETELL_DID  = cfg.get("retell_did", "")
    CLIENT_CELL = cfg.get("client_cell", "")

    if evt == "call.initiated":
        TelnyxCC.answer(ccid)
        return {"ok": True}

    if evt == "call.answered":
        # 1) Trusted → send to client cell
        if is_trusted(frm) and CLIENT_CELL:
            TelnyxCC.transfer_to(ccid, CLIENT_CELL)
            return {"status": "trusted_transfer", "to": CLIENT_CELL}

        # 2) Risk screen (spam)
        lookup = number_lookup(frm)
        if should_block_by_risk(lookup):
            notify_blocked(frm, lookup.get("cnam", ""))
            TelnyxCC.hangup(ccid)
            return {"status": "blocked_spam"}

        # 3) Priority intents (healthcare/bank) could be verified here
        intent = classify_intent(frm)
        if intent in ("healthcare", "bank") and CLIENT_CELL:
            whitelist(frm, tag=intent)
            notify_verified(intent)
            TelnyxCC.transfer_to(ccid, CLIENT_CELL)
            return {"status": "verified_transfer", "intent": intent}

        # 4) Unknown → Retell DID (already bound to agent)
        if RETELL_DID:
            TelnyxCC.transfer_to(ccid, RETELL_DID)
            return {"status": "retell_transfer_did", "to": RETELL_DID}

        # 5) Fallback mini-voicemail
        TelnyxCC.speak(ccid, "This line is protected by RootCall. Please state your name and reason for calling.")
        TelnyxCC.record_start(ccid)
        return {"status": "screening_vm"}

    if evt in ("call.hangup", "call.ended"):
        return {"ok": True}

    # Ignore other events
    return {"ok": True}

# --- optional debug route (only if ROOTCALL_DEBUG=1) ---
from fastapi import Depends

@router.get("/debug-auth")
async def debug_auth(request: Request):
    if os.getenv("ROOTCALL_DEBUG") != "1":
        raise HTTPException(status_code=403, detail="Debug disabled")
    return {
        "expected_token": os.getenv("WEBHOOK_AUTH_TOKEN", ""),
        "received_header": request.headers.get("x-webhook-token", ""),
    }

# ---- DRY RUN HOOK (for local testing without real Telnyx calls) ----
if os.getenv("ROOTCALL_DRY_RUN") == "1":
    _orig_post = TelnyxCC._post

    @classmethod
    def _mock_post(cls, ccid: str, action: str, payload: Dict[str, Any] | None = None):
        log.info("[DRY_RUN] Telnyx %s ccid=%s payload=%s", action, ccid, payload)
        # mimic a 2xx response body so the rest of the flow proceeds
        return {"ok": True, "dry_run": True, "action": action, "ccid": ccid, "payload": payload or {}}

    TelnyxCC._post = _mock_post
    log.warning("ROOTCALL_DRY_RUN=1 — Telnyx API calls are mocked.")
