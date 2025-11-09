with open('app/main.py', 'r') as f:
    lines = f.readlines()

new_lines = []
found_badbot_telnyx_import = False

for i, line in enumerate(lines):
    # Check if badbot_telnyx import is commented
    if '# from app.routers.badbot_telnyx' in line:
        found_badbot_telnyx_import = True
        new_lines.append(line)
    # If the import is commented and we find the include_router, comment it too
    elif found_badbot_telnyx_import and 'app.include_router(badbot_router)' in line and not line.strip().startswith('#'):
        new_lines.append('# ' + line)
        found_badbot_telnyx_import = False  # Only comment the first one
        print(f"Commented line {i}: {line.strip()}")
    else:
        new_lines.append(line)

with open('app/main.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed!")
