# -*- coding: utf-8 -*-
"""
Fix send_sms_alert function signature
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Fix the function definition to accept 3 parameters
old_def = '''async def send_sms_alert(to_number: str, message: str, from_number: str = None):'''

# Already correct, but let's check the calls
# The issue is calls are: send_sms_alert(client_cell, message, to_num)
# Should be: send_sms_alert(to_number, message, from_number)

# Find and fix all calls
old_call = 'await send_sms_alert(client_cell, f"[BadBot] Unknown caller {cnam or from_num} being screened", to_num)'
new_call = 'await send_sms_alert(to_number=client_cell, message=f"[BadBot] Unknown caller {cnam or from_num} being screened", from_number=to_num)'

if old_call in content:
    content = content.replace(old_call, new_call)
    print("Fixed unknown caller SMS call")

# Fix spam alert call
old_spam = 'await send_sms_alert(client_cell, f"[BadBot] SPAM BLOCKED: {cnam or from_num}", to_num)'
new_spam = 'await send_sms_alert(to_number=client_cell, message=f"[BadBot] SPAM BLOCKED: {cnam or from_num}", from_number=to_num)'

if old_spam in content:
    content = content.replace(old_spam, new_spam)
    print("Fixed spam SMS call")

# Fix trusted contact call
old_trusted = 'await send_sms_alert(client_cell, f"[BadBot] Trusted contact {cnam or from_num} calling", to_num)'
new_trusted = 'await send_sms_alert(to_number=client_cell, message=f"[BadBot] Trusted contact {cnam or from_num} calling", from_number=to_num)'

if old_trusted in content:
    content = content.replace(old_trusted, new_trusted)
    print("Fixed trusted SMS call")

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("\nFixed! Server will reload.")
print("Call +18135478530 now - SMS should work!")

