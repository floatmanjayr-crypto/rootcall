from app.database import SessionLocal
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig

db = SessionLocal()

print("="*60)
print("DEBUGGING CONFIG ISSUE")
print("="*60)

# Check user 1
user = db.query(User).filter(User.id == 1).first()
print(f"\nUser 1: {user.email if user else 'NOT FOUND'}")

# Check phones for user 1
phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == 1).all()
print(f"\nPhones for user 1: {len(phones)}")
for p in phones:
    print(f"  - {p.phone_number} (ID: {p.id})")

# Check configs
configs = db.query(BadBotConfig).all()
print(f"\nAll BadBot Configs: {len(configs)}")
for c in configs:
    phone = db.query(PhoneNumber).filter(PhoneNumber.id == c.phone_number_id).first()
    print(f"  Config {c.id}:")
    print(f"    Phone Number ID: {c.phone_number_id}")
    print(f"    User ID: {c.user_id}")
    print(f"    Client Name: {c.client_name}")
    if phone:
        print(f"    Phone: {phone.phone_number}")
        print(f"    Phone User ID: {phone.user_id}")

# Try to replicate the query
print("\n" + "="*60)
print("REPLICATING API QUERY")
print("="*60)

phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == 1).first()
print(f"\nFirst phone for user 1: {phone.phone_number if phone else 'NONE'}")

if phone:
    config = db.query(BadBotConfig).filter(BadBotConfig.phone_number_id == phone.id).first()
    print(f"Config for phone {phone.id}: {config.client_name if config else 'NOT FOUND'}")
    
    if not config:
        print("\n❌ PROBLEM: No config found for this phone!")
        print("Creating config now...")
        
        new_config = BadBotConfig(
            phone_number_id=phone.id,
            user_id=1,
            client_name="Test User",
            client_cell="+17543670370",
            sms_alerts_enabled=True,
            alert_on_spam=True,
            alert_on_unknown=True,
            auto_block_spam=True,
            is_active=True,
            trusted_contacts=[]
        )
        db.add(new_config)
        db.commit()
        print("✓ Config created!")

db.close()
print("\n" + "="*60)
