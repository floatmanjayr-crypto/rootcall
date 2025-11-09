# -*- coding: utf-8 -*-
"""
Quick Stripe Setup Checker
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*60)
print("STRIPE CONFIGURATION CHECKER")
print("="*60 + "\n")

configs = {
    "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY"),
    "STRIPE_BASIC_PRICE_ID": os.getenv("STRIPE_BASIC_PRICE_ID"),
    "STRIPE_SMART_PRICE_ID": os.getenv("STRIPE_SMART_PRICE_ID"),
    "STRIPE_PREMIUM_PRICE_ID": os.getenv("STRIPE_PREMIUM_PRICE_ID"),
}

all_good = True

for key, value in configs.items():
    if not value or value.startswith("sk_test_...") or value.startswith("price_"):
        print(f"X {key}: NOT SET")
        all_good = False
    else:
        if key == "STRIPE_SECRET_KEY":
            display = value[:15] + "..." if len(value) > 15 else value
        else:
            display = value[:20] + "..." if len(value) > 20 else value
        print(f"OK {key}: {display}")

print("\n" + "="*60)

if all_good:
    print("ALL STRIPE KEYS CONFIGURED!")
    print("\nYou're ready to test payments!")
    print("Test URL: http://localhost:8000/static/shield-pricing.html")
else:
    print("SETUP INCOMPLETE")
    print("\nTo complete setup:")
    print("1. Go to https://dashboard.stripe.com/test/products")
    print("2. Create 3 products")
    print("3. Copy each Price ID")
    print("4. Add to your .env file")

print("="*60 + "\n")
