# -*- coding: utf-8 -*-
"""
Fix main.py to include badbot_portal router
"""

with open('app/main.py', 'r') as f:
    content = f.read()

print("Current routers:")
if 'include_router' in content:
    for line in content.split('\n'):
        if 'include_router' in line:
            print(f"  {line.strip()}")

# Add badbot_portal import if not exists
if 'from app.routers import badbot_portal' not in content and 'import badbot_portal' not in content:
    print("\nAdding badbot_portal import...")
    
    # Find where to add import
    if 'from app.routers import badbot_screen' in content:
        content = content.replace(
            'from app.routers import badbot_screen',
            'from app.routers import badbot_screen, badbot_portal'
        )
    elif 'from app.routers import' in content:
        content = content.replace(
            'from app.routers import',
            'from app.routers import badbot_portal,'
        )
    else:
        # Add new import line
        content = content.replace(
            'from fastapi import FastAPI',
            'from fastapi import FastAPI\nfrom app.routers import badbot_portal'
        )
    print("✓ Added import")

# Add router include if not exists
if 'badbot_portal.router' not in content:
    print("Adding badbot_portal.router...")
    
    # Find where to add router
    if 'app.include_router(badbot_screen.router)' in content:
        content = content.replace(
            'app.include_router(badbot_screen.router)',
            'app.include_router(badbot_screen.router)\napp.include_router(badbot_portal.router)'
        )
    else:
        # Add after app creation
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'app = FastAPI' in line:
                # Find end of FastAPI() call
                j = i
                while ')' not in lines[j] or 'FastAPI' not in lines[i]:
                    j += 1
                lines.insert(j + 1, '\napp.include_router(badbot_portal.router)')
                break
        content = '\n'.join(lines)
    print("✓ Added router")

with open('app/main.py', 'w') as f:
    f.write(content)

print("\n✓ Fixed! Server will reload.")
print("\nNow test: python test_portal_api.py")

