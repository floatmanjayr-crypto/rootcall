# -*- coding: utf-8 -*-
"""
Fix duplicate SMS - only send once per call
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add a simple flag to track if SMS was sent for this call
# Find the screen_call function start
old_start = '''async def screen_call(request: Request, db: Session = Depends(get_db)):
    """BadBot call screening webhook"""
    body = await request.json()'''

new_start = '''# Track SMS sent per call to avoid duplicates
sms_sent_calls = set()

async def screen_call(request: Request, db: Session = Depends(get_db)):
    """BadBot call screening webhook"""
    body = await request.json()'''

content = content.replace(old_start, new_start)

# Modify SMS sending to check if already sent for this call
old_sms = '''        log.info("[SMS] Sending unknown caller alert to %s", client_cell)
        if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_unknown"):
            log.info("[SMS] Sending unknown caller alert to %s", client_cell)
            await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened")'''

new_sms = '''        # Send SMS only once per call
        if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_unknown"):
            if ccid not in sms_sent_calls:
                log.info("[SMS] Sending unknown caller alert to %s", client_cell)
                await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened")
                sms_sent_calls.add(ccid)
            else:
                log.info("[SMS] Alert already sent for this call")'''

if old_sms in content:
    content = content.replace(old_sms, new_sms)
    print("Fixed duplicate SMS issue")

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("\nFixed! SMS will only send once per call now.")
print("Test by calling +18135478530 - James gets ONE SMS!")

