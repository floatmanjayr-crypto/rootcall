with open('app/main.py', 'r') as f:
    content = f.read()

# Fix the conflicting imports
old_imports = '''from app.routers.badbot_telnyx import router as badbot_router
app.include_router(badbot_router)
# ===== BadBot Call Screening =====
from app.routers.badbot_screen import router as badbot_router
app.include_router(badbot_router)'''

new_imports = '''from app.routers.badbot_telnyx import router as badbot_telnyx_router
app.include_router(badbot_telnyx_router)
# ===== BadBot Call Screening =====
from app.routers.badbot_screen import router as badbot_screen_router
app.include_router(badbot_screen_router)'''

content = content.replace(old_imports, new_imports)

with open('app/main.py', 'w') as f:
    f.write(content)

print("Fixed conflicting router names!")
print("Server will auto-reload...")
