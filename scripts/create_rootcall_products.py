# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import stripe

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

print("Creating RootCall products in Stripe...\n")

plans = [
    {"name": "Essential", "price": 3900, "desc": "Solo protection for one line"},
    {"name": "Family", "price": 7900, "desc": "Protect up to 3 lines"},
    {"name": "Guardian", "price": 12900, "desc": "Maximum protection + white-glove setup"}
]

price_ids = {}

for plan in plans:
    try:
        # Create product
        product = stripe.Product.create(
            name=f"RootCall {plan['name']}",
            description=plan['desc']
        )
        
        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=plan['price'],
            currency='usd',
            recurring={'interval': 'month'}
        )
        
        print(f"✓ Created {plan['name']}: ${plan['price']/100:.2f}/month")
        print(f"  Price ID: {price.id}\n")
        
        price_ids[plan['name'].lower()] = price.id
        
    except Exception as e:
        print(f"✗ Error creating {plan['name']}: {str(e)}\n")

print("="*60)
print("Add these to your .env file:")
print("="*60)
print(f"STRIPE_ESSENTIAL_PRICE_ID={price_ids.get('essential', 'NOT_CREATED')}")
print(f"STRIPE_FAMILY_PRICE_ID={price_ids.get('family', 'NOT_CREATED')}")
print(f"STRIPE_GUARDIAN_PRICE_ID={price_ids.get('guardian', 'NOT_CREATED')}")
print("="*60)
