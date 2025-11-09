# -*- coding: utf-8 -*-
"""
Final SMS fix - just remove from_number from calls
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Replace all send_sms_alert calls to only use 2 params
content = content.replace(
    'await send_sms_alert(to_number=client_cell, message=f"[BadBot] Unknown caller {cnam or from_num} being screened", from_number=to_num)',
    'await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened")'
)

content = content.replace(
    'await send_sms_alert(to_number=client_cell, message=f"[BadBot] SPAM BLOCKED: {cnam or from_num}", from_number=to_num)',
    'await send_sms_alert(client_cell, f"[BadBot] SPAM BLOCKED: {cnam or from_num}")'
)

content = content.replace(
    'await send_sms_alert(to_number=client_cell, message=f"[BadBot] Trusted contact {cnam or from_num} calling", from_number=to_num)',
    'await send_sms_alert(client_cell, f"[BadBot] Trusted contact {cnam or from_num} calling")'
)

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("Fixed all SMS calls!")
print("Server will reload - call +18135478530 now!")

