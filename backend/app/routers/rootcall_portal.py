# -*- coding: utf-8 -*-
"""
RootCall Client Portal API Routes - SECURE VERSION WITH TELNYX + RETELL
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import io
import csv
import os
import secrets
import logging
import re
import requests

# Database
from app.database import get_db

# Models
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig, TrustedContact
from app.models.onboarding import CustomerOnboarding
from app.services.customer_onboarding import automated_onboarding_enabled, sip_credentials

# Services
from app.services.telnyx_service import TelnyxService
from app.services.retell_service import RetellService, build_scam_screening_prompt
from app.services.trusted_routing import enable_trusted_routing, normalize_caller
from app.services.customer_activity import activity_query, activity_stats, serialize_activity

# Auth
try:
    from app.dependencies import get_current_user
except ImportError:
    from app.core.deps import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(tags=["RootCall Portal"])

# Initialize services
# Services initialized per-request
# telnyx_service = TelnyxService()

# ============================================
# PYDANTIC MODELS
# ============================================



def normalize_transfer_number(value: str) -> str:
    """Normalize a US phone number or validate an E.164 destination."""
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        normalized = f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        normalized = f"+{digits}"
    elif raw.startswith("+") and 8 <= len(digits) <= 15 and not digits.startswith("0"):
        normalized = f"+{digits}"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid phone number, including the country code (example: +14155550123)."
        )
    if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid phone number in international format."
        )
    return normalized


class ConfigUpdate(BaseModel):
    client_cell: Optional[str] = None
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None
    voice_id: Optional[str] = None
    full_name: Optional[str] = None

class TrustedContactAdd(BaseModel):
    phone_number: str
    name: Optional[str] = None

class ProvisionRequest(BaseModel):
    phone_number: Optional[str] = None  # NEW: specific number to provision
    area_code: Optional[str] = "813"    # Or search by area code
    recover_existing: bool = False

# ============================================
# STATS & DASHBOARD
# ============================================

@router.get("/api/rootcall/stats/{client_id}")
async def get_stats(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get RootCall protection stats - AUTHENTICATED"""
    
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's data"
        )
    
    return activity_stats(db, client_id)


@router.get("/api/rootcall/calls/{client_id}")
async def get_recent_calls(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent call activity - AUTHENTICATED"""
    
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's data"
        )
    
    return [serialize_activity(row) for row in activity_query(db, client_id).limit(20)]


# ============================================
# CONFIGURATION
# ============================================

@router.get("/api/rootcall/config/{client_id}")
async def get_config(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get RootCall configuration - AUTHENTICATED"""
    
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other user's data"
        )
    
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="No phone number")
    
    config = db.query(RootCallConfig).filter(RootCallConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="No config")
    
    names = {
        contact.phone_number: contact.name
        for contact in db.query(TrustedContact).filter(
            TrustedContact.rootcall_config_id == config.id,
            TrustedContact.is_active.is_(True),
        ).order_by(TrustedContact.id).all()
    }
    onboarding = db.get(CustomerOnboarding, client_id)
    return {
        "setup_guide_available": bool(onboarding and onboarding.status == "completed"),
        "client_name": config.client_name,
        "voice_id": config.voice_id or "11labs-Adrian",
        "client_cell": config.client_cell,
        "sms_alerts_enabled": config.sms_alerts_enabled,
        "alert_on_spam": config.alert_on_spam,
        "alert_on_unknown": config.alert_on_unknown,
        "auto_block_spam": config.auto_block_spam,
        "trusted_routing_enabled": config.trusted_routing_enabled,
        "line_configured": bool(
            phone.is_active and config.is_active and config.retell_agent_id
            and normalize_caller(config.client_cell)
            and normalize_caller(config.client_cell) != phone.phone_number
        ),
        "trusted_contacts": [
            {"phone_number": p, "name": names.get(p, "")}
            for p in (config.trusted_contacts or [])
        ]
    }


