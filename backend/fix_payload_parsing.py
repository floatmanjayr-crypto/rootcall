with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Fix the from/to parsing to handle both string and dict formats
old_parsing = '''    from_num = (payload.get("from") or {}).get("phone_number", "")
    to_num = (payload.get("to") or {}).get("phone_number", "")'''

new_parsing = '''    # Handle both string and dict formats for from/to
    from_field = payload.get("from", "")
    to_field = payload.get("to", "")
    
    if isinstance(from_field, dict):
        from_num = from_field.get("phone_number", "")
    else:
        from_num = str(from_field)
    
    if isinstance(to_field, dict):
        to_num = to_field.get("phone_number", "")
    else:
        to_num = str(to_field)'''

content = content.replace(old_parsing, new_parsing)

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("Fixed payload parsing! Server will reload.")
