# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import stripe

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

print("="*60)
print("TESTING STRIPE CHECKOUT")
print("="*60)

try:
    account = stripe.Account.retrieve()
    print(f"Connected to Stripe account: {account.id}")
    print()
    
    price_ids = {
        "Basic": os.getenv("STRIPE_BASIC_PRICE_ID"),
        "Smart": os.getenv("STRIPE_SMART_PRICE_ID"),
        "Premium": os.getenv("STRIPE_PREMIUM_PRICE_ID")
    }
    
    print("Checking prices:")
    for name, price_id in price_ids.items():
        try:
            price = stripe.Price.retrieve(price_id)
            amount = price.unit_amount / 100
            print(f"OK {name}: ${amount:.2f}/month")
        except Exception as e:
            print(f"ERROR {name}: {str(e)}")
    
    print()
    print("Creating test checkout session...")
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_ids["Smart"], "quantity": 1}],
        mode="subscription",
        success_url="http://localhost:8000/success",
        cancel_url="http://localhost:8000/cancel",
    )
    
    print(f"Checkout session created!")
    print(f"Session ID: {session.id}")
    print(f"URL: {session.url}")
    print()
    print("Copy this URL and paste in browser:")
    print(session.url)
    
except Exception as e:
    print(f"ERROR: {str(e)}")
    print()
    print("Common issues:")
    print("1. Price IDs from different Stripe account")
    print("2. Using live prices with test key")
    print("3. Check you're in TEST mode in Stripe dashboard")

print("="*60)
