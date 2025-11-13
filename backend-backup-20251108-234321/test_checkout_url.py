# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import stripe

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

print("="*60)
print("TESTING STRIPE CHECKOUT URL")
print("="*60)

try:
    # Create a test session
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": os.getenv("STRIPE_SMART_PRICE_ID"),
            "quantity": 1
        }],
        mode="subscription",
        success_url="http://localhost:8000/static/client-portal.html?success=true",
        cancel_url="http://localhost:8000/static/shield-pricing.html?canceled=true",
    )
    
    print(f"\nCheckout Session Created:")
    print(f"  Session ID: {session.id}")
    print(f"  Status: {session.status}")
    print(f"  Payment Status: {session.payment_status}")
    print(f"\nCheckout URL:")
    print(session.url)
    print("\n" + "="*60)
    print("Copy the URL above and paste it in an INCOGNITO browser window")
    print("(Sometimes cookies/cache can cause issues)")
    print("="*60)
    
    # Also check if we can retrieve the session
    print("\nVerifying session can be retrieved...")
    retrieved = stripe.checkout.Session.retrieve(session.id)
    print(f"✅ Session retrieved successfully: {retrieved.id}")
    
except stripe.error.InvalidRequestError as e:
    print(f"\n❌ Invalid Request Error:")
    print(f"   {str(e)}")
    print("\nPossible issues:")
    print("- Price ID might be invalid")
    print("- Price might be archived in Stripe")
    print("- Check if price exists: https://dashboard.stripe.com/test/prices")
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    print(f"   Type: {type(e).__name__}")

print("")
