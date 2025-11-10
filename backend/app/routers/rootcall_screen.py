import os
import logging
from typing import Optional
from fastapi import APIRouter, Request, Response
from app.services.client_config import get_client_config
import httpx

log = logging.getLogger("rootcall")

async def send_sms_alert(to_number: str, message: str, from_number: str = "+18135478530"):
    """Send SMS alert"""
    if DRY_RUN:
        log.info("[DRY_RUN] SMS to %s: %s", to_number, message)
        return True
    
    if not TELNYX_API_KEY or not to_number:
        log.warning("[SMS] Missing API key or phone number")
        return False
    
    url = "https://api.telnyx.com/v2/messages"
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={"from": from_number, "to": to_number, "text": message}
            )
            log.info("[SMS] Sent to %s: status %s", to_number, r.status_code)
            return r.status_code in [200, 201, 202]
        except Exception as e:
            log.error("[SMS] Error: %s", e)
            return False

router = APIRouter(prefix="/telnyx/rootcall", tags=["BadBot Screen"])

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "").strip()
TELNYX_SMS_FROM = os.getenv("TELNYX_SMS_FROM", "").strip()
DRY_RUN = os.getenv("BADBOT_DRY_RUN", "").strip() == "1"

# Telnyx webhook signature verification (optional but recommended)
TELNYX_PUBLIC_KEY = os.getenv("TELNYX_PUBLIC_KEY", "").strip()

def verify_telnyx_signature(request: Request, body: bytes):
    """Verify Telnyx webhook signature - currently disabled for testing"""
    # TODO: Implement signature verification for production
    # For now, we'll allow all requests for testing
    return True


async def telnyx_gather_speak(ccid: str, text: str):
    """Ask caller a question and wait for DTMF response"""
    if DRY_RUN:
        log.info("[DRY_RUN] gather_speak ccid=%s", ccid)
        return {"ok": True, "dry_run": True}

    if not TELNYX_API_KEY:
        log.error("Missing TELNYX_API_KEY")
        return {"error": "Missing API key"}

    url = f"https://api.telnyx.com/v2/calls/{ccid}/actions/gather_using_speak"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={
                    "payload": text,
                    "voice": "female",
                    "language": "en-US",
                    "valid_digits": "1234567890*#",
                    "timeout_millis": 10000,
                    "maximum_digits": 1,
                    "minimum_digits": 1
                }
            )
            log.info("Gather response: %s", r.status_code)
            return r.json() if r.text else {"ok": True}
        except Exception as e:
            log.error("Gather error: %s", e)
            return {"error": str(e)}

async def telnyx_answer(ccid: str):
    """Answer the incoming call"""
    if DRY_RUN:
        log.info("[DRY_RUN] answer ccid=%s", ccid)
        return {"ok": True, "dry_run": True}
    
    if not TELNYX_API_KEY:
        log.error("Missing TELNYX_API_KEY")
        return {"error": "Missing API key"}
    
    url = f"https://api.telnyx.com/v2/calls/{ccid}/actions/answer"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={}
            )
            log.info("Answer response: %s", r.status_code)
            return r.json() if r.text else {"ok": True}
        except Exception as e:
            log.error("Answer error: %s", e)
            return {"error": str(e)}


async def telnyx_speak(ccid: str, text: str):
    """Speak text to caller"""
    if DRY_RUN:
        log.info("[DRY_RUN] speak: %s", text)
        return {"ok": True}
    
    if not TELNYX_API_KEY:
        log.error("Missing TELNYX_API_KEY")
        return {"error": "Missing API key"}
    
    url = f"https://api.telnyx.com/v2/calls/{ccid}/actions/speak"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={
                    "payload": text,
                    "voice": "female",
                    "language": "en-US"
                }
            )
            log.info("Speak response: %s", r.status_code)
            return r.json() if r.text else {"ok": True}
        except Exception as e:
            log.error("Speak error: %s", e)
            return {"error": str(e)}

async def telnyx_transfer(ccid: str, to: str):
    """Transfer call to destination"""
    if DRY_RUN:
        log.info("[DRY_RUN] transfer ccid=%s to=%s", ccid, to)
        return {"ok": True, "dry_run": True}
    
    if not TELNYX_API_KEY:
        log.error("Missing TELNYX_API_KEY")
        return {"error": "Missing API key"}
    
    url = f"https://api.telnyx.com/v2/calls/{ccid}/actions/transfer"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={"to": to}
            )
            log.info("Transfer response: %s", r.status_code)
            log.info("Transfer response body: %s", r.text)
            
            if r.status_code >= 400:
                log.error("Transfer FAILED: %s", r.text)
                return {"error": r.text, "status_code": r.status_code}
            
            return r.json() if r.text else {"ok": True}
        except Exception as e:
            log.error("Transfer error: %s", e)
            return {"error": str(e)}

