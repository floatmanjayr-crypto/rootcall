import logging
import os
import secrets
from urllib.parse import urlparse

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_active_user
from app.database import get_db
from app.models.onboarding import CustomerOnboarding
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.services.customer_onboarding import new_onboarding, next_url
from app.services.payment_verification import billing_summary, refresh_payment, stripe_data, verify_checkout

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
PRICE_MAP = {
    "essential": os.getenv("STRIPE_ESSENTIAL_PRICE_ID"),
    "family": os.getenv("STRIPE_FAMILY_PRICE_ID"),
    "guardian": os.getenv("STRIPE_GUARDIAN_PRICE_ID"),
}


def public_url():
    base = settings.APP_BASE_URL.rstrip("/")
    parsed = urlparse(base)
    if not parsed.netloc or parsed.scheme != "https" or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail="A public HTTPS APP_BASE_URL must be configured.")
    return base


class CreateCheckout(BaseModel):
    tier: str
    user_id: int | None = None


@router.post("/create-checkout")
def create_checkout_session(
    data: CreateCheckout, current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if data.user_id is not None and data.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot create checkout for another account.")
    if data.tier != "essential":
        raise HTTPException(status_code=422, detail="Only the single-line Essential plan is available at launch.")
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Payments are not configured.")
    if not PRICE_MAP.get(data.tier):
        raise HTTPException(status_code=422, detail="Choose a configured subscription plan.")
    base = public_url()
    onboarding = db.query(CustomerOnboarding).filter(
        CustomerOnboarding.user_id == current_user.id
    ).with_for_update().first()
    if not onboarding:
        if db.query(PhoneNumber).filter(PhoneNumber.user_id == current_user.id).first():
            raise HTTPException(status_code=409, detail="Your account already has phone service. Contact support to change your subscription.")
        onboarding = new_onboarding(current_user.id)
        db.add(onboarding)
        db.flush()
    try:
        if onboarding.stripe_subscription_id:
            refresh_payment(db, onboarding)
            raise HTTPException(status_code=409, detail=(
                "A subscription already exists. Resume setup or contact support about billing."
            ))
        if onboarding.checkout_session_id:
            checkout = stripe_data(stripe.checkout.Session.retrieve(onboarding.checkout_session_id))
            if checkout.get("status") == "complete":
                raise HTTPException(status_code=409, detail="Checkout is complete. Resume setup to verify payment.")
            if checkout.get("status") == "open":
                if onboarding.tier != data.tier:
                    raise HTTPException(status_code=409, detail="Finish or cancel your existing checkout before changing plans.")
                return {"checkout_url": checkout["url"], "session_id": checkout["id"]}
            onboarding.checkout_key = secrets.token_urlsafe(24)
            onboarding.checkout_session_id = None
        elif onboarding.tier and onboarding.tier != data.tier:
            raise HTTPException(status_code=409, detail="Retry your original plan while checkout is being confirmed.")
        onboarding.tier = data.tier
        # Persist the idempotency key before contacting Stripe, including on timeouts.
        db.commit()
        checkout = stripe.checkout.Session.create(
            customer_email=current_user.email,
            client_reference_id=str(current_user.id),
            line_items=[{"price": PRICE_MAP[data.tier], "quantity": 1}],
            mode="subscription",
            success_url=f"{base}/static/onboarding.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/static/onboarding.html?payment=cancelled",
            metadata={"user_id": str(current_user.id), "tier": data.tier,
                      "flow": "rootcall_onboarding_v1", "checkout_key": onboarding.checkout_key},
            idempotency_key=f"rootcall-checkout-{onboarding.checkout_key}",
        )
        onboarding.checkout_session_id = checkout.id
        db.commit()
        return {"checkout_url": checkout.url, "session_id": checkout.id}
    except stripe.StripeError:
        db.rollback()
        log.exception("Stripe checkout failed for user %s", current_user.id)
        raise HTTPException(status_code=502, detail="Checkout could not start. Please retry.")


class VerifyCheckout(BaseModel):
    session_id: str


@router.get("/status")
def payment_status(
    user: User = Depends(get_current_active_user), db: Session = Depends(get_db),
):
    onboarding = db.get(CustomerOnboarding, user.id)
    if onboarding and onboarding.stripe_subscription_id:
        refresh_payment(db, onboarding)
    result = billing_summary(onboarding)
    if not onboarding:
        result["billing_available"] = bool(user.stripe_customer_id)
    return result


@router.post("/billing-portal")
def billing_portal(
    user: User = Depends(get_current_active_user), db: Session = Depends(get_db),
):
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Billing is not configured.")
    base = public_url()
    onboarding = db.get(CustomerOnboarding, user.id)
    customer_id = onboarding.stripe_customer_id if onboarding else user.stripe_customer_id
    if not customer_id:
        raise HTTPException(status_code=409, detail="No verified billing account was found. Complete checkout first or contact support.")
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id, return_url=f"{base}{next_url(db, user.id)}",
        )
    except stripe.StripeError:
        log.exception("Billing portal failed for user %s", user.id)
        raise HTTPException(status_code=502, detail="Billing management is unavailable. Please retry.")
    return {"portal_url": session.url}


@router.post("/verify")
def verify_payment(
    body: VerifyCheckout, user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    verify_checkout(db, user, body.session_id)
    return {"paid": True, "next_url": "/static/onboarding.html"}


@router.post("/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Payment webhooks are not configured.")
    try:
        event = stripe_data(stripe.Webhook.construct_event(
            await request.body(), request.headers.get("stripe-signature", ""),
            settings.STRIPE_WEBHOOK_SECRET,
        ))
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid payment webhook signature.")
    payload = event["data"]["object"]
    if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        metadata = payload.get("metadata") or {}
        if metadata.get("flow") != "rootcall_onboarding_v1":
            return {"received": True}
        user_id = metadata.get("user_id", "")
        user = db.get(User, int(user_id)) if str(user_id).isdigit() else None
        if not user:
            raise HTTPException(status_code=400, detail="Checkout account was not found.")
        if payload.get("payment_status") == "paid":
            verify_checkout(db, user, payload["id"])
    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted",
                            "invoice.paid", "invoice.payment_failed"):
        subscription_id = payload["id"]
        if event["type"].startswith("invoice."):
            subscription_id = payload.get("subscription") or (
                ((payload.get("parent") or {}).get("subscription_details") or {}).get("subscription")
            )
        if subscription_id:
            onboarding = db.query(CustomerOnboarding).filter(
                CustomerOnboarding.stripe_subscription_id == subscription_id
            ).first()
            if onboarding:
                # Read current Stripe state so duplicate/out-of-order events cannot grant access.
                refresh_payment(db, onboarding)
    return {"received": True}
