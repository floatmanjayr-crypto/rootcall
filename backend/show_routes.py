# -*- coding: utf-8 -*-
"""
Show all registered routes
"""
import sys
sys.path.insert(0, '.')

from app.main import app

print("="*60)
print("REGISTERED ROUTES")
print("="*60)

badbot_routes = []
other_routes = []

for route in app.routes:
    if hasattr(route, 'path'):
        if 'badbot' in route.path:
            badbot_routes.append(route.path)
        else:
            other_routes.append(route.path)

print("\nBadBot Routes:")
if badbot_routes:
    for path in sorted(badbot_routes):
        print(f"  {path}")
else:
    print("  NONE FOUND! This is the problem.")

print("\nOther Routes (sample):")
for path in sorted(other_routes)[:10]:
    print(f"  {path}")

print("\n" + "="*60)

if not badbot_routes:
    print("\nPROBLEM: badbot_portal routes not registered!")
    print("\nLet me check the router file...")
    
    try:
        from app.routers import badbot_portal
        print(f"Router prefix: {badbot_portal.router.prefix}")
        print(f"Number of routes: {len(badbot_portal.router.routes)}")
        
        print("\nRoutes in badbot_portal.router:")
        for route in badbot_portal.router.routes:
            if hasattr(route, 'path'):
                print(f"  {route.path}")
    except Exception as e:
        print(f"Error importing: {e}")

