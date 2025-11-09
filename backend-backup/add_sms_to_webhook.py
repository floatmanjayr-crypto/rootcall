# -*- coding: utf-8 -*-
"""
Add SMS alerts to BadBot webhook
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add SMS function if not exists
if 'async def send_sms_alert' not in content:
    sms_function = '''
async def send_sms_alert(to_number: str, message: str, from_number: str = None):
    """Send SMS alert to client or caregiver"""
    if DRY_RUN:
        log.info("[DRY_RUN] SMS to %s: %s", to_number, message)
        return True
    
    if not TELNYX_API_KEY or not to_number:
        return False
    
    # Use first available BadBot number as sender if not specified
    if not from_number:
        from_number = "+18135478530"  # Default BadBot number
    
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
            log.info("SMS sent to %s: %s", to_number, r.status_code)
            return r.status_code in [200, 201, 202]
        except Exception as e:
            log.error("SMS error: %s", e)
            return False

'''
    
    # Insert SMS function after imports
    content = content.replace(
        'log = logging.getLogger("badbot")',
        'log = logging.getLogger("badbot")\n' + sms_function
    )

# Add SMS alert when spam is blocked
old_spam = '''        if any(keyword in cnam.lower() for keyword in spam_keywords):
            log.warning("[SPAM] Blocked: %s (%s)", from_num, cnam)
            send_sms_alert(client_cell, f"[BadBot] Blocked spam: {from_num}")
            if caregiver:
                send_sms_alert(caregiver, f"[BadBot] Blocked spam for client: {from_num}")
            await telnyx_hangup(ccid)
            return {"status": "spam_blocked", "from": from_num}'''

new_spam = '''        if any(keyword in cnam.lower() for keyword in spam_keywords):
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
            return {"status": "spam_blocked", "from": from_num}'''

if old_spam in content:
    content = content.replace(old_spam, new_spam)

# Add SMS alert for unknown callers sent to screening
old_unknown = '''        # 3) Unknown -> Send to Retell agent for screening
        if retell_did:
            log.info("[UNKNOWN] Sending %s to Retell agent for screening: %s", from_num, retell_did)
            result = await telnyx_transfer(ccid, retell_did)
            return {"status": "sent_to_retell_screening", "from": from_num, "retell_did": retell_did}'''

new_unknown = '''        # 3) Unknown -> Send to Retell agent for screening
        if retell_did:
            log.info("[UNKNOWN] Sending %s to Retell agent for screening: %s", from_num, retell_did)
            
            # Send alert if enabled
            if cfg.get("sms_alerts_enabled") and cfg.get("alert_on_unknown"):
                await send_sms_alert(
                    client_cell,
                    f"[BadBot] Unknown caller {cnam or from_num} being screened by AI",
                    to_num
                )
            
            result = await telnyx_transfer(ccid, retell_did)
            return {"status": "sent_to_retell_screening", "from": from_num, "retell_did": retell_did}'''

if old_unknown in content:
    content = content.replace(old_unknown, new_unknown)

# Add SMS for trusted contact
old_trusted = '''        if from_num in trusted:
            log.info("[TRUSTED] Forwarding %s to %s", from_num, client_cell)
            if client_cell:
                result = await telnyx_transfer(ccid, client_cell)
                return {"status": "trusted_forwarded", "from": from_num, "to": client_cell, "result": result}'''

new_trusted = '''        if from_num in trusted:
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
                return {"status": "trusted_forwarded", "from": from_num, "to": client_cell, "result": result}'''

if old_trusted in content:
    content = content.replace(old_trusted, new_trusted)

# Write updated file
with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("="*60)
print("SMS ALERTS ADDED TO WEBHOOK")
print("="*60)
print("\nAlerts will be sent for:")
print("1. Spam blocked (if alert_on_spam enabled)")
print("2. Unknown caller screening (if alert_on_unknown enabled)")
print("3. Trusted contact calling")
print("\nServer will auto-reload!")
print("="*60)

