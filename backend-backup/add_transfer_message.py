# -*- coding: utf-8 -*-
"""
Add "One moment please" message before transfer
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Find the transfer section and add speak before transfer
old_code = '''        # 3) Unknown -> Transfer directly to client
        log.info("[UNKNOWN] Transferring %s to client: %s", from_num, client_cell)
        if client_cell:
            result = await telnyx_transfer(ccid, client_cell)
            return {"status": "direct_transfer", "from": from_num, "to": client_cell}'''

new_code = '''        # 3) Unknown -> Greet then transfer to client
        log.info("[UNKNOWN] Greeting then transferring %s to client: %s", from_num, client_cell)
        if client_cell:
            # Say "One moment please" before transferring
            await telnyx_speak(ccid, "One moment please, transferring your call.")
            # Wait a moment for speech to complete
            import asyncio
            await asyncio.sleep(2)
            # Now transfer
            result = await telnyx_transfer(ccid, client_cell)
            return {"status": "greeted_and_transferred", "from": from_num, "to": client_cell}'''

if old_code in content:
    content = content.replace(old_code, new_code)
    
    # Now add the speak function
    speak_function = '''
async def telnyx_speak(ccid: str, text: str):
    """Speak text to caller before action"""
    if DRY_RUN:
        log.info("[DRY_RUN] speak ccid=%s text=%s", ccid, text)
        return {"ok": True, "dry_run": True}

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

'''
    
    # Insert speak function before telnyx_transfer
    transfer_func_start = 'async def telnyx_transfer(ccid: str, to: str):'
    content = content.replace(transfer_func_start, speak_function + transfer_func_start)
    
    with open('app/routers/badbot_screen.py', 'w') as f:
        f.write(content)
    
    print("✅ Added greeting before transfer!")
    print("\nNow when calling +18135478530:")
    print("1. Call connects")
    print('2. Agent says: "One moment please, transferring your call."')
    print("3. Waits 2 seconds")
    print("4. Transfers to +17543670370")
else:
    print("Code already updated or pattern not found")

print("\n" + "="*60)
print("TEST NOW")
print("="*60)
print("Call: +18135478530")
print("You should hear the greeting before transfer!")
print("="*60)
