with open('app/main.py', 'r') as f:
    content = f.read()

# Fix the duplicate router names
old = '''from app.routers.badbot_telnyx import router as badbot_router
app.include_router(badbot_router)
# ===== BadBot Call Screening =====
from app.routers.badbot_screen import router as badbot_router
app.include_router(badbot_router)'''

new = '''from app.routers.badbot_telnyx import router as badbot_telnyx_router
app.include_router(badbot_telnyx_router)
# ===== BadBot Call Screening =====
from app.routers.badbot_screen import router as badbot_screen_router
app.include_router(badbot_screen_router)'''

if old in content:
    content = content.replace(old, new)
    with open('app/main.py', 'w') as f:
        f.write(content)
    print("Fixed! Server will reload.")
else:
    print("Pattern not found. Checking what's there...")
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'badbot' in line.lower():
            print(f"{i}: {line}")

