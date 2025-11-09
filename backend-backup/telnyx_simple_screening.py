# -*- coding: utf-8 -*-
"""
Simple Telnyx call screening - NO RETELL NEEDED
Uses Telnyx gather_using_speak to ask caller identity
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add gather function
gather_function = '''
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

'''

# Insert before first async function
first_async = 'async def telnyx_answer'
content = content.replace(first_async, gather_function + first_async)

# Replace call.answered logic with screening
old_answered = '''    # Handle call.answered - Route the call
    if evt == "call.answered":'''

new_answered = '''    # Handle call.answered - Start screening
    if evt == "call.answered":
        client_cell = cfg.get("client_cell", "")
        trusted = cfg.get("trusted_contacts", [])
        
        # 1) Check for spam
        spam_keywords = ["spam", "scam", "fraud", "robocall", "telemarketer"]
        if any(keyword in cnam.lower() for keyword in spam_keywords):
            log.warning("[SPAM] Blocked: %s (%s)", from_num, cnam)
            await telnyx_hangup(ccid)
            return {"status": "spam_blocked"}
        
        # 2) Check if trusted
        if from_num in trusted:
            log.info("[TRUSTED] Forwarding %s to %s", from_num, client_cell)
            await telnyx_transfer(ccid, client_cell)
            return {"status": "trusted_forwarded"}
        
        # 3) Unknown caller - Screen them
        log.info("[SCREENING] Asking %s to identify themselves", from_num)
        await telnyx_gather_speak(
            ccid,
            "Hello, who is calling? Press 1 if this is a doctor or medical office. Press 2 if you are family. Press 3 for all other calls."
        )
        return {"status": "screening_started"}
    
    # Handle gather.ended - Process caller response
    if evt == "call.gather.ended":'''

content = content.replace(old_answered, new_answered)

# Add gather response handler
gather_handler = '''
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
'''

# Add after call.gather.ended line
content = content.replace(
    'if evt == "call.gather.ended":',
    'if evt == "call.gather.ended":' + gather_handler
)

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("✅ Added Telnyx-only screening!")
print("\nNEW FLOW:")
print("1. Caller dials +18135478530")
print("2. Telnyx answers")
print('3. Plays: "Who is calling? Press 1 for medical, 2 for family, 3 for other"')
print("4. If 1 or 2: Transfers to +17543670370")
print("5. If 3: Plays rejection message and hangs up")
print("\n✅ NO RETELL NEEDED!")
print("="*60)
