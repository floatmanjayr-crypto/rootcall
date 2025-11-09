from app.database import SessionLocal
from app.models import User, PhoneNumber

db = SessionLocal()

# Find your user
user = db.query(User).filter(User.username == "testuser").first()
if not user:
    print("User 'testuser' not found!")
    exit()

print(f"Found user: {user.username} (ID: {user.id})")
print()

# Check all phone numbers in database
all_phones = db.query(PhoneNumber).all()

if not all_phones:
    print("No phone numbers in database!")
    print("\nYou need to purchase a phone number first.")
else:
    print(f"Available phone numbers ({len(all_phones)}):")
    for p in all_phones:
        owner = "Unassigned" if not p.user_id else f"User ID: {p.user_id}"
        print(f"  - {p.phone_number} | {owner} | Active: {p.is_active}")
    
    # Assign the phone to testuser
    phone = db.query(PhoneNumber).filter(PhoneNumber.phone_number == "+18339370862").first()
    
    if phone:
        phone.user_id = user.id
        phone.is_active = True
        db.commit()
        print(f"\nAssigned {phone.phone_number} to {user.username}")
    else:
        # Assign any available phone
        any_phone = db.query(PhoneNumber).first()
        if any_phone:
            any_phone.user_id = user.id
            any_phone.is_active = True
            db.commit()
            print(f"\nAssigned {any_phone.phone_number} to {user.username}")

db.close()
