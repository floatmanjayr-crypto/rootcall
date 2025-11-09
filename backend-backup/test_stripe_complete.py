# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import stripe

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

print("="*60)
print("COMPLETE STRIPE CHECKOUT TEST")
print("="*60)

try:
    print("\n1. Testing Stripe API connection...")
    account = stripe.Account.retrieve()
    print(f"   Connected to: {account.id}")
    
    print("\n2. Checking price IDs...")
    price_ids = {
        "essential": os.getenv("STRIPE_ESSENTIAL_PRICE_ID") or os.getenv("STRIPE_BASIC_PRICE_ID"),
        "family": os.getenv("STRIPE_FAMILY_PRICE_ID") or os.getenv("STRIPE_SMART_PRICE_ID"),
        "guardian": os.getenv("STRIPE_GUARDIAN_PRICE_ID") or os.getenv("STRIPE_PREMIUM_PRICE_ID")
    }
    
    for name, price_id in price_ids.items():
        if price_id:
            try:
                price = stripe.Price.retrieve(price_id)
                print(f"   OK {name}: ${price.unit_amount/100:.2f}/month")
            except Exception as e:
                print(f"   ERROR {name}: {str(e)}")
        else:
            print(f"   MISSING {name}: Not configured in .env")
    
    print("\n3. Creating test checkout session...")
    test_price_id = price_ids.get("family")
    
    if test_price_id:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": test_price_id, "quantity": 1}],
            mode="subscription",
            success_url="http://localhost:8000/static/client-portal.html?success=true",
            cancel_url="http://localhost:8000/static/index.html?canceled=true"
        )
        
        print(f"\n   Session created: {session.id}")
        print(f"   Status: {session.status}")
        print(f"\n   Checkout URL:")
        print(f"   {session.url}")
        print("\n   Copy this URL and paste in browser to test")
    else:
        print("   ERROR: No price ID found for testing")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

except Exception as e:
    print(f"\nERROR: {str(e)}")
    print("\nTroubleshooting:")
    print("1. Check .env has STRIPE_SECRET_KEY")
    print("2. Verify price IDs are correct")
    print("3. Make sure you're in TEST mode in Stripe")
