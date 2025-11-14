# -*- coding: utf-8 -*-
"""
Check and enable SMS alerts for BadBot config
"""
from app.database import SessionLocal
from app.models.rootcall_config import RootCallConfig
from app.models.phone_number import PhoneNumber

db = SessionLocal()

print("="*60)
print("BADBOT SMS ALERT CONFIGURATION")
print("="*60)

# Find James's config
phone = db.query(PhoneNumber).filter(
    PhoneNumber.phone_number == "+18135478530"
).first()

if phone:
    config = db.query(BadBotConfig).filter(
        BadBotConfig.phone_number_id == phone.id
    ).first()
    
    if config:
        print(f"\nClient: {config.client_name}")
        print(f"Client Cell: {config.client_cell}")
        print(f"\nCurrent Alert Settings:")
        print(f"  SMS Alerts Enabled: {config.sms_alerts_enabled}")
        print(f"  Alert on Spam: {config.alert_on_spam}")
        print(f"  Alert on Unknown: {config.alert_on_unknown}")
        
        # Enable all alerts if not already
        if not config.sms_alerts_enabled or not config.alert_on_spam or not config.alert_on_unknown:
            print("\nEnabling all SMS alerts...")
            config.sms_alerts_enabled = True
            config.alert_on_spam = True
            config.alert_on_unknown = True
            db.commit()
            print("UPDATED!")
        else:
            print("\nAll alerts already enabled!")
        
        print("\n" + "="*60)
        print("TEST ALERTS")
        print("="*60)
        print("\n1. Call +18135478530 from unknown number")
        print("   -> James gets: '[BadBot] Unknown caller being screened'")
        print("\n2. Have spam number call")
        print("   -> James gets: '[BadBot] SPAM BLOCKED: ...'")
        print("\n3. Add trusted contact and call")
        print("   -> James gets: '[BadBot] Trusted contact calling'")
        print("="*60)
    else:
        print("No BadBot config found!")
else:
    print("Phone number not found!")

db.close()

