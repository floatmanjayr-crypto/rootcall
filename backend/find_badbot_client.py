# -*- coding: utf-8 -*-
"""
Find which client has BadBot config
"""
from app.database import SessionLocal
from app.models.rootcall_config import RootCallConfig
from app.models.phone_number import PhoneNumber
from app.models.user import User

db = SessionLocal()

print("="*60)
print("BADBOT CONFIGURATIONS")
print("="*60)

configs = db.query(BadBotConfig).all()

if not configs:
    print("\nNo BadBot configs found!")
else:
    for cfg in configs:
        phone = db.query(PhoneNumber).filter(PhoneNumber.id == cfg.phone_number_id).first()
        if phone:
            user = db.query(User).filter(User.id == phone.user_id).first()
            
            print(f"\nConfig ID: {cfg.id}")
            print(f"Client: {cfg.client_name}")
            print(f"Phone: {phone.phone_number}")
            print(f"User ID: {phone.user_id}")
            if user:
                print(f"User Email: {user.email}")
            
            print(f"\nUse this in portal HTML:")
            print(f"  const CLIENT_ID = {phone.user_id};")

db.close()
print("\n" + "="*60)

