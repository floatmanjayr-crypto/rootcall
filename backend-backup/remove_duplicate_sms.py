# -*- coding: utf-8 -*-
"""
Remove duplicate send_sms_alert function
"""

with open('app/routers/badbot_screen.py', 'r') as f:
    lines = f.readlines()

# Find and remove the second definition (non-async one at line 186)
new_lines = []
skip_until_next_function = False
in_bad_function = False

for i, line in enumerate(lines):
    line_num = i + 1
    
    # Found the bad function at line 186
    if line_num == 186 and 'def send_sms_alert' in line:
        print(f"Found bad function at line {line_num}, removing it...")
        in_bad_function = True
        skip_until_next_function = True
        continue
    
    # Skip lines until next function or class
    if skip_until_next_function:
        if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
            # Found next top-level item
            skip_until_next_function = False
            in_bad_function = False
        elif line.strip().startswith('def ') or line.strip().startswith('class ') or line.strip().startswith('async def'):
            skip_until_next_function = False
            in_bad_function = False
        else:
            continue
    
    new_lines.append(line)

with open('app/routers/badbot_screen.py', 'w') as f:
    f.writelines(new_lines)

print("Removed duplicate function!")
print("Server will reload - call +18135478530 now!")
print("\nSMS alerts should finally work!")

