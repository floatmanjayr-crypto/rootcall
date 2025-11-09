from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from pydantic import BaseModel
import os

router = APIRouter(tags=["Payments"])

class CreateCheckout(BaseModel):
    tier: str
    user_id: int

@router.post("/api/payments/create-checkout")
async def create_checkout_session(data: CreateCheckout, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "checkout_url": "https://checkout.stripe.com/demo",
        "message": "Stripe integration pending - add STRIPE_SECRET_KEY to .env"
    }

@router.get("/api/payments/plans")
async def get_plans():
    return [
        {
            "id": "basic",
            "name": "Basic Protection",
            "price": 34.99,
            "tier": "Tier 1",
            "color": "green",
            "features": [
                "Spam & spoof blocking",
                "Caller ID screening",
                "SMS fraud alerts",
                "Basic voicemail + forwarding",
                "1 Protected Number",
                "10 Trusted Contacts"
            ],
            "ideal_for": "Seniors or families protecting a single number"
        },
        {
            "id": "smart",
            "name": "Smart AI Screening",
            "price": 69.99,
            "tier": "Tier 2",
            "color": "blue",
            "popular": True,
            "features": [
                "Everything in Basic",
                "Live AI call screening",
                "Doctor/bank verification",
                "Safe scheduling + transfer",
                "Activity logs + reports",
                "1 Protected Number",
                "25 Trusted Contacts",
                "Email Alerts"
            ],
            "ideal_for": "Retirees, caregivers, or small businesses"
        },
        {
            "id": "premium",
            "name": "Premium Family Shield",
            "price": 124.99,
            "tier": "Tier 3",
            "color": "purple",
            "features": [
                "All Smart AI features",
                "Multi-number protection (5 lines)",
                "Custom AI voice",
                "Priority SMS/email alerts",
                "Auto-block list sync",
                "Call recording",
                "Monthly scam report PDF",
                "50 Trusted Contacts",
                "Priority Support"
            ],
            "ideal_for": "Families or professionals protecting multiple lines"
        }
    ]

@router.get("/api/payments/rootcall-plans")
async def get_rootcall_plans():
    """Get RootCall subscription plans"""
    return [
        {
            "id": "essential",
            "name": "Essential",
            "price": 39.00,
            "price_id": os.getenv("STRIPE_ESSENTIAL_PRICE_ID", os.getenv("STRIPE_BASIC_PRICE_ID")),
            "description": "Solo protection for one line",
            "features": [
                "AI answers & screens",
                "Spoof & scam blocking",
                "Verified call forwarding"
            ]
        },
        {
            "id": "family",
            "name": "Family",
            "price": 79.00,
            "price_id": os.getenv("STRIPE_FAMILY_PRICE_ID", os.getenv("STRIPE_SMART_PRICE_ID")),
            "description": "Protect up to 3 lines",
            "popular": True,
            "features": [
                "Everything in Essential",
                "Caregiver SMS alerts",
                "Priority screening queue"
            ]
        },
        {
            "id": "guardian",
            "name": "Guardian",
            "price": 129.00,
            "price_id": os.getenv("STRIPE_GUARDIAN_PRICE_ID", os.getenv("STRIPE_PREMIUM_PRICE_ID")),
            "description": "Maximum protection + white-glove setup",
            "features": [
                "Dedicated onboarding",
                "Expanded allow/deny lists",
                "Priority support"
            ]
        }
    ]
