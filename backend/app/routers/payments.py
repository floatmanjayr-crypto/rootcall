from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from pydantic import BaseModel
import os
import logging

import stripe
from stripe.checkout import Session as StripeCheckoutSession  # ⬅️ DIRECT import

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Payments"])

# ---------- Stripe config ----------
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if not STRIPE_SECRET_KEY:
    log.error("STRIPE_SECRET_KEY is NOT set in environment")
else:
    stripe.api_key = STRIPE_SECRET_KEY

PRICE_MAP = {
    "essential": os.getenv("STRIPE_ESSENTIAL_PRICE_ID"),
    "family": os.getenv("STRIPE_FAMILY_PRICE_ID"),
    "guardian": os.getenv("STRIPE_GUARDIAN_PRICE_ID"),
}


class CreateCheckout(BaseModel):
    tier: str
    user_id: int


@router.post("/create-checkout")
async def create_checkout_session(
    data: CreateCheckout,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create Stripe checkout session"""

    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured on server")

    price_id = PRICE_MAP.get(data.tier)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid or misconfigured tier")

    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.email:
        raise HTTPException(status_code=400, detail="User has no email")

    try:
        origin = request.headers.get("origin") or "https://getrootcall.com"

        # ✅ Use the directly imported Session class (no stripe.checkout)
        checkout_session = StripeCheckoutSession.create(
            customer_email=user.email,
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{origin}/success.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/",
            metadata={
                "user_id": str(data.user_id),
                "tier": data.tier,
            },
        )

        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
        }

    except Exception as e:
        log.exception("Stripe checkout failed")
        raise HTTPException(status_code=500, detail=str(e))
