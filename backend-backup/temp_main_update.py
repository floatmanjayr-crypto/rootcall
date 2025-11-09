# Read main.py and check imports
with open('app/main.py', 'r') as f:
    content = f.read()

# Show current imports
print("Current imports in main.py:")
for line in content.split('\n'):
    if 'from app.routers import' in line:
        print(f"  {line}")

print("\n" + "="*60)
print("Checking which router files exist:")
import os
routers = []
for f in os.listdir('app/routers'):
    if f.endswith('.py') and f != '__init__.py':
        router_name = f.replace('.py', '')
        exists = os.path.exists(f'app/routers/{f}')
        print(f"  {router_name}: {'✓' if exists else '✗'}")
        if exists:
            routers.append(router_name)

print("\n" + "="*60)
print("Fix: Remove problematic import line from main.py")
print("Replace with individual working routers only")
