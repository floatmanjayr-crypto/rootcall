with open('app/main.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip_next = False

for line in lines:
    # Comment out badbot_telnyx import and include
    if 'from app.routers.badbot_telnyx' in line:
        new_lines.append('# ' + line)
        print(f"Commented: {line.strip()}")
    elif skip_next and 'app.include_router(badbot_router)' in line:
        new_lines.append('# ' + line)
        skip_next = False
        print(f"Commented: {line.strip()}")
    elif 'from app.routers.badbot_telnyx' in line:
        skip_next = True
        new_lines.append(line)
    else:
        if 'badbot_telnyx' in line:
            new_lines.append('# ' + line)
        else:
            new_lines.append(line)

with open('app/main.py', 'w') as f:
    f.writelines(new_lines)

print("\nFixed! Server will reload.")
