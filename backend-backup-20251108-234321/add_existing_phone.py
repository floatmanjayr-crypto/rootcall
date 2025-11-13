from app.database import SessionLocal
from app.models import User, PhoneNumber
from datetime import datetime

db = SessionLocal()

user = db.query(User).filter(User.username == "testuser").first()
if not user:
    print("User 'testuser' not found!")
    exit()

print(f"Found user: {user.username} (ID: {user.id})")

existing = db.query(PhoneNumber).filter(PhoneNumber.phone_number == "+18339370862").first()

if existing:
    print(f"Phone already exists in DB! Updating...")
    existing.user_id = user.id
    existing.is_active = True
    existing.telnyx_connection_id = "2809979059520407054"
    db.commit()
    print(f"✅ Updated +18339370862 for {user.username}")
else:
    phone = PhoneNumber(
        user_id=user.id,
        phone_number="+18339370862",
        friendly_name="Main Phone",
        country_code="US",
        telnyx_connection_id="2809979059520407054",
        is_active=True,
        monthly_cost=1.0,
        purchased_at=datetime.utcnow()
    )
    db.add(phone)
    db.commit()
    print(f"✅ Added +18339370862 to database for {user.username}")

db.close()
