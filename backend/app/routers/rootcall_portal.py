# -*- coding: utf-8 -*-
"""
RootCall Client Portal API Routes - SECURE VERSION WITH TELNYX + RETELL
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import io
import csv
import os
import secrets
import logging
import requests

# Database
from app.database import get_db

# Models
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig
from app.models.rootcall_call_log import RootCallCallLog

# Services
from app.services.telnyx_service import TelnyxService
from app.services.retell_service import RetellService

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

class ConfigUpdate(BaseModel):
    client_cell: Optional[str] = None
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None

class TrustedContactAdd(BaseModel):
    phone_number: str
    name: Optional[str] = None

class ProvisionRequest(BaseModel):
    phone_number: Optional[str] = None  # NEW: specific number to provision
    area_code: Optional[str] = "813"    # Or search by area code

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
    
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        return {
            "spam_blocked": 0,
            "calls_screened": 0,
            "trusted_forwarded": 0,
            "total_calls": 0
        }
    
    spam_blocked = db.query(RootCallCallLog).filter(
        RootCallCallLog.phone_number_id.in_(phone_ids),
        RootCallCallLog.action == "spam_blocked"
    ).count()
    
    calls_screened = db.query(RootCallCallLog).filter(
        RootCallCallLog.phone_number_id.in_(phone_ids),
        RootCallCallLog.action == "screened"
    ).count()
    
    trusted_forwarded = db.query(RootCallCallLog).filter(
        RootCallCallLog.phone_number_id.in_(phone_ids),
        RootCallCallLog.action == "trusted_forwarded"
    ).count()
    
    total_calls = db.query(RootCallCallLog).filter(
        RootCallCallLog.phone_number_id.in_(phone_ids)
    ).count()
    
    return {
        "spam_blocked": spam_blocked,
        "calls_screened": calls_screened,
        "trusted_forwarded": trusted_forwarded,
        "total_calls": total_calls
    }


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
    
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        return []
    
    logs = db.query(RootCallCallLog).filter(
        RootCallCallLog.phone_number_id.in_(phone_ids)
    ).order_by(RootCallCallLog.timestamp.desc()).limit(20).all()
    
    return [
        {
            "timestamp": log.timestamp.isoformat(),
            "from_number": log.from_number,
            "caller_name": log.caller_name or "Unknown",
            "action": log.action,
            "status": log.status
        }
        for log in logs
    ]


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
    
    return {
        "client_name": config.client_name,
        "client_cell": config.client_cell,
        "sms_alerts_enabled": config.sms_alerts_enabled,
        "alert_on_spam": config.alert_on_spam,
        "alert_on_unknown": config.alert_on_unknown,
        "auto_block_spam": config.auto_block_spam,
        "trusted_contacts": [
            {"phone_number": p, "name": ""} 
            for p in (config.trusted_contacts or [])
        ]
    }


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
    
    if updates.client_cell is not None:
        config.client_cell = updates.client_cell
    if updates.sms_alerts_enabled is not None:
        config.sms_alerts_enabled = updates.sms_alerts_enabled
    if updates.alert_on_spam is not None:
        config.alert_on_spam = updates.alert_on_spam
    if updates.alert_on_unknown is not None:
        config.alert_on_unknown = updates.alert_on_unknown
    if updates.auto_block_spam is not None:
        config.auto_block_spam = updates.auto_block_spam
    
    db.commit()
    return {"success": True}


# ============================================
# TRUSTED CONTACTS
# ============================================

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
    
    config = db.query(RootCallConfig).filter(RootCallConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="No config")
    
    if not config.trusted_contacts:
        config.trusted_contacts = []
    
    if contact.phone_number not in config.trusted_contacts:
        config.trusted_contacts.append(contact.phone_number)
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
    
    config = db.query(RootCallConfig).filter(RootCallConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="No config")
    
    if config.trusted_contacts and phone_number in config.trusted_contacts:
        config.trusted_contacts.remove(phone_number)
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
    
    logs = db.query(RootCallCallLog).filter(
        RootCallCallLog.phone_number_id.in_(phone_ids)
    ).order_by(RootCallCallLog.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'From', 'Caller Name', 'Action', 'Status'])
    
    for log in logs:
        writer.writerow([
            log.timestamp.isoformat(),
            log.from_number,
            log.caller_name or 'Unknown',
            log.action,
            log.status
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rootcall_calls.csv"}
    )


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
        
        # If no specific number provided, search for one
        if not phone_number:
            if not area_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either phone_number or area_code required"
                )
            
            log.info(f"Searching for available number in area code {area_code}")
            
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
        
        # Initialize services
        telnyx = TelnyxService()
        retell = RetellService()
        
        # STEP 1: Purchase from Telnyx
        log.info("STEP 1: Purchasing from Telnyx...")
        order_result = telnyx.order_number(phone_number)
        
        if not order_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to purchase number from Telnyx"
            )
        
        log.info(f"SUCCESS - Purchased: {phone_number}")
        
        # STEP 2: Create Telnyx SIP credential connection for Retell
        # SIP trunk setup moved above
        
        connection_name = f"RootCall-Retell-{current_user.id}"
        sip_username = f"rootcall_{current_user.id}"
        sip_password = f"rc_{secrets.token_urlsafe(16)}"
        
        # Create Elastic SIP Trunk pointing to Retell (sip.retellai.com)
        log.info("STEP 2: Creating Elastic SIP Trunk for Retell...")
        connection, username, password = telnyx.get_or_create_retell_trunk(
            connection_name=connection_name,
            sip_username=sip_username,
            sip_password=sip_password
        )
        
        connection_id = connection.get("id")
        log.info(f"SUCCESS - SIP Connection: {connection_id}")
        
        # STEP 3: Assign number to connection
        log.info("STEP 3: Assigning number to SIP trunk...")
        telnyx.assign_number_to_connection(phone_number, connection_id)
        log.info(f"SUCCESS - Number assigned to connection")
        
        # STEP 4: Create Retell agent
        log.info("STEP 4: Creating Retell AI agent...")
        
        agent_name = f"ScamShield-{current_user.email.split('@')[0]}"
        
        # Create LLM with scam screening prompt
        scam_prompt = """You are an AI scam screening assistant protecting the user from fraud and scams.

Your job is to:
1. Greet callers professionally
2. Ask for their name and reason for calling
3. Detect scam indicators and block suspicious calls
4. Connect legitimate callers to the user

SCAM INDICATORS TO BLOCK:
- Requests for money, gift cards, wire transfers, cryptocurrency
- Claims to be IRS, Social Security, government agencies demanding payment
- Threats, urgency, or pressure tactics
- Requests for personal info (SSN, bank details, passwords)
- Tech support scams (fake Microsoft, Apple, antivirus)
- Prize/lottery winnings requiring payment
- Robocalls or clearly automated voices

If SCAM detected, say: "This call appears to be fraudulent and will not be connected. Goodbye." Then hang up.

For LEGITIMATE calls, say: "Thank you, connecting you now." Then transfer.

Be polite but firm with scammers. Protect the user at all costs."""

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
        log.error(f"[ERROR] Provision failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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
