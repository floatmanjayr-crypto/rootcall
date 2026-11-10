import logging
import re
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.database import get_db
from app.models.onboarding import CustomerOnboarding
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.models.activation_job import ActivationJob
from app.models.rootcall_config import RootCallConfig
from app.services.activation_jobs import ACTIVE_STATUSES, enqueue_activation, job_summary
from app.services.customer_onboarding import available_voices, require_paid
from app.services.payment_verification import refresh_payment, verify_checkout
from app.services.telnyx_service import TelnyxService

router = APIRouter(prefix="/api/onboarding", tags=["Customer Onboarding"])
log = logging.getLogger(__name__)


def normalize_phone(value: str) -> str:
    value = re.sub(r"[\s().-]", "", value)
    if re.fullmatch(r"\d{10}", value):
        value = "+1" + value
    if not re.fullmatch(r"\+[1-9]\d{1,14}", value):
        raise ValueError("Use a phone number with country code, such as +12025550123.")
    return value


@router.get("/status")
def status(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    onboarding = db.get(CustomerOnboarding, user.id)
    if not onboarding:
        return {"legacy": True, "status": "completed", "next_url": "/static/client-portal.html"}
    # Recover paid checkout even if the customer closed Stripe before its redirect.
    job = db.get(ActivationJob, user.id)
    if onboarding.checkout_session_id and not onboarding.stripe_subscription_id:
        try:
            verify_checkout(db, user, onboarding.checkout_session_id)
        except HTTPException as error:
            if error.status_code != 402:
                raise
    elif onboarding.stripe_subscription_id and onboarding.status != "completed" and not (
        job and job.status in ACTIVE_STATUSES
    ):
        refresh_payment(db, onboarding)
    return {
        "legacy": False, "status": onboarding.status, "payment_status": onboarding.payment_status,
        "tier": onboarding.tier, "email": user.email,
        "first_name": onboarding.first_name or "", "last_name": onboarding.last_name or "",
        "forwarding_number": onboarding.forwarding_number or "",
        "voice_id": onboarding.voice_id or "", "shield_number": onboarding.shield_number or "",
        "trusted_contacts": onboarding.trusted_contacts or [],
        "contacts_completed": onboarding.trusted_contacts is not None,
        "billing_available": bool(onboarding.stripe_customer_id),
        "number_locked": onboarding.order_attempted,
        "error_message": onboarding.error_message,
        "activation_stage": onboarding.activation_stage,
        "support_review_required": bool(onboarding.uncertain_operation or (job and job.status == "paused")),
        "activation_job": job_summary(job),
        "next_url": "/static/client-portal.html" if onboarding.status == "completed" else "/static/onboarding.html",
    }


class Profile(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    forwarding_number: str
    voice_id: str = Field(min_length=1, max_length=200)

    @validator("first_name", "last_name")
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Enter your name.")
        return value.strip()

    @validator("forwarding_number")
    def valid_phone(cls, value):
        return normalize_phone(value)


class TrustedContacts(BaseModel):
    phone_numbers: list[str] = Field(max_length=100)

    @validator("phone_numbers")
    def valid_contacts(cls, value):
        return list(dict.fromkeys(normalize_phone(phone) for phone in value))


def editable(db, user):
    onboarding = require_paid(db, user)
    onboarding = db.query(CustomerOnboarding).filter(
        CustomerOnboarding.user_id == user.id
    ).populate_existing().with_for_update().one()
    if onboarding.status not in ("draft", "error"):
        raise HTTPException(status_code=409, detail="Setup is already running or completed.")
    job = db.get(ActivationJob, user.id)
    if job and job.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Automatic activation is queued or running. Details are locked.")
    if onboarding.order_attempted:
        raise HTTPException(status_code=409, detail="Your order has started. Resume activation without changing details.")
    return onboarding


@router.get("/voices")
def voices(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    require_paid(db, user)
    return {"voices": available_voices()}


@router.put("/trusted-contacts")
def save_trusted_contacts(
    body: TrustedContacts, user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    onboarding = editable(db, user)
    if onboarding.shield_number and onboarding.shield_number in body.phone_numbers:
        raise HTTPException(status_code=422, detail="Your Shield number cannot be a trusted contact.")
    onboarding.trusted_contacts = body.phone_numbers
    db.commit()
    return {"saved": True, "trusted_contacts": onboarding.trusted_contacts}


@router.put("/profile")
def save_profile(body: Profile, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    onboarding = editable(db, user)
    if str(body.email).lower() != user.email.lower():
        raise HTTPException(status_code=422, detail="Use your account email. Contact support to change your email.")
    if onboarding.shield_number == body.forwarding_number:
        raise HTTPException(status_code=422, detail="Forwarding number cannot be your Shield number.")
    if body.voice_id not in {voice["voice_id"] for voice in available_voices()}:
        raise HTTPException(status_code=422, detail="Choose an available agent voice.")
    onboarding.first_name = body.first_name
    onboarding.last_name = body.last_name
    onboarding.forwarding_number = body.forwarding_number
    onboarding.voice_id = body.voice_id
    user.full_name = f"{body.first_name} {body.last_name}"
    db.commit()
    return {"saved": True}


@router.get("/numbers")
def numbers(area_code: str, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    require_paid(db, user)
    return search_numbers(area_code)


def search_numbers(area_code: str):
    if not re.fullmatch(r"[2-9]\d{2}", area_code):
        raise HTTPException(status_code=422, detail="Enter a three-digit US area code.")
    try:
        results = TelnyxService().search_available_numbers(area_code=area_code, limit=20)
    except (RuntimeError, requests.RequestException, ValueError):
        log.exception("Onboarding number search failed")
        raise HTTPException(status_code=502, detail="Number search is unavailable. Please retry.")
    return {"numbers": [{"phone_number": item["phone_number"], "locality": item.get("locality", "")}
                        for item in results if item.get("phone_number")]}


class NumberChoice(BaseModel):
    phone_number: str = Field(pattern=r"^\+1[2-9]\d{9}$")


@router.put("/number")
def select_number(body: NumberChoice, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    onboarding = editable(db, user)
    if body.phone_number == onboarding.forwarding_number:
        raise HTTPException(status_code=422, detail="Choose a Shield number different from your forwarding number.")
    if db.query(PhoneNumber).filter(PhoneNumber.phone_number == body.phone_number).first():
        raise HTTPException(status_code=409, detail="That number is already assigned. Choose another.")
    if body.phone_number in (onboarding.trusted_contacts or []):
        raise HTTPException(status_code=422, detail="Choose a Shield number different from your trusted contacts.")
    results = search_numbers(body.phone_number[2:5])
    if not any(item["phone_number"] == body.phone_number for item in results["numbers"]):
        raise HTTPException(status_code=409, detail="That number is no longer available. Search again.")
    onboarding.shield_number = body.phone_number
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That number was selected by another customer. Choose another.")
    return {"saved": True, "phone_number": body.phone_number}


@router.post("/complete", status_code=202)
def complete(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    from app.routers.payments import public_url
    public_url()
    return enqueue_activation(db, user)


class ServiceChecks(BaseModel):
    shield_number: str
    forwarding_number: str
    mode: Literal["direct", "carrier"]
    screening_tested: bool = False
    trusted_tested: bool = False
    audio_tested: bool = False
    carrier_forwarding_confirmed: bool = False


def setup_line(db, user):
    state = db.query(CustomerOnboarding).filter(
        CustomerOnboarding.user_id == user.id,
    ).populate_existing().with_for_update().first()
    if not state or state.status != "completed":
        raise HTTPException(status_code=409, detail="Finish activating your Shield line before saving call checks.")
    config = db.query(RootCallConfig).filter(
        RootCallConfig.user_id == user.id, RootCallConfig.retell_did == state.shield_number,
        RootCallConfig.is_active.is_(True),
    ).first()
    if not config:
        raise HTTPException(status_code=409, detail="Your line configuration needs support review.")
    return state, config


def service_checks(state, config):
    saved = state.service_setup or {}
    if saved.get("shield_number") != state.shield_number or saved.get("forwarding_number") != config.client_cell:
        saved = {}
    return {
        "shield_number": state.shield_number, "forwarding_number": config.client_cell,
        "has_trusted_contacts": bool(config.trusted_contacts),
        "checks": {key: saved.get(key, default) for key, default in {
            "mode": "direct", "screening_tested": False, "trusted_tested": False,
            "audio_tested": False, "carrier_forwarding_confirmed": False,
        }.items()},
        "self_reported": True,
    }


@router.get("/service-setup")
def get_service_setup(user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    state, config = setup_line(db, user)
    return service_checks(state, config)


@router.put("/service-setup")
def save_service_setup(body: ServiceChecks, user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    state, config = setup_line(db, user)
    if body.shield_number != state.shield_number or body.forwarding_number != config.client_cell:
        raise HTTPException(status_code=409, detail="Your line details changed. Reload call checks and test the current destination.")
    state.service_setup = {
        "shield_number": state.shield_number, "forwarding_number": config.client_cell,
        **body.dict(),
    }
    db.commit()
    return service_checks(state, config)
