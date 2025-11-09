# -*- coding: utf-8 -*-
"""
Add missing telnyx_speak function
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Check if telnyx_speak exists
if 'async def telnyx_speak' not in content:
    print("Adding telnyx_speak function...")
    
    speak_function = '''
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

'''
    
    # Insert before telnyx_transfer
    if 'async def telnyx_transfer' in content:
        content = content.replace('async def telnyx_transfer', speak_function + 'async def telnyx_transfer')
        print("Added telnyx_speak function")
    else:
        # Insert after send_sms_alert
        content = content.replace('async def send_sms_alert', speak_function + '\nasync def send_sms_alert')
        print("Added telnyx_speak function after send_sms_alert")

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("Fixed! Server will restart.")
print("Call +18135478530 again!")

