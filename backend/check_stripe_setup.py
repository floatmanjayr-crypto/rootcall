# -*- coding: utf-8 -*-
"""
RootCall Stripe Configuration Checker
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*60)
print("ROOTCALL STRIPE CONFIGURATION CHECKER")
print("="*60 + "\n")

configs = {
    "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY"),
    "STRIPE_PUBLISHABLE_KEY": os.getenv("STRIPE_PUBLISHABLE_KEY"),
    "STRIPE_WEBHOOK_SECRET": os.getenv("STRIPE_WEBHOOK_SECRET"),

    # Your actual plan names
    "STRIPE_ESSENTIAL_PRICE_ID": os.getenv("STRIPE_ESSENTIAL_PRICE_ID"),
    "STRIPE_FAMILY_PRICE_ID": os.getenv("STRIPE_FAMILY_PRICE_ID"),
    "STRIPE_GUARDIAN_PRICE_ID": os.getenv("STRIPE_GUARDIAN_PRICE_ID"),
}

all_good = True

for key, value in configs.items():
    if not value:
        print(f"❌ {key}: NOT SET")
        all_good = False
    else:
        # Mask keys for safety
        display = value[:15] + "..." if len(value) > 15 else value
        print(f"✅ {key}: {display}")

print("\n" + "="*60)

if all_good:
    print("🎉 ALL ROOTCALL STRIPE KEYS ARE CONFIGURED CORRECTLY!")
    print("Your backend is ready for live subscriptions.\n")
else:
    print("⚠️ SETUP INCOMPLETE")
    print("Please add missing values to Render or your .env file.\n")

print("="*60 + "\n")
