# -*- coding: utf-8 -*-
"""
Fix badbot_portal router prefix
"""

with open('app/main.py', 'r') as f:
    content = f.read()

# Remove the prefix="/api/v1" from badbot_portal router
old_line = 'app.include_router(badbot_portal.router, prefix="/api/v1")'
new_line = 'app.include_router(badbot_portal.router)'

if old_line in content:
    content = content.replace(old_line, new_line)
    print("✓ Fixed router prefix")
    
    with open('app/main.py', 'w') as f:
        f.write(content)
    
    print("\nRouter will now be at: /api/badbot/*")
    print("Server will reload automatically")
else:
    print("Already fixed or different format")

