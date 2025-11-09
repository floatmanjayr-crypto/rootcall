# -*- coding: utf-8 -*-
"""
RootCall Client Portal API Routes - REAL DATA
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.rootcall_config import RootCallConfig
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.models.rootcall_call_log import RootCallCallLog
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(tags=["RootCall Portal"])

class ConfigUpdate(BaseModel):
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None

class TrustedContactAdd(BaseModel):
    phone_number: str
    name: Optional[str] = None

@router.get("/api/rootcall/stats/{client_id}")
async def get_stats(client_id: int, db: Session = Depends(get_db)):
    """Get REAL RootCall protection stats"""
    # Get all phone numbers for this user
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        return {
            "spam_blocked": 0,
            "calls_screened": 0,
            "trusted_forwarded": 0,
            "total_calls": 0
        }
    
    # Count by action
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
async def get_recent_calls(client_id: int, db: Session = Depends(get_db)):
    """Get REAL recent call activity"""
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        return []
    
    # Get last 20 calls
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
async def get_config(client_id: int, db: Session = Depends(get_db)):
    """Get RootCall configuration"""
    user = db.query(User).filter(User.id == client_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    
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
async def update_config(client_id: int, updates: ConfigUpdate, db: Session = Depends(get_db)):
    """Update RootCall configuration"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404)
    
    config = db.query(RootCallConfig).filter(RootCallConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404)
    
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
async def add_trusted_contact(client_id: int, contact: TrustedContactAdd, db: Session = Depends(get_db)):
    """Add trusted contact"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404)
    
    config = db.query(RootCallConfig).filter(RootCallConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404)
    
    if not config.trusted_contacts:
        config.trusted_contacts = []
    
    if contact.phone_number not in config.trusted_contacts:
        config.trusted_contacts.append(contact.phone_number)
        db.commit()
    
    return {"success": True}

@router.delete("/api/rootcall/trusted-contacts/{client_id}/{phone_number}")
async def remove_trusted_contact(client_id: int, phone_number: str, db: Session = Depends(get_db)):
    """Remove trusted contact"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404)
    
    config = db.query(RootCallConfig).filter(RootCallConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404)
    
    if config.trusted_contacts and phone_number in config.trusted_contacts:
        config.trusted_contacts.remove(phone_number)
        db.commit()
    
    return {"success": True}


@router.get("/api/rootcall/export/{client_id}")
async def export_calls(client_id: int, db: Session = Depends(get_db)):
    """Export call logs as CSV"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        raise HTTPException(status_code=404)
    
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
