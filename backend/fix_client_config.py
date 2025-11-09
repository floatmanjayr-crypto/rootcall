import os

config_file = 'app/services/client_config.py'

if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        content = f.read()
    
    # The function is probably returning a list instead of a dict
    # Let's check what's there
    print("Current client_config.py:")
    print(content)
    print("\n" + "="*60)
    print("Need to see this to fix it!")
else:
    print("client_config.py not found!")
    print("Creating a simple one...")
    
    new_config = '''"""Client configuration service"""
from app.database import SessionLocal
from app.models import PhoneNumber, BadBotConfig

def get_client_config(phone_number: str) -> dict:
    """Get client configuration for a phone number"""
    db = SessionLocal()
    try:
        # Find the phone number
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == phone_number
        ).first()
        
        if not phone:
            return {}
        
        # Get BadBot config
        config = db.query(BadBotConfig).filter(
            BadBotConfig.phone_number_id == phone.id
        ).first()
        
        if not config:
            return {}
        
        # Return as dict
        return {
            "client_cell": config.client_cell,
            "client_name": config.client_name,
            "trusted_contacts": config.trusted_contacts or [],
            "retell_did": config.retell_did,
            "caregiver_cell": config.caregiver_cell,
            "sms_alerts_enabled": config.sms_alerts_enabled,
        }
    finally:
        db.close()
'''
    
    with open(config_file, 'w') as f:
        f.write(new_config)
    
    print("Created new client_config.py!")
