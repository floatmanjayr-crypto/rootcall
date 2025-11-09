with open('app/services/client_config.py', 'r') as f:
    content = f.read()

# Fix the query - badbot_config is a relationship that returns a list
old_code = '''        if phone and phone.badbot_config:
            config = phone.badbot_config
            # Convert database model to dict format expected by screening logic'''

new_code = '''        if phone:
            # Query BadBotConfig directly
            config = db.query(BadBotConfig).filter(
                BadBotConfig.phone_number_id == phone.id
            ).first()
            
            if not config:
                log.warning(f"[DB CONFIG] No BadBot config found for phone {phone.id}")
                return None
            
            # Convert database model to dict format expected by screening logic'''

content = content.replace(old_code, new_code)

with open('app/services/client_config.py', 'w') as f:
    f.write(content)

print("Fixed! Server will reload.")