async def telnyx_hangup(ccid: str):
    """Hangup the call"""
    if DRY_RUN:
        log.info("[DRY_RUN] hangup ccid=%s", ccid)
        return {"ok": True, "dry_run": True}
    
    if not TELNYX_API_KEY:
        return
    
    url = f"https://api.telnyx.com/v2/calls/{ccid}/actions/hangup"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={}
            )
        except Exception as e:
            log.error("Hangup error: %s", e)

@router.post("/webhook", status_code=200)
async def screen_call(request: Request):
    """
    Main BadBot screening webhook - NO AUTHENTICATION REQUIRED
    This endpoint receives webhooks directly from Telnyx
    """
    
    # Log the incoming request
    client_ip = request.client.host if request.client else "unknown"
    log.info("[WEBHOOK] Received from IP: %s", client_ip)
    
    # Get raw body for signature verification
    try:
        raw_body = await request.body()
        body = await request.json()
        log.info("[WEBHOOK] Event received: %s", body.get("data", {}).get("event_type", "unknown"))
    except Exception as e:
        log.error("[WEBHOOK] Failed to parse body: %s", e)
        return {"error": "Invalid JSON", "status": "error"}
    
    # Optional: Verify Telnyx signature (disabled for testing)
    # if not verify_telnyx_signature(request, raw_body):
    #     log.warning("[WEBHOOK] Signature verification failed")
    #     return {"error": "Invalid signature", "status": "unauthorized"}
    
    data = body.get("data", {})
    evt = data.get("event_type", "")
    payload = data.get("payload", {})
    
    ccid = payload.get("call_control_id")
    # Handle both string and dict formats for from/to
    from_field = payload.get("from", "")
    to_field = payload.get("to", "")
    
    if isinstance(from_field, dict):
        from_num = from_field.get("phone_number", "")
    else:
        from_num = str(from_field)
    
    if isinstance(to_field, dict):
        to_num = to_field.get("phone_number", "")
    else:
        to_num = str(to_field)
    cnam = payload.get("caller_id_name", "")
    
    log.info("[CALL] Event: %s | From: %s | To: %s | CCID: %s", evt, from_num, to_num, ccid)
    
    if not ccid:
        log.warning("[WEBHOOK] No call_control_id found")
        return {"status": "no_ccid"}
    
    # Get client config
    cfg = get_client_config(to_num)
    if not cfg:
        log.warning("[CONFIG] No config for number: %s", to_num)
        return {"status": "no_config", "telnyx_number": to_num}
    
    # Handle call.initiated - Answer immediately
    if evt == "call.initiated":
        log.info("[INITIATED] Answering call")
        result = await telnyx_answer(ccid)
        return {"status": "answered", "result": result}
    
    # Handle call.answered - Start screening
    if evt == "call.answered":
        client_cell = cfg.get("client_cell", "")
        trusted = cfg.get("trusted_contacts", [])
        
        # 1) Check for spam
        spam_keywords = ["spam", "scam", "fraud", "robocall", "telemarketer"]
        if any(keyword in cnam.lower() for keyword in spam_keywords):
            log.warning("[SPAM] Blocked: %s (%s)", from_num, cnam)
            
            # Send SMS alert
            if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_spam"):
                await send_sms_alert(client_cell, f"[BadBot] SPAM BLOCKED: {cnam or from_num}")
            
            await telnyx_hangup(ccid)
            return {"status": "spam_blocked"}
        
        # 2) Check if trusted
        if from_num in trusted:
            log.info("[TRUSTED] Forwarding %s to %s", from_num, client_cell)
            
            # Alert about trusted contact
            if cfg.get("sms_alerts_enabled"):
                await send_sms_alert(client_cell, f"[BadBot] Trusted contact {cnam or from_num} calling")
            
            await telnyx_transfer(ccid, client_cell)
            return {"status": "trusted_forwarded"}
        
        # 3) Unknown caller - Screen them
        log.info("[SCREENING] Asking %s to identify themselves", from_num)
        
        # Alert client screening is happening
        log.info("[SMS CHECK] sms_alerts_enabled=%s, alert_on_unknown=%s, client_cell=%s", 
                 cfg.get("sms_alerts_enabled"), cfg.get("alert_on_unknown"), client_cell)
        if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_unknown"):
            log.info("[SMS] Sending unknown caller alert to %s", client_cell)
            await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened")
        else:
            log.warning("[SMS] Alert skipped - alerts not enabled or no client_cell")
        
        await telnyx_gather_speak(
            ccid,
            "Hello, who is calling? Press 1 if this is a doctor or medical office. Press 2 if you are family. Press 3 for all other calls."
        )
        return {"status": "screening_started"}
    
    # Handle gather.ended - Process caller response
    if evt == "call.gather.ended":
        digits = payload.get("digits", "")
        log.info("[GATHER] Caller pressed: %s", digits)
        
        client_cell = cfg.get("client_cell", "")
        
        if digits == "1":
            # Medical call - transfer immediately
            log.info("[MEDICAL] Transferring to %s", client_cell)
            await telnyx_speak(ccid, "Transferring you now.")
            import asyncio
            await asyncio.sleep(1)
            await telnyx_transfer(ccid, client_cell)
            return {"status": "medical_transferred"}
        elif digits == "2":
            # Family - transfer
            log.info("[FAMILY] Transferring to %s", client_cell)
            await telnyx_speak(ccid, "One moment please.")
            import asyncio
            await asyncio.sleep(1)
            await telnyx_transfer(ccid, client_cell)
            return {"status": "family_transferred"}
        else:
            # Other - send to voicemail or reject
            log.info("[OTHER] Rejecting call")
            await telnyx_speak(ccid, "Sorry, the person you are trying to reach is not available. Goodbye.")
            import asyncio
            await asyncio.sleep(2)
            await telnyx_hangup(ccid)
            return {"status": "rejected"}

        client_cell = cfg.get("client_cell", "")
        trusted = cfg.get("trusted_contacts", [])
        retell_did = cfg.get("retell_did", "")
        caregiver = cfg.get("caregiver_cell", "")
        
        # 1) Check for spam
        spam_keywords = ["spam", "scam", "fraud", "robocall", "telemarketer"]
        if any(keyword in cnam.lower() for keyword in spam_keywords):
            log.warning("[SPAM] Blocked: %s (%s)", from_num, cnam)
            
            # Send SMS alerts
            if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_spam"):
                await send_sms_alert(
                    client_cell, 
                    f"[BadBot] SPAM BLOCKED: {cnam or 'Unknown'} ({from_num})",
                    to_num  # Send from the BadBot number
                )
                if caregiver:
                    await send_sms_alert(
                        caregiver,
                        f"[BadBot] Spam blocked for {cfg.get('client_name')}: {from_num}"
                    )
            
            await telnyx_hangup(ccid)
            return {"status": "spam_blocked", "from": from_num}
        
        # 2) Check if trusted
        if from_num in trusted:
            log.info("[TRUSTED] Forwarding %s to %s", from_num, client_cell)
            
            # Notify client
            if cfg.get("sms_alerts_enabled"):
                await send_sms_alert(
                    client_cell,
                    f"[BadBot] Trusted contact {cnam or from_num} calling now",
                    to_num
                )
            
            if client_cell:
                result = await telnyx_transfer(ccid, client_cell)
                return {"status": "trusted_forwarded", "from": from_num, "to": client_cell, "result": result}
        
        # 3) Unknown -> Transfer DIRECTLY to client (bypass Retell for now)
        log.info("[UNKNOWN] Transferring %s DIRECTLY to client: %s", from_num, client_cell)
        if client_cell:
            send_sms_alert(client_cell, f"[BadBot] Unknown caller {from_num} - transferred")
            result = await telnyx_transfer(ccid, client_cell)
            return {"status": "unknown_transferred_direct", "from": from_num, "to": client_cell, "result": result}
        
        # 4) Fallback - forward with alert
        if client_cell:
            log.info("[FALLBACK] Forwarding %s to %s", from_num, client_cell)
            send_sms_alert(client_cell, f"[BadBot] Unknown caller {from_num} forwarded")
            result = await telnyx_transfer(ccid, client_cell)
            return {"status": "unknown_forwarded", "from": from_num, "to": client_cell, "result": result}
        
        log.warning("[NO_CONFIG] No routing configured")
        return {"status": "no_action_configured"}
    
    # Handle hangup events
    if evt in ("call.hangup", "call.ended", "call.hangup.completed"):
        log.info("[ENDED] Call ended: %s", evt)
        return {"status": "ok", "event": evt}
    
    # All other events
    log.info("[OTHER] Event: %s", evt)
    return {"status": "ignored", "event": evt}

@router.get("/health")
async def health_check():
    """Health check - no auth required"""
    return {
        "status": "ok",
        "service": "BadBot Call Screening",
        "dry_run": DRY_RUN,
        "has_api_key": bool(TELNYX_API_KEY)
    }

@router.get("/debug")
async def debug_info():
    """Debug info - no auth required"""
    from app.services.client_config import CLIENT_LINES
    return {
        "dry_run": DRY_RUN,
        "has_telnyx_key": bool(TELNYX_API_KEY),
        "has_sms_from": bool(TELNYX_SMS_FROM),
        "client_count": len(CLIENT_LINES),
        "telnyx_numbers": list(CLIENT_LINES.keys())
    }
