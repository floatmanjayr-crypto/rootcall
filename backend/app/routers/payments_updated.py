from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from pydantic import BaseModel
import stripe
import os

router = APIRouter(prefix="/api/payments", tags=["Payments"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

PRICE_MAP = {
    "essential": os.getenv("STRIPE_ESSENTIAL_PRICE_ID"),
    "family": os.getenv("STRIPE_FAMILY_PRICE_ID"),
    "guardian": os.getenv("STRIPE_GUARDIAN_PRICE_ID")
}

class CreateCheckout(BaseModel):
    tier: str
    user_id: int

@router.post("/create-checkout")
async def create_checkout_session(data: CreateCheckout, db: Session = Depends(get_db)):
    """Create Stripe checkout session"""
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    price_id = PRICE_MAP.get(data.tier)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=user.email,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url='https://getrootcall.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://getrootcall.com/',
            metadata={
                'user_id': str(data.user_id),
                'tier': data.tier
            }
        )
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
