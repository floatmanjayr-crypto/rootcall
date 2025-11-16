with open('app/routers/auth.py', 'r') as f:
    lines = f.readlines()

new_lines = []
settings_imported = False

for line in lines:
    # Add settings import after 'import os'
    if line.strip() == 'import os' and not settings_imported:
        new_lines.append(line)
        new_lines.append('from app.config import settings\n')
        settings_imported = True
        continue
    
    # Skip if settings already imported
    if 'from app.config import settings' in line:
        settings_imported = True
        new_lines.append(line)
        continue
    
    # Replace SECRET_KEY definition
    if line.strip().startswith('SECRET_KEY = os.getenv'):
        new_lines.append('SECRET_KEY = settings.JWT_SECRET_KEY  # Use settings for consistency\n')
        continue
    
    # Replace ALGORITHM definition
    if line.strip() == 'ALGORITHM = "HS256"':
        new_lines.append('ALGORITHM = settings.JWT_ALGORITHM  # Use settings for consistency\n')
        continue
    
    # Keep everything else
    new_lines.append(line)

with open('app/routers/auth.py', 'w') as f:
    f.writelines(new_lines)

print("✅ Updated auth.py to use settings!")
