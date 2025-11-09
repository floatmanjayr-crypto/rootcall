# -*- coding: utf-8 -*-
"""
Properly add SMS alerts to badbot_screen.py
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Check if SMS function exists
if 'async def send_sms_alert' not in content:
    print("Adding send_sms_alert function...")
    
    sms_function = '''
async def send_sms_alert(to_number: str, message: str, from_number: str = None):
    """Send SMS alert to client or caregiver"""
    if DRY_RUN:
        log.info("[DRY_RUN] SMS to %s: %s", to_number, message)
        return True
    
    if not TELNYX_API_KEY or not to_number:
        log.warning("[SMS] Missing API key or phone number")
        return False
    
    if not from_number:
        from_number = "+18135478530"
    
    url = "https://api.telnyx.com/v2/messages"
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {TELNYX_API_KEY}"},
                json={
                    "from": from_number,
                    "to": to_number,
                    "text": message
                }
            )
            log.info("[SMS] Sent to %s: status %s", to_number, r.status_code)
            return r.status_code in [200, 201, 202]
        except Exception as e:
            log.error("[SMS] Error: %s", e)
            return False

'''
    
    # Insert after log declaration
    insert_after = 'log = logging.getLogger("badbot")'
    content = content.replace(insert_after, insert_after + sms_function)
    print("OK: SMS function added")
else:
    print("SMS function already exists")

# Add SMS to spam blocking
if 'SPAM BLOCKED' not in content:
    print("\nAdding SMS to spam blocking...")
    old = 'await telnyx_hangup(ccid)'
    new = '''# Alert client about spam
            if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_spam"):
                await send_sms_alert(client_cell, f"[BadBot] SPAM BLOCKED: {cnam or from_num}", to_num)
            
            await telnyx_hangup(ccid)'''
    
    # Find first occurrence in spam section
    if old in content:
        parts = content.split(old, 1)
        if len(parts) == 2:
            content = parts[0] + new + parts[1]
            print("OK: Spam alert added")

# Write back
with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("\nDone! Server will reload.")
print("Call +18135478530 to test SMS alerts!")