@router.get("/api/rootcall/voice-options")
async def get_voice_options(
    current_user: User = Depends(get_current_user)
):
    """Return every voice available in the connected Retell workspace."""
    try:
        catalog = RetellService().list_voices()
    except Exception as exc:
        log.exception("Could not retrieve Retell voice catalog")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load voices from Retell. Check the Retell API connection."
        ) from exc

    voices = []
    for item in catalog:
        if not isinstance(item, dict) or not item.get("voice_id"):
            continue
        voices.append({
            "voice_id": item.get("voice_id"),
            "voice_name": item.get("voice_name") or item.get("name") or item.get("voice_id"),
            "provider": item.get("provider") or "Unknown provider",
            "gender": item.get("gender") or "",
            "accent": item.get("accent") or "",
            "age": item.get("age") or "",
            "preview_audio_url": item.get("preview_audio_url"),
        })
    voices.sort(key=lambda voice: (str(voice["provider"]).lower(), str(voice["voice_name"]).lower()))
    return {"voices": voices}


@router.post("/api/rootcall/sync-agent-identity/{client_id}")
async def sync_agent_identity(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Synchronize the existing Retell agent with the authenticated account holder identity."""
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify another user's screening agent"
        )

    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == client_id,
        PhoneNumber.is_active == True
    ).first()
    if not phone:
        raise HTTPException(status_code=404, detail="No active RootCall phone number")

    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id
    ).first()
    if not config or not config.retell_agent_id:
        raise HTTPException(status_code=409, detail="No Retell screening agent is configured")

    owner_name = (current_user.full_name or "").strip()
    if not owner_name:
        raise HTTPException(status_code=409, detail="Protected account holder name is not configured")

    try:
        retell = RetellService()
        retell.update_screening_identity(config.retell_agent_id, owner_name)
        config.client_name = owner_name
        db.commit()
    except Exception as exc:
        db.rollback()
        log.exception("Failed to synchronize protected identity for client %s", client_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Retell could not be updated. The existing screening prompt was not confirmed as changed."
        ) from exc

    return {"success": True, "message": "Protected account identity rules synchronized."}


@router.patch("/api/rootcall/config/{client_id}")
async def update_config(
    client_id: int,
    updates: ConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update RootCall configuration - AUTHENTICATED"""
    
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify other user's config"
        )
    
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="No phone number")
    
    config = db.query(RootCallConfig).filter(RootCallConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="No config")
    
    if updates.full_name is not None:
        owner_name = updates.full_name.strip()
        if len(owner_name) < 2 or len(owner_name) > 120 or len(owner_name.split()) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Enter the account holder's first and last name."
            )
        current_user.full_name = owner_name
        config.client_name = owner_name

    if updates.client_cell is not None:
        transfer_number = (
            normalize_transfer_number(updates.client_cell)
            if updates.client_cell.strip()
            else None
        )
        if transfer_number == phone.phone_number:
            raise HTTPException(status_code=422, detail="Forwarding number cannot be your Shield number.")

        if transfer_number:
            if not phone.telnyx_connection_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This RootCall number is missing its Telnyx SIP connection link. Contact support before enabling transfers."
                )
            try:
                telnyx = TelnyxService()
                if telnyx.trunk_needs_credentials(phone.telnyx_connection_id):
                    # Older trunks have no SIP login on Telnyx and Retell holds a password we
                    # never stored. Set one known login on both sides (Retell first).
                    sip_user, sip_pass = sip_credentials(current_user.id)
                    RetellService().update_phone_number(
                        phone.phone_number, auth_username=sip_user, auth_password=sip_pass
                    )
                    telnyx.set_trunk_credentials(phone.telnyx_connection_id, sip_user, sip_pass)
                    log.info("Repaired SIP login for trunk %s", phone.telnyx_connection_id)
                telnyx.ensure_outbound_voice_profile(phone.telnyx_connection_id)
            except (RuntimeError, ValueError, requests.RequestException) as exc:
                db.rollback()
                log.exception("Failed to ensure Telnyx outbound profile for client %s", client_id)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Your transfer number was not saved because Telnyx outbound calling is not configured. Please try again or contact support."
                ) from exc

        if config.retell_agent_id:
            try:
                retell = RetellService()
                retell.configure_transfer_tool(
                    agent_id=config.retell_agent_id,
                    transfer_number=transfer_number
                )
            except (RuntimeError, ValueError, requests.RequestException) as exc:
                db.rollback()
                log.exception("Failed to update Retell transfer for client %s", client_id)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Your transfer number was not saved because Retell could not be updated. Please try again."
                ) from exc
        elif transfer_number:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This RootCall number is not connected to a Retell screening agent yet."
            )

        config.client_cell = transfer_number or ""
        log.info(
            "Updated customer transfer destination for client %s: %s",
            client_id,
            "configured" if transfer_number else "cleared"
        )
    if updates.sms_alerts_enabled is not None:
        config.sms_alerts_enabled = updates.sms_alerts_enabled
    if updates.alert_on_spam is not None:
        config.alert_on_spam = updates.alert_on_spam
    if updates.alert_on_unknown is not None:
        config.alert_on_unknown = updates.alert_on_unknown
    if updates.auto_block_spam is not None:
        config.auto_block_spam = updates.auto_block_spam
    if updates.voice_id is not None:
        try:
            available_voices = RetellService().list_voices()
        except Exception as exc:
            log.exception("Could not validate Retell voice for client %s", client_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not load available voices from Retell. Please try again."
            ) from exc
        if not any(
            isinstance(item, dict) and item.get("voice_id") == updates.voice_id
            for item in available_voices
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Choose a voice returned by your connected Retell workspace."
            )
        if not config.retell_agent_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This RootCall number is not connected to a screening agent yet."
            )
        try:
            RetellService().update_voice(config.retell_agent_id, updates.voice_id)
        except Exception as exc:
            db.rollback()
            log.exception("Failed to update Retell voice for client %s", client_id)
            # Include Retell's sanitized API error so the dashboard can show
            # the actual rejection instead of masking every failure as publish-related.
            retell_error = str(exc).replace("\\n", " ").strip()[:600]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Retell voice update failed: "
                    + (retell_error or "Retell returned an empty error.")
                    + " Your saved voice was not changed."
                )
            ) from exc
        config.voice_id = updates.voice_id
    
    db.commit()
    return {"success": True, "voice_id": config.voice_id or "11labs-Adrian", "full_name": current_user.full_name}


