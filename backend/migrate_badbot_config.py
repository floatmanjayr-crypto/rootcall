# -*- coding: utf-8 -*-
"""
Migrate Hardcoded BadBot Config to Database
Run once: python migrate_rootcall_config.py

Moves your hardcoded CLIENT_LINES configuration into the database
"""
import sys
sys.path.append(".")

from app.database import SessionLocal
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import BadBotConfig
from app.models.user import User

# Your current hardcoded config
CLIENT_LINES = {
    "+18135478218": {
        "client_cell": "+17543314009",
        "client_name": "Primary Senior Client",
        "retell_agent_id": "agent_cde1ba4c8efa2aba5665a77b91",
        "retell_did": "+18135478218",
        "trusted_contacts": [
            # Add your trusted numbers here:
            # "+17545551234",  # Family member
            # "+18005551234",  # Doctor
        ],
        "caregiver_cell": ""  # Optional: SMS alert number
    }
}

def migrate_config():
    db = SessionLocal()
    
    try:
        for phone_number, config in CLIENT_LINES.items():
            print(f"\nChecking {phone_number}...")
            
            # Find phone number in database
            phone = db.query(PhoneNumber).filter(
                PhoneNumber.phone_number == phone_number
            ).first()
            
            if not phone:
                print(f"ERROR: Phone number {phone_number} not found in database")
                print(f"       Please create it first or check the number format")
                continue
            
            # Check if config already exists
            existing = db.query(BadBotConfig).filter(
                BadBotConfig.phone_number_id == phone.id
            ).first()
            
            if existing:
                print(f"WARNING: Config already exists for {phone_number}")
                print(f"         Updating existing config...")
                
                # Update existing config
                existing.client_name = config["client_name"]
                existing.client_cell = config["client_cell"]
                existing.retell_agent_id = config["retell_agent_id"]
                existing.retell_did = config["retell_did"]
                existing.trusted_contacts = config.get("trusted_contacts", [])
                existing.caregiver_cell = config.get("caregiver_cell", "")
                existing.is_active = True
                
            else:
                print(f"Creating new BadBot config...")
                
                # Create new config
                new_config = BadBotConfig(
                    phone_number_id=phone.id,
                    user_id=phone.user_id,
                    client_name=config["client_name"],
                    client_cell=config["client_cell"],
                    retell_agent_id=config["retell_agent_id"],
                    retell_did=config["retell_did"],
                    trusted_contacts=config.get("trusted_contacts", []),
                    caregiver_cell=config.get("caregiver_cell", ""),
                    sms_alerts_enabled=True,
                    alert_on_spam=True,
                    alert_on_unknown=False,
                    auto_block_spam=True,
                    is_active=True
                )
                
                db.add(new_config)
            
            db.commit()
            print(f"SUCCESS: Migrated config for {phone_number}")
            print(f"         Client: {config['client_name']}")
            print(f"         Transfer to: {config['client_cell']}")
            print(f"         Trusted contacts: {len(config.get('trusted_contacts', []))}")
        
        print("\n" + "="*50)
        print("Migration complete!")
        print("="*50)
        print("\nNext steps:")
        print("1. Test the API: GET /api/v1/badbot/portal/dashboard")
        print("2. Add trusted contacts via portal")
        print("3. Check that screening still works")
        
    except Exception as e:
        print(f"\nERROR during migration: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()

if __name__ == "__main__":
    print("="*50)
    print("BadBot Config Migration")
    print("="*50)
    print("\nThis will migrate your hardcoded CLIENT_LINES")
    print("configuration into the database.")
    print("\nWARNING: Make sure you've run the database migration first:")
    print("         alembic upgrade head")
    
    response = input("\nContinue? (y/n): ")
    
    if response.lower() == 'y':
        migrate_config()
    else:
        print("Migration cancelled")
