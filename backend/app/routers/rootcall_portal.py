# -*- coding: utf-8 -*-
"""
RootCall Client Portal API Routes - SECURE VERSION
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
import requests

# Database
from app.database import get_db

# Models
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig
from app.models.rootcall_call_log import RootCallCallLog

# Auth - Use whichever import path works in your project
try:
    from app.dependencies import get_current_user
except ImportError:
    from app.core.deps import get_current_user

router = APIRouter(tags=["RootCall Portal"])

# ============================================
# PYDANTIC MODELS
# ============================================

class ConfigUpdate(BaseModel):
    client_cell: Optional[str] = None  # ✅ ADDED - for forwarding number
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None

class TrustedContactAdd(BaseModel):
    phone_number: str
    name: Optional[str] = None

class ProvisionRequest(BaseModel):
    area_code: str = "813"

# ============================================
# ✅ SECURE ENDPOINTS - WITH AUTH
# ============================================

@router.get("/api/rootcall/stats/{client_id}")
async def get_stats(
    client_id: int,
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Get RootCall protection stats - AUTHENTICATED"""
    
    # ✅ AUTHORIZATION CHECK - User can only access their own data
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
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Get recent call activity - AUTHENTICATED"""
    
    # ✅ AUTHORIZATION CHECK
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


@router.get("/api/rootcall/config/{client_id}")
async def get_config(
    client_id: int,
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Get RootCall configuration - AUTHENTICATED"""
    
    # ✅ AUTHORIZATION CHECK
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
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Update RootCall configuration - AUTHENTICATED"""
    
    # ✅ AUTHORIZATION CHECK
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
    
    # ✅ UPDATE ALL FIELDS
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


@router.post("/api/rootcall/trusted-contacts/{client_id}")
async def add_trusted_contact(
    client_id: int,
    contact: TrustedContactAdd,
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Add trusted contact - AUTHENTICATED"""
    
    # ✅ AUTHORIZATION CHECK
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
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Remove trusted contact - AUTHENTICATED"""
    
    # ✅ AUTHORIZATION CHECK
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


@router.get("/api/rootcall/export/{client_id}")
async def export_calls(
    client_id: int,
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Export call logs as CSV - AUTHENTICATED"""
    
    # ✅ AUTHORIZATION CHECK
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


@router.post("/api/rootcall/provision")
async def provision_rootcall(
    request: ProvisionRequest,
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Provision RootCall number - AUTHENTICATED"""
    
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
    
    area_code = request.area_code
    TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
    
    if not TELNYX_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telnyx not configured"
        )
    
    try:
        telnyx_headers = {"Authorization": f"Bearer {TELNYX_API_KEY}"}
        
        # Search for available numbers
        search = requests.get(
            "https://api.telnyx.com/v2/available_phone_numbers",
            headers=telnyx_headers,
            params={
                "filter[country_code]": "US",
                "filter[features]": "sms,voice",
                "filter[national_destination_code]": area_code,
                "filter[limit]": 1
            },
            timeout=15
        )
        
        if search.status_code != 200 or not search.json().get("data"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No numbers available in {area_code}"
            )
        
        phone_data = search.json()["data"][0]
        phone_number = phone_data["phone_number"]
        
        # Purchase number
        purchase = requests.post(
            f"https://api.telnyx.com/v2/phone_numbers/{phone_data['id']}",
            headers=telnyx_headers,
            json={},
            timeout=15
        )
        
        if purchase.status_code not in [200, 201]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Purchase failed"
            )
        
        purchased = purchase.json()["data"]
        
        # Create phone record
        phone_record = PhoneNumber(
            user_id=current_user.id,
            phone_number=phone_number,
            friendly_name=f"RootCall - {area_code}",
            country_code="US",
            telnyx_phone_number_id=purchased["id"],
            telnyx_connection_id=purchased.get("connection_id", ""),
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
            client_cell=current_user.email,
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
            "rootcall_number": phone_number,
            "message": f"✅ Activated! {phone_number}"
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/api/rootcall/my-number")
async def get_my_number(
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
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


@router.get("/dashboard-setup")
async def get_dashboard_setup(
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: Session = Depends(get_db)
):
    """Get dashboard setup status - AUTHENTICATED"""
    
    # Get first phone number for this user
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.is_active == True
    ).first()
    
    config = None
    if phone:
        config = db.query(RootCallConfig).filter(
            RootCallConfig.phone_number_id == phone.id
        ).first()
    
    # Create config if doesn't exist but user has phone
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
# LANDING PAGE
# ============================================

@router.get("/", response_class=FileResponse)
async def landing_page():
    """Serve RootCall landing page"""
    return FileResponse("static/index.html")