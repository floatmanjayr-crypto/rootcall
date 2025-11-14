from app.database import SessionLocal
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig

db = SessionLocal()

# Get phone ID 1 (+18339370862)
phone = db.query(PhoneNumber).filter(PhoneNumber.id == 1).first()

if phone:
    print(f"Creating config for {phone.phone_number}...")
    
    config = BadBotConfig(
        phone_number_id=1,
        user_id=1,
        client_name="Shield Number 1",
        client_cell="+17543670370",
        retell_agent_id="",  # Empty string instead of None
        retell_did="",
        sms_alerts_enabled=True,
        alert_on_spam=True,
        alert_on_unknown=True,
        auto_block_spam=True,
        is_active=True,
        trusted_contacts=[]
    )
    db.add(config)
    db.commit()
    print("✓ Config created!")
else:
    print("Phone not found")

db.close()
