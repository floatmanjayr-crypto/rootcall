import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime

import requests
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.onboarding import CustomerOnboarding
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig
from app.models.user import User
from app.services.retell_service import RetellService, build_scam_screening_prompt
from app.services.telnyx_service import TelnyxService
from app.services.trusted_routing import enable_trusted_routing
from app.services.activation_recovery import ActivationPending, activation_lock, resource_creation

log = logging.getLogger(__name__)

SCREENING_PROMPT = """You are RootCall, an AI scam screening assistant.
Ask callers their name and reason for calling. Never disclose the user's private
forwarding number. Reject fraud, requests for passwords or money, threats, gift
cards, and government or tech-support impersonation using end_call.
For legitimate callers, say "Thank you, let me connect you now" and use transfer_call.
Do not claim a call was connected if the tool fails. Be polite and concise."""


def automated_onboarding_enabled() -> bool:
    return bool(settings.AUTOMATED_ONBOARDING)


def new_onboarding(user_id: int) -> CustomerOnboarding:
    return CustomerOnboarding(user_id=user_id, checkout_key=secrets.token_urlsafe(24))


def next_url(db: Session, user_id: int) -> str:
    if not automated_onboarding_enabled():
        return "/static/client-portal.html"
    onboarding = db.get(CustomerOnboarding, user_id)
    if onboarding and onboarding.status != "completed":
        return "/static/onboarding.html"
    return "/static/client-portal.html"


def require_paid(db: Session, user: User) -> CustomerOnboarding:
    from app.services.payment_verification import refresh_payment

    onboarding = db.get(CustomerOnboarding, user.id)
    if not onboarding or not onboarding.stripe_subscription_id:
        raise HTTPException(status_code=402, detail="Complete payment before setting up protection.")
    refresh_payment(db, onboarding)
    if onboarding.payment_status != "active":
        raise HTTPException(status_code=402, detail="An active paid subscription is required.")
    return onboarding


def available_voices():
    try:
        voices = RetellService().list_voices()
        return [
            {
                "voice_id": voice["voice_id"], "name": voice["voice_name"],
                "accent": voice.get("accent", ""), "gender": voice.get("gender", ""),
                "preview_url": voice.get("preview_audio_url"),
            }
            for voice in voices
            if voice.get("voice_id") and voice.get("voice_name")
            and voice.get("provider") != "xai"
        ]
    except (RuntimeError, requests.RequestException, ValueError, TypeError, KeyError):
        log.exception("Could not load onboarding voices")
        raise HTTPException(status_code=502, detail="Voice choices are unavailable. Please try again.")


def provision_customer(db: Session, user: User):
    with activation_lock(db, user.id):
        return _provision_customer(db, user)


def validate_activation(db: Session, user: User):
    onboarding = require_paid(db, user)
    if onboarding.status == "completed":
        return onboarding
    if onboarding.uncertain_operation:
        raise HTTPException(status_code=409, detail=(
            "A provider resource may have been created before setup paused. "
            "Support must reconcile it before retrying; no new resource was created."
        ))
    if not all((onboarding.first_name, onboarding.last_name, onboarding.forwarding_number,
                onboarding.voice_id, onboarding.shield_number)):
        raise HTTPException(status_code=422, detail="Complete your profile, voice, and Shield number first.")
    return onboarding


def sip_credentials(user_id: int):
    """Per-customer Telnyx/Retell SIP login, named exactly as the dashboard purchase always did.

    No environment variables are required. The password is derived from the server's signing secret
    so every activation retry produces the same value without storing another secret.
    """
    username = f"{(settings.TELNYX_SIP_USERNAME or 'rootcall').strip()}_{user_id}"
    explicit = (settings.TELNYX_SIP_PASSWORD or "").strip()
    if explicit:
        return username, explicit
    secret = (settings.JWT_SECRET_KEY or "").encode()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be configured")
    digest = hmac.new(secret, f"telnyx-sip-password:{user_id}".encode(), hashlib.sha256).digest()
    return username, "rc_" + base64.urlsafe_b64encode(digest).decode().rstrip("=")[:24]


