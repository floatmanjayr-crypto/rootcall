# -*- coding: utf-8 -*-
"""
Setup RootCall Config for Current Working Number
Run once to configure your existing +18135478218 number
"""
import sys
sys.path.append(".")

from app.database import SessionLocal
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig
from app.models.user import User

# Your current working configuration
ROOTCALL_NUMBER = "+18135478218"
CLIENT_CELL = "+17543314009"
CLIENT_NAME = "Primary Senior Client"
RETELL_AGENT_ID = "agent_cde1ba4c8efa2aba5665a77b91"
RETELL_DID = "+18135478218"

def setup_current_config():
    db = SessionLocal()
    
    try:
        print("="*50)
        print("Setting up RootCall for current number")
        print("="*50)
        print(f"\nRootCall Number: {ROOTCALL_NUMBER}")
        print(f"Client Cell: {CLIENT_CELL}")
        print(f"Client Name: {CLIENT_NAME}")
        print()
        
        # Find or create phone number
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == ROOTCALL_NUMBER
        ).first()
        
        if not phone:
            print("Phone number not in database. Creating...")
            
            # Get first user (or create if needed)
            user = db.query(User).first()
            if not user:
                print("ERROR: No users found in database")
                print("Please create a user first")
                return
            
            phone = PhoneNumber(
                user_id=user.id,
                phone_number=ROOTCALL_NUMBER,
                friendly_name=f"RootCall - {CLIENT_NAME}",
                country_code="US",
                is_active=True,
                monthly_cost=2.0
            )
            db.add(phone)
            db.flush()
            print(f"Created PhoneNumber: ID {phone.id}")
        else:
            print(f"Found existing phone: ID {phone.id}, User: {phone.user_id}")
        
        # Check if RootCallConfig exists
        existing = db.query(RootCallConfig).filter(
            RootCallConfig.phone_number_id == phone.id
        ).first()
        
        if existing:
            print("\nRootCallConfig already exists!")
            print(f"  Config ID: {existing.id}")
            print(f"  Client: {existing.client_name}")
            print(f"  Active: {existing.is_active}")
            
            response = input("\nUpdate existing config? (y/n): ")
            if response.lower() != 'y':
                print("Cancelled")
                return
            
            # Update existing
            existing.client_name = CLIENT_NAME
            existing.client_cell = CLIENT_CELL
            existing.retell_agent_id = RETELL_AGENT_ID
            existing.retell_did = RETELL_DID
            existing.is_active = True
            
            db.commit()
            print("\nSUCCESS: Updated existing config")
        
        else:
            print("\nCreating new RootCallConfig...")
            
            config = RootCallConfig(
                phone_number_id=phone.id,
                user_id=phone.user_id,
                client_name=CLIENT_NAME,
                client_cell=CLIENT_CELL,
                retell_agent_id=RETELL_AGENT_ID,
                retell_did=RETELL_DID,
                trusted_contacts=[],
                caregiver_cell="",
                sms_alerts_enabled=True,
                alert_on_spam=True,
                alert_on_unknown=False,
                auto_block_spam=True,
                is_active=True
            )
            
            db.add(config)
            db.commit()
            
            print("\nSUCCESS: RootCall configured!")
            print(f"  Config ID: {config.id}")
        
        print("\n" + "="*50)
        print("Setup Complete!")
        print("="*50)
        print("\nYou can now:")
        print("1. Start the server: uvicorn app.main:app --reload")
        print("2. Test dashboard: GET /api/v1/rootcall/portal/dashboard")
        print("3. Add trusted contacts via portal")
        print("4. View call history")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    
    finally:
        db.close()

if __name__ == "__main__":
    setup_current_config()
