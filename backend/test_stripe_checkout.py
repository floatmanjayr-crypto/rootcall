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
        "Essential": os.getenv("STRIPE_ESSENTIAL_PRICE_ID"),
        "Family": os.getenv("STRIPE_FAMILY_PRICE_ID"),
        "Guardian": os.getenv("STRIPE_GUARDIAN_PRICE_ID")
    }

    print("Checking prices:")
    for name, price_id in price_ids.items():
        try:
            price = stripe.Price.retrieve(price_id)
            amount = price.unit_amount / 100
            print(f"‚úÖ {name}: ${amount:.2f}/month (ID: {price_id})")
        except Exception as e:
            print(f"‚ùå {name}: {str(e)}")

    print()
    print("Creating test checkout session...")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_ids["Family"], "quantity": 1}],
        mode="subscription",
        success_url="https://getrootcall.com/success.html?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://getrootcall.com/",
    )

    print(f"‚úÖ Checkout session created!")
    print(f"Session ID: {session.id}")
    print(f"URL: {session.url}")
    print()
    print("Ì¥ó Copy this URL and paste in browser:")
    print(session.url)

except Exception as e:
    print(f"‚ùå ERROR: {str(e)}")
    print()
    print("Common issues:")
    print("1. Price IDs from different Stripe account")
    print("2. Using live prices with test key")
    print("3. Check you're in TEST mode in Stripe dashboard")

print("="*60)
