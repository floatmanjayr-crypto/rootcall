# -*- coding: utf-8 -*-
"""
Add SMS alerts to the DTMF (button press) flow
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add SMS to spam blocking
old_spam = '''        if any(keyword in cnam.lower() for keyword in spam_keywords):
            log.warning("[SPAM] Blocked: %s (%s)", from_num, cnam)
            await telnyx_hangup(ccid)
            return {"status": "spam_blocked"}'''

new_spam = '''        if any(keyword in cnam.lower() for keyword in spam_keywords):
            log.warning("[SPAM] Blocked: %s (%s)", from_num, cnam)
            
            # Send SMS alert
            if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_spam"):
                await send_sms_alert(client_cell, f"[BadBot] SPAM BLOCKED: {cnam or from_num}", to_num)
            
            await telnyx_hangup(ccid)
            return {"status": "spam_blocked"}'''

if old_spam in content:
    content = content.replace(old_spam, new_spam)
    print("Added spam SMS alert")

# Add SMS when screening starts
old_screening = '''        # 3) Unknown caller - Screen them
        log.info("[SCREENING] Asking %s to identify themselves", from_num)
        await telnyx_gather_speak(
            ccid,
            "Hello, who is calling? Press 1 if this is a doctor or medical office. Press 2 if you are family. Press 3 for all other calls."
        )
        return {"status": "screening_started"}'''

new_screening = '''        # 3) Unknown caller - Screen them
        log.info("[SCREENING] Asking %s to identify themselves", from_num)
        
        # Alert client screening is happening
        if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_unknown"):
            await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened", to_num)
        
        await telnyx_gather_speak(
            ccid,
            "Hello, who is calling? Press 1 if this is a doctor or medical office. Press 2 if you are family. Press 3 for all other calls."
        )
        return {"status": "screening_started"}'''

if old_screening in content:
    content = content.replace(old_screening, new_screening)
    print("Added screening SMS alert")

# Add SMS for trusted contacts
old_trusted = '''        if from_num in trusted:
            log.info("[TRUSTED] Forwarding %s to %s", from_num, client_cell)
            await telnyx_transfer(ccid, client_cell)
            return {"status": "trusted_forwarded"}'''

new_trusted = '''        if from_num in trusted:
            log.info("[TRUSTED] Forwarding %s to %s", from_num, client_cell)
            
            # Alert about trusted contact
            if cfg.get("sms_alerts_enabled"):
                await send_sms_alert(client_cell, f"[BadBot] Trusted contact {cnam or from_num} calling", to_num)
            
            await telnyx_transfer(ccid, client_cell)
            return {"status": "trusted_forwarded"}'''

if old_trusted in content:
    content = content.replace(old_trusted, new_trusted)
    print("Added trusted contact SMS alert")

# Write back
with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("\nDone! Server will reload.")
print("\nNow call +18135478530 and James will get SMS!")