# ============================================
# TRUSTED CONTACTS
# ============================================

@router.post("/api/rootcall/trusted-routing/{client_id}")
def connect_trusted_routing(
    client_id: int, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id != client_id or not current_user.is_active:
        raise HTTPException(status_code=403, detail="Cannot modify this account's routing.")
    setup = db.get(CustomerOnboarding, client_id) if automated_onboarding_enabled() else None
    if setup and setup.status != "completed":
        raise HTTPException(status_code=409, detail="Resume onboarding or contact support before changing trusted routing.")
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == client_id, PhoneNumber.is_active.is_(True),
    ).first()
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id, RootCallConfig.user_id == client_id,
    ).with_for_update().first() if phone else None
    if not config:
        raise HTTPException(status_code=404, detail="No active Shield configuration.")
    try:
        enable_trusted_routing(db, config, phone.phone_number)
    except (RuntimeError, requests.RequestException, ValueError):
        db.rollback()
        log.exception("Could not connect trusted routing for user %s", client_id)
        raise HTTPException(status_code=502, detail="Trusted routing could not be connected. Your screening agent is unchanged; retry or contact support.")
    return {"success": True, "trusted_routing_enabled": True}


@router.post("/api/rootcall/trusted-contacts/{client_id}")
async def add_trusted_contact(
    client_id: int,
    contact: TrustedContactAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add trusted contact - AUTHENTICATED"""
    
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify other user's contacts"
        )
    
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="No phone number")
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id
    ).with_for_update().first()
    if not config:
        raise HTTPException(status_code=404, detail="No config")
    
    normalized = normalize_caller(contact.phone_number)
    if not normalized or normalized == phone.phone_number:
        raise HTTPException(status_code=422, detail="Enter a valid trusted caller number different from your Shield number.")
    name = (contact.name or "").strip()
    if len(name) > 100:
        raise HTTPException(status_code=422, detail="Contact names must be 100 characters or fewer.")
    if normalized not in (config.trusted_contacts or []):
        if len(config.trusted_contacts or []) >= 100:
            raise HTTPException(status_code=422, detail="You can save up to 100 trusted contacts.")
        config.trusted_contacts = [*(config.trusted_contacts or []), normalized]
    saved = db.query(TrustedContact).filter(
        TrustedContact.rootcall_config_id == config.id,
        TrustedContact.phone_number == normalized,
    ).order_by(TrustedContact.id).first()
    if saved:
        if contact.name is not None:
            saved.name = name
        saved.is_active = True
    else:
        db.add(TrustedContact(rootcall_config_id=config.id, phone_number=normalized, name=name))
    db.commit()
    
    return {"success": True}


@router.delete("/api/rootcall/trusted-contacts/{client_id}/{phone_number}")
async def remove_trusted_contact(
    client_id: int,
    phone_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove trusted contact - AUTHENTICATED"""
    
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify other user's contacts"
        )
    
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="No phone number")
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id
    ).with_for_update().first()
    if not config:
        raise HTTPException(status_code=404, detail="No config")
    
    if config.trusted_contacts and phone_number in config.trusted_contacts:
        config.trusted_contacts = [p for p in config.trusted_contacts if p != phone_number]
    db.query(TrustedContact).filter(
        TrustedContact.rootcall_config_id == config.id,
        TrustedContact.phone_number == phone_number,
    ).delete(synchronize_session=False)
    db.commit()
    
    return {"success": True}


