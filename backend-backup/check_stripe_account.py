# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import stripe

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

print("="*60)
print("STRIPE ACCOUNT DIAGNOSIS")
print("="*60)

try:
    account = stripe.Account.retrieve()
    
    print(f"\nAccount ID: {account.id}")
    print(f"Country: {account.country}")
    print(f"Email: {account.email}")
    print(f"\nAccount Status:")
    print(f"  Charges enabled: {account.charges_enabled}")
    print(f"  Payouts enabled: {account.payouts_enabled}")
    print(f"  Details submitted: {account.details_submitted}")
    
    if hasattr(account, 'requirements'):
        print(f"\nRequirements:")
        if account.requirements.currently_due:
            print(f"  Currently due: {account.requirements.currently_due}")
        if account.requirements.errors:
            print(f"  Errors: {account.requirements.errors}")
    
    # Check if account can create checkout sessions
    print("\nTesting checkout session creation...")
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": os.getenv("STRIPE_FAMILY_PRICE_ID"),
            "quantity": 1
        }],
        mode="subscription",
        success_url="http://localhost:8000/success",
        cancel_url="http://localhost:8000/cancel"
    )
    
    print(f"  ✓ Session created: {session.id}")
    print(f"  ✓ Status: {session.status}")
    print(f"\n  Checkout URL: {session.url}")
    
    # Test if the URL is accessible
    print("\n  Try opening this URL in your browser:")
    print(f"  {session.url}")
    
    print("\n" + "="*60)
    print("DIAGNOSIS:")
    print("="*60)
    
    if not account.charges_enabled:
        print("\n⚠️  ISSUE: Charges are not enabled on your account")
        print("   FIX: Complete your Stripe account setup")
        print("   Go to: https://dashboard.stripe.com/account/onboarding")
    elif session.url.startswith('https://checkout.stripe.com'):
        print("\n✓ Checkout URL created successfully")
        print("  If you get 'Access Denied', this means:")
        print("  1. Your Stripe account needs verification")
        print("  2. Or you're in a restricted country")
        print("  3. Or account is limited")
        print("\n  Check your Stripe dashboard for any alerts:")
        print("  https://dashboard.stripe.com/test/dashboard")
    
except Exception as e:
    print(f"\n✗ ERROR: {str(e)}")
    print("\nPossible issues:")
    print("1. Account not fully set up")
    print("2. Missing business information")
    print("3. Account restrictions")
    print("\nCheck: https://dashboard.stripe.com/account")

print("="*60)
