import logging
from datetime import datetime, timezone

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.onboarding import CustomerOnboarding
from app.models.user import User

log = logging.getLogger(__name__)


def stripe_data(value):
    return value.to_dict() if isinstance(value, stripe.StripeObject) else value


def stripe_time(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(status_code=502, detail="Billing dates could not be verified. Please retry.")
    try:
        return datetime.fromtimestamp(value, timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        raise HTTPException(status_code=502, detail="Billing dates could not be verified. Please retry.")


def billing_summary(onboarding: CustomerOnboarding | None):
    def iso(value):
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None

    return {
        "managed": bool(onboarding and onboarding.stripe_subscription_id),
        "status": onboarding.subscription_status if onboarding else None,
        "payment_status": onboarding.payment_status if onboarding else None,
        "current_period_end": iso(onboarding.current_period_end) if onboarding else None,
        "cancel_at": iso(onboarding.cancel_at) if onboarding else None,
        "canceled_at": iso(onboarding.canceled_at) if onboarding else None,
        "cancel_at_period_end": bool(onboarding and onboarding.cancel_at_period_end),
        "checked_at": iso(onboarding.billing_checked_at) if onboarding else None,
        "payment_issue_since": iso(onboarding.payment_issue_since) if onboarding else None,
        "billing_available": bool(onboarding and onboarding.stripe_customer_id),
        "service_policy": "warnings_only",
        "needs_attention": bool(onboarding and onboarding.subscription_status
                                and onboarding.subscription_status != "active"),
    }


def refresh_payment(db: Session, onboarding: CustomerOnboarding):
    try:
        subscription = stripe_data(stripe.Subscription.retrieve(onboarding.stripe_subscription_id))
    except stripe.StripeError:
        log.exception("Could not verify subscription for user %s", onboarding.user_id)
        raise HTTPException(status_code=502, detail="Payment verification is unavailable. Please try again.")
    if subscription.get("customer") != onboarding.stripe_customer_id:
        raise HTTPException(status_code=409, detail="Subscription ownership needs support review.")
    stripe_status = subscription.get("status")
    if stripe_status not in {"active", "past_due", "unpaid", "canceled", "incomplete",
                             "incomplete_expired", "trialing", "paused"}:
        raise HTTPException(status_code=502, detail="Subscription status could not be verified. Please retry.")
    items = (subscription.get("items") or {}).get("data") or []
    period_end = subscription.get("current_period_end")
    if period_end is None and items:
        ends = [stripe_time(item.get("current_period_end")) for item in items]
        period_end = min((value for value in ends if value is not None), default=None)
    else:
        period_end = stripe_time(period_end)
    cancel_at = stripe_time(subscription.get("cancel_at"))
    canceled_at = stripe_time(subscription.get("canceled_at"))
    onboarding.subscription_status = stripe_status
    onboarding.current_period_end = period_end
    onboarding.cancel_at = cancel_at
    onboarding.canceled_at = canceled_at
    onboarding.cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))
    onboarding.billing_checked_at = datetime.utcnow()
    onboarding.payment_status = "active" if stripe_status == "active" else "inactive"
    if stripe_status == "active":
        onboarding.payment_issue_since = None
    elif onboarding.payment_issue_since is None:
        onboarding.payment_issue_since = datetime.utcnow()
    db.commit()
    return subscription


def verify_checkout(db: Session, user: User, session_id: str):
    try:
        checkout = stripe_data(stripe.checkout.Session.retrieve(session_id))
    except stripe.StripeError:
        log.exception("Could not verify checkout for user %s", user.id)
        raise HTTPException(status_code=502, detail="Could not verify checkout. Please try again.")
    onboarding = db.get(CustomerOnboarding, user.id)
    metadata = checkout.get("metadata") or {}
    if (not onboarding or metadata.get("user_id") != str(user.id)
            or metadata.get("flow") != "rootcall_onboarding_v1"
            or metadata.get("checkout_key") != onboarding.checkout_key):
        raise HTTPException(status_code=403, detail="This checkout does not belong to your account.")
    if metadata.get("tier") not in ("essential", "family", "guardian"):
        raise HTTPException(status_code=409, detail="Checkout plan needs support review.")
    if checkout.get("status") != "complete" or checkout.get("payment_status") != "paid":
        raise HTTPException(status_code=402, detail="Payment is not confirmed yet. Please check again shortly.")
    if checkout.get("mode") != "subscription" or not checkout.get("subscription") or not checkout.get("customer"):
        raise HTTPException(status_code=409, detail="Checkout subscription details are incomplete.")
    onboarding.checkout_session_id = checkout["id"]
    onboarding.stripe_customer_id = checkout["customer"]
    onboarding.stripe_subscription_id = checkout["subscription"]
    onboarding.tier = metadata["tier"]
    user.stripe_customer_id = checkout["customer"]
    refresh_payment(db, onboarding)
    if onboarding.payment_status != "active":
        raise HTTPException(status_code=402, detail="Your subscription is not active.")
    return onboarding