# ============================================
# EXPORT
# ============================================

@router.get("/api/rootcall/export/{client_id}")
async def export_calls(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export call logs as CSV - AUTHENTICATED"""
    
    if current_user.id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot export other user's data"
        )
    
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        raise HTTPException(status_code=404, detail="No phone numbers")
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'From', 'Caller Name', 'Action', 'Status'])
    
    for row in activity_query(db, client_id).yield_per(500):
        values = serialize_activity(row)
        writer.writerow([
            csv_cell(values[key])
            for key in ("timestamp", "from_number", "caller_name", "action", "status")
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rootcall_calls.csv"}
    )


def csv_cell(value):
    text = "" if value is None else str(value)
    # Phone numbers and caller names are untrusted spreadsheet input.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else text


# ============================================
# NEW: SEARCH AVAILABLE NUMBERS FROM TELNYX
# ============================================

@router.get("/api/rootcall/available-numbers")
async def get_available_numbers(
    area_code: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for available phone numbers from Telnyx
    Query params: area_code (optional, e.g., "813")
    """
    if automated_onboarding_enabled() and db.get(CustomerOnboarding, current_user.id):
        from app.services.customer_onboarding import require_paid
        require_paid(db, current_user)
    try:
        log.info(f"Client {current_user.id} searching numbers for area code: {area_code}")
        
        # Initialize service
        telnyx = TelnyxService()
        
        # Search Telnyx for available numbers
        numbers = telnyx.search_available_numbers(
            area_code=area_code,
            country_code="US",
            limit=50
        )
        
        # Format response for frontend
        formatted_numbers = []
        for num in numbers:
            formatted_numbers.append({
                "phone_number": num.get("phone_number"),
                "locality": num.get("locality"),
                "region": num.get("region_information", [{}])[0].get("region_name") if num.get("region_information") else None,
                "rate_center": num.get("rate_center"),
            })
        
        log.info(f"Found {len(formatted_numbers)} available numbers")
        
        return {
            "success": True,
            "count": len(formatted_numbers),
            "numbers": formatted_numbers
        }
        
    except Exception as e:
        log.error(f"Error searching available numbers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search numbers: {str(e)}"
        )


# ============================================
# ENHANCED: PROVISION WITH RETELL AUTO-IMPORT
# ============================================

@router.post("/api/rootcall/provision")
async def provision_rootcall(
    request: ProvisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Provision RootCall number with AUTO Retell import
    - Purchase from Telnyx
    - Create Retell agent
    - Import to Retell
    - Configure for scam screening
    """
    if automated_onboarding_enabled() and db.get(CustomerOnboarding, current_user.id):
        from app.services.activation_jobs import enqueue_activation
        from app.routers.payments import public_url
        public_url()
        return JSONResponse(status_code=202, content=enqueue_activation(db, current_user))
    provision_step = "checking your account"
    order_accepted = False
    phone_number = request.phone_number
    try:
        # Check if user already has active number
        existing = db.query(PhoneNumber).filter(
            PhoneNumber.user_id == current_user.id,
            PhoneNumber.is_active == True
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already have active number"
            )
        
        # Get the selected phone number from request
        phone_number = request.phone_number
        area_code = request.area_code
        provision_step = "initializing phone providers"
        telnyx = TelnyxService()
        retell = RetellService()
        
        # If no specific number provided, search for one
        if not phone_number:
            if request.recover_existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A phone number is required to recover an existing purchase"
                )
            if not area_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either phone_number or area_code required"
                )
            
            log.info(f"Searching for available number in area code {area_code}")
            provision_step = "searching for an available number"
            
            # Search for available number
            available = telnyx.search_available_numbers(
                area_code=area_code,
                country_code="US",
                limit=1
            )
            
            if not available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No numbers available in area code {area_code}"
                )
            
            phone_number = available[0]["phone_number"]
        
        log.info(f"[PROVISION] Starting for {phone_number} - user {current_user.id}")
        
        provision_step = "checking Telnyx for an existing number"
        existing_telnyx_numbers = telnyx.list_phone_numbers(phone_number=phone_number)
        existing_telnyx_number = next(
            (number for number in existing_telnyx_numbers if number.get("phone_number") == phone_number),
            None,
        )
        if existing_telnyx_number:
            order_result = {"data": existing_telnyx_number}
            order_accepted = True
            log.info("Found existing Telnyx number for provisioning retry: %s", phone_number)
        else:
            if request.recover_existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="That number was not found in your Telnyx account. No purchase was made."
                )
            log.info("STEP 1: Purchasing from Telnyx...")
            provision_step = "ordering the number from Telnyx"
            order_result = telnyx.order_number(phone_number)

            if not order_result:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to purchase number from Telnyx"
                )
            order_accepted = True
        
        log.info(f"SUCCESS - Purchased: {phone_number}")
        
        # STEP 2: Create Telnyx SIP credential connection for Retell
        # SIP trunk setup moved above
        
        connection_name = f"RootCall-Retell-{current_user.id}"
        sip_username, sip_password = sip_credentials(current_user.id)
        
        # Create Elastic SIP Trunk pointing to Retell (sip.retellai.com)
        log.info("STEP 2: Creating Elastic SIP Trunk for Retell...")
        provision_step = "creating the Telnyx SIP connection"
        connection, username, password = telnyx.get_or_create_retell_trunk(
            connection_name=connection_name,
            sip_username=sip_username,
            sip_password=sip_password
        )
        
        connection_id = connection.get("id")
        log.info(f"SUCCESS - SIP Connection: {connection_id}")

        number_is_assigned = bool(existing_telnyx_number and existing_telnyx_number.get("connection_id"))
        if number_is_assigned and existing_telnyx_number.get("connection_id") != connection_id:
            log.error(
                "Number %s is on connection %s, not this user's trunk %s",
                phone_number, existing_telnyx_number.get("connection_id"), connection_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Telnyx number is not assigned to your RootCall SIP connection. Contact support before retrying.",
            )
        
        # STEP 3: Assign number to connection
        if not number_is_assigned:
            log.info("STEP 3: Assigning number to SIP trunk...")
            provision_step = "connecting the number to the Telnyx SIP trunk"
            telnyx.assign_number_to_connection(phone_number, connection_id)
            log.info("SUCCESS - Number assigned to connection")
        else:
            log.info("Number is already assigned to the user's SIP trunk; skipping assignment")
        
        # STEP 4: Create Retell agent
        log.info("STEP 4: Creating Retell AI agent...")
        provision_step = "creating the Retell screening agent"
        
        agent_name = f"ScamShield-{current_user.email.split('@')[0]}"
        
        # Bind the agent to the protected account holder from the authenticated account.
        owner_name = (current_user.full_name or "").strip()
        scam_prompt = build_scam_screening_prompt(owner_name)

        llm_id = retell.create_llm(
            general_prompt=scam_prompt,
            begin_message="Hello, this is the AI scam screening service. May I ask who's calling and the reason for your call?",
            start_speaker="agent"
        )
        
        agent_id = retell.create_agent(
            name=agent_name,
            llm_id=llm_id,
            voice_id="11labs-Adrian",
            language="en-US",
            publish=True
        )
        
        log.info(f"SUCCESS - Agent created: {agent_id}")
        
        # STEP 5: Import number to Retell
        log.info("STEP 5: Importing number to Retell...")
        provision_step = "connecting the number to Retell"
        
        retell_import = retell.import_phone_number(
            phone_number=phone_number,
            termination_uri="sip.telnyx.com",
            sip_username=username,
            sip_password=password,
            inbound_agent_id=agent_id,
            outbound_agent_id=agent_id
        )
        
        log.info(f"SUCCESS - Imported to Retell")
        
        # STEP 6: Save to database
        log.info("STEP 6: Saving to database...")
        provision_step = "saving the number to your dashboard"
        
        phone_record = PhoneNumber(
            user_id=current_user.id,
            phone_number=phone_number,
            friendly_name=f"RootCall Shield - {area_code or phone_number[-10:-7]}",
            country_code="US",
            telnyx_phone_number_id=order_result.get("data", {}).get("id", ""),
            telnyx_connection_id=connection_id,
            is_active=True,
            monthly_cost=1.0
        )
        db.add(phone_record)
        db.flush()
        
        # Create config
        config = RootCallConfig(
            phone_number_id=phone_record.id,
            user_id=current_user.id,
            client_name=current_user.full_name or current_user.email,
            client_cell="",
            retell_agent_id=agent_id,
            retell_did=phone_number,
            trusted_contacts=[],
            sms_alerts_enabled=True,
            alert_on_spam=True,
            alert_on_unknown=True,
            auto_block_spam=True,
            is_active=True
        )
        db.add(config)
        db.commit()
        db.refresh(phone_record)
        
        log.info("[COMPLETE] Provisioning successful!")
        
        return {
            "success": True,
            "rootcall_number": phone_number,
            "phone_number": phone_number,
            "friendly_name": phone_record.friendly_name,
            "agent_id": agent_id,
            "purchased_at": phone_record.purchased_at.isoformat(),
            "message": f"Number activated with AI scam protection!"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log.exception("Provision failed while %s for user %s", provision_step, current_user.id)
        detail = f"Number setup failed while {provision_step}."
        if order_accepted:
            detail += (
                f" Telnyx already accepted the order for {phone_number}."
                " Do not purchase another number; contact support to finish connecting this one."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        ) from e


# ============================================
# MY NUMBER
# ============================================

@router.get("/api/rootcall/my-number")
async def get_my_number(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's number - AUTHENTICATED"""
    
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.is_active == True
    ).first()
    
    if not phone:
        return {"has_number": False}
    
    return {
        "has_number": True,
        "number": phone.phone_number,
        "friendly_name": phone.friendly_name,
        "purchased_at": phone.purchased_at.isoformat()
    }


# ============================================
# DASHBOARD SETUP
# ============================================

@router.get("/dashboard-setup")
async def get_dashboard_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard setup status - AUTHENTICATED"""
    
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.is_active == True
    ).first()
    
    config = None
    if phone:
        config = db.query(RootCallConfig).filter(
            RootCallConfig.phone_number_id == phone.id
        ).first()
    
    if phone and not config:
        config = RootCallConfig(
            phone_number_id=phone.id,
            user_id=current_user.id,
            client_name=current_user.full_name or current_user.email,
            client_cell=None,
            sms_alerts_enabled=False,
            alert_on_spam=True,
            alert_on_unknown=True,
            auto_block_spam=True,
            trusted_contacts=[]
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    
    has_number = phone is not None
    has_forwarding = bool(config.client_cell) if config else False
    trusted_count = len(config.trusted_contacts or []) if config else 0
    
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "has_number": has_number,
        "has_forwarding_number": has_forwarding,
        "trusted_contacts_count": trusted_count,
        "sms_alerts_enabled": bool(config.sms_alerts_enabled) if config else False,
        "auto_block_spam": bool(config.auto_block_spam) if config else True,
    }


# ============================================
# IMPORT EXISTING
# ============================================

@router.post("/api/rootcall/import-existing/{phone_number}")
async def import_existing_number(
    phone_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import existing Telnyx number into RootCall"""
    if automated_onboarding_enabled() and db.get(CustomerOnboarding, current_user.id):
        raise HTTPException(status_code=409, detail="Use paid onboarding to activate your Shield number.")
    from urllib.parse import unquote
    
    phone_number = unquote(phone_number)
    
    existing = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number
    ).first()
    
    if existing:
        existing_config = db.query(RootCallConfig).filter(
            RootCallConfig.phone_number_id == existing.id
        ).first()
        
        if existing_config:
            return {
                "success": True,
                "message": "Number already configured",
                "phone_id": existing.id,
                "already_existed": True
            }
        else:
            config = RootCallConfig(
                phone_number_id=existing.id,
                user_id=current_user.id,
                client_name=current_user.full_name or current_user.email,
                client_cell="",
                retell_agent_id="",
                retell_did=phone_number,
                trusted_contacts=[],
                sms_alerts_enabled=True,
                alert_on_spam=True,
                alert_on_unknown=True,
                auto_block_spam=True,
                is_active=True
            )
            db.add(config)
            db.commit()
            
            return {
                "success": True,
                "message": f"Added config for existing number {phone_number}",
                "phone_id": existing.id
            }
    
    phone_record = PhoneNumber(
        user_id=current_user.id,
        phone_number=phone_number,
        friendly_name=f"RootCall - {phone_number[-10:-7]}",
        country_code="US",
        telnyx_phone_number_id="imported_existing",
        telnyx_connection_id="",
        is_active=True,
        monthly_cost=1.0
    )
    db.add(phone_record)
    db.flush()
    
    config = RootCallConfig(
        phone_number_id=phone_record.id,
        user_id=current_user.id,
        client_name=current_user.full_name or current_user.email,
        client_cell="",
        retell_agent_id="",
        retell_did=phone_number,
        trusted_contacts=[],
        sms_alerts_enabled=True,
        alert_on_spam=True,
        alert_on_unknown=True,
        auto_block_spam=True,
        is_active=True
    )
    db.add(config)
    db.commit()
    db.refresh(phone_record)
    
    return {
        "success": True,
        "message": f"Successfully imported {phone_number}",
        "phone_id": phone_record.id,
        "phone_number": phone_number
    }


# ============================================
# LANDING PAGE
# ============================================

@router.get("/", response_class=FileResponse)
async def landing_page():
    """Serve RootCall landing page"""
    return FileResponse("static/index.html")


@router.delete("/api/rootcall/my-number")
async def delete_my_number(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete/deactivate user's current number"""
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.is_active == True
    ).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="No active number found")
    
    # Deactivate
    phone.is_active = False
    db.commit()
    
    log.info(f"Deactivated number {phone.phone_number} for user {current_user.id}")
    
    return {
        "success": True,
        "message": f"Number {phone.phone_number} deactivated. You can now provision a new one."
    }