def _provision_customer(db: Session, user: User):
    onboarding = validate_activation(db, user)
    if onboarding.status == "completed":
        return {"success": True, "rootcall_number": onboarding.shield_number}
    claimed = db.query(CustomerOnboarding).filter(
        CustomerOnboarding.user_id == user.id,
        CustomerOnboarding.status.in_(["draft", "error"]),
    ).update({"status": "provisioning", "error_message": None,
              "activation_stage": "Checking phone providers",
              "activation_updated_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()
    if not claimed:
        raise HTTPException(status_code=409, detail="Setup is already running. Refresh to check progress.")
    db.refresh(onboarding)
    stage = "connecting to phone providers"
    try:
        telnyx, retell = TelnyxService(), RetellService()
        sip_username, sip_password = sip_credentials(user.id)
        if not onboarding.order_attempted and onboarding.voice_id not in {
            voice["voice_id"] for voice in available_voices()
        }:
            raise HTTPException(status_code=422, detail="Your selected voice is no longer available. Choose another before activating.")
        number = onboarding.shield_number
        existing = db.query(PhoneNumber).filter(PhoneNumber.phone_number == number).first()
        if existing and existing.user_id != user.id:
            raise HTTPException(status_code=409, detail="This number is already assigned.")

        stage = "checking your number order"
        onboarding.activation_stage = stage
        onboarding.activation_updated_at = datetime.utcnow()
        db.commit()
        owned = next((item for item in telnyx.list_phone_numbers(phone_number=number)
                      if item.get("phone_number") == number), None)
        if not owned:
            if onboarding.order_attempted:
                raise ActivationPending(detail=(
                    "Your number order is pending or needs review. No second order was placed. "
                    "Retry once the number appears in Telnyx, or contact support."
                ))
            stage = "ordering your Shield number"
            onboarding.order_attempted = True
            db.commit()
            order = telnyx.order_number(number)
            if not (order.get("data") or {}).get("id"):
                raise RuntimeError("Telnyx did not confirm an order ID")
            owned = next((item for item in telnyx.list_phone_numbers(phone_number=number)
                          if item.get("phone_number") == number), None)
            if not owned:
                raise ActivationPending(detail=(
                    "Telnyx accepted your number order and is still activating it. "
                    "Your progress is saved. Retry shortly; do not select another number."
                ))
        elif not onboarding.order_attempted and not existing:
            raise HTTPException(status_code=409, detail="This number is not available for a new purchase.")

        stage = "connecting your phone line"
        onboarding.activation_stage = stage
        onboarding.activation_updated_at = datetime.utcnow()
        db.commit()
        if not onboarding.connection_id:
            connection, _, _ = telnyx.get_or_create_retell_trunk(
                f"RootCall-Retell-{user.id}", sip_username,
                sip_password,
                outbound_voice_profile_id=(settings.TELNYX_OUTBOUND_VOICE_PROFILE_ID or "").strip() or None,
            )
            if not connection.get("id"):
                raise RuntimeError("Telnyx did not return a connection ID")
            onboarding.connection_id = connection["id"]
            db.commit()
        if owned.get("connection_id") not in (None, "", onboarding.connection_id):
            raise HTTPException(status_code=409, detail="Number routing needs support review; no routing was changed.")
        if owned.get("connection_id") != onboarding.connection_id:
            telnyx.assign_number_to_connection(number, onboarding.connection_id)

        stage = "creating your screening assistant"
        onboarding.activation_stage = stage
        onboarding.activation_updated_at = datetime.utcnow()
        db.commit()
        if not onboarding.llm_id:
            with resource_creation(db, onboarding, "screening_llm"):
                onboarding.llm_id = retell.create_llm(
                    build_scam_screening_prompt(user.full_name, SCREENING_PROMPT),
                    begin_message="Hello, you've reached RootCall AI Assistant. Who would you like to speak with?",
                )
                if not onboarding.llm_id:
                    raise RuntimeError("Retell did not return an LLM ID")
        if not onboarding.agent_id:
            with resource_creation(db, onboarding, "screening_agent"):
                onboarding.agent_id = retell.create_agent(
                    f"RootCall-{user.id}", onboarding.llm_id,
                    voice_id=onboarding.voice_id, publish=False,
                )
                if not onboarding.agent_id:
                    raise RuntimeError("Retell did not return an agent ID")
        stage = "configuring call forwarding"
        onboarding.activation_stage = stage
        onboarding.activation_updated_at = datetime.utcnow()
        db.commit()
        if not onboarding.transfer_ready:
            retell.configure_transfer_tool(
                onboarding.agent_id, onboarding.forwarding_number,
                custom_sip_headers={"X-Telnyx-Username": sip_username},
            )
            retell.configure_call_webhook(
                onboarding.agent_id, f"{settings.APP_BASE_URL.rstrip('/')}/retell/webhook"
            )
            retell.publish_agent(onboarding.agent_id)
            onboarding.transfer_ready = True
            db.commit()
        stage = "activating AI screening"
        onboarding.activation_stage = stage
        onboarding.activation_updated_at = datetime.utcnow()
        db.commit()
        if not onboarding.number_imported:
            # A previous import may have succeeded before the process lost its response.
            numbers = retell.list_phone_numbers()
            imported = next((item for item in numbers if item.get("phone_number") == number), None)
            if imported:
                bindings = imported.get("inbound_agents") or []
                if not any(item.get("agent_id") == onboarding.agent_id for item in bindings):
                    raise HTTPException(status_code=409, detail="Retell number binding needs support review.")
            else:
                retell.import_phone_number(
                    number, "sip.telnyx.com",
                    sip_username, sip_password,
                    inbound_agent_id=onboarding.agent_id,
                )
            onboarding.number_imported = True
            db.commit()

        stage = "saving your protection settings"
        if not existing:
            existing = PhoneNumber(
                user_id=user.id, phone_number=number, friendly_name="RootCall Shield",
                country_code="US", telnyx_phone_number_id=owned["id"],
                telnyx_connection_id=onboarding.connection_id, is_active=True, monthly_cost=1.0,
            )
            db.add(existing)
            db.flush()
        config = db.query(RootCallConfig).filter(
            RootCallConfig.phone_number_id == existing.id
        ).first()
        if not config:
            config = RootCallConfig(
                phone_number_id=existing.id, user_id=user.id,
                client_name=user.full_name, client_cell=onboarding.forwarding_number,
                retell_agent_id=onboarding.agent_id, retell_did=number,
                voice_id=onboarding.voice_id,
                trusted_contacts=list(onboarding.trusted_contacts or []), sms_alerts_enabled=False,
                alert_on_spam=True, alert_on_unknown=False, auto_block_spam=True,
                is_active=True,
            )
            db.add(config)
            db.flush()
        stage = "connecting trusted caller routing"
        onboarding.activation_stage = stage
        onboarding.activation_updated_at = datetime.utcnow()
        db.commit()
        enable_trusted_routing(db, config, number, service=retell, onboarding=onboarding)
        onboarding.status = "completed"
        onboarding.activation_stage = "Setup complete"
        onboarding.completed_at = datetime.utcnow()
        onboarding.error_message = None
        db.commit()
        return {"success": True, "rootcall_number": number}
    except (HTTPException, RuntimeError, requests.RequestException, ValueError, KeyError, IntegrityError) as error:
        db.rollback()
        log.exception("Onboarding failed at %s for user %s", stage, user.id)
        db.refresh(onboarding)
        detail = error.detail if isinstance(error, HTTPException) else (
            f"Setup paused while {stage}. Your progress is saved. Retry or contact support; do not buy another number."
        )
        onboarding.status = "error"
        onboarding.error_message = detail
        db.commit()
        if isinstance(error, ActivationPending):
            raise
        raise HTTPException(status_code=error.status_code if isinstance(error, HTTPException) else 502, detail=detail)
