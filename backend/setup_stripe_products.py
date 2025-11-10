# -*- coding: utf-8 -*-
import stripe
import os
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

print("Creating RootCall Stripe Products...")

# 1. Essential Plan - $9.99/month
essential = stripe.Product.create(
    name="RootCall Essential",
    description="Basic call screening for individuals",
)
essential_price = stripe.Price.create(
    product=essential.id,
    unit_amount=999,
    currency="usd",
    recurring={"interval": "month"},
)

# 2. Family Plan - $19.99/month
family = stripe.Product.create(
    name="RootCall Family",
    description="Protect up to 5 family members",
)
family_price = stripe.Price.create(
    product=family.id,
    unit_amount=1999,
    currency="usd",
    recurring={"interval": "month"},
)

# 3. Guardian Plan - $39.99/month
guardian = stripe.Product.create(
    name="RootCall Guardian",
    description="Enterprise-grade protection with priority support",
)
guardian_price = stripe.Price.create(
    product=guardian.id,
    unit_amount=3999,
    currency="usd",
    recurring={"interval": "month"},
)

print("\nProducts Created Successfully!\n")
print(f"STRIPE_ESSENTIAL_PRICE_ID={essential_price.id}")
print(f"STRIPE_FAMILY_PRICE_ID={family_price.id}")
print(f"STRIPE_GUARDIAN_PRICE_ID={guardian_price.id}")
print("\nCopy these to your .env and Render environment variables!")
