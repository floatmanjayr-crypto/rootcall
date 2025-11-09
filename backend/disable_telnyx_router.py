with open('app/main.py', 'r') as f:
    content = f.read()

# Comment out badbot_telnyx router
content = content.replace(
    'from app.routers.badbot_telnyx import router as badbot_telnyx_router',
    '# from app.routers.badbot_telnyx import router as badbot_telnyx_router'
)

content = content.replace(
    'app.include_router(badbot_telnyx_router)',
    '# app.include_router(badbot_telnyx_router)  # DISABLED - has auth'
)

with open('app/main.py', 'w') as f:
    f.write(content)

print("Disabled badbot_telnyx router!")
