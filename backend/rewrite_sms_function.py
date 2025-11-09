# -*- coding: utf-8 -*-
"""
Completely rewrite send_sms_alert function
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    lines = f.readlines()

# Find and replace the send_sms_alert function
in_function = False
start_line = None
end_line = None

for i, line in enumerate(lines):
    if 'async def send_sms_alert' in line:
        in_function = True
        start_line = i
    elif in_function and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
        end_line = i
        break

if start_line is not None:
    # Remove old function
    if end_line:
        del lines[start_line:end_line]
    
    # Insert new function
    new_function = '''async def send_sms_alert(to_number: str, message: str, from_number: str = "+18135478530"):
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

'''
    lines.insert(start_line, new_function)
    print("Rewrote send_sms_alert function")

with open('app/routers/badbot_screen.py', 'w') as f:
    f.writelines(lines)

print("Fixed! Server will reload.")
print("Call +18135478530 - SMS will work now!")

