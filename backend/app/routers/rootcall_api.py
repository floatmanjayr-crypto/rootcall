from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.rootcall_config import RootCallConfig
from app.models.phone_number import PhoneNumber
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/rootcall", tags=["BadBot API"])

class ConfigUpdate(BaseModel):
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None

class TrustedContactAdd(BaseModel):
    phone_number: str

@router.get("/config")
async def get_config(db: Session = Depends(get_db)):
    """Get BadBot configuration for current user"""
    # TODO: Get user_id from auth token
    user_id = 1  # Placeholder
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    return {
        "client_name": config.client_name,
        "client_cell": config.client_cell,
        "trusted_contacts": config.trusted_contacts or [],
        "sms_alerts_enabled": config.sms_alerts_enabled,
        "alert_on_spam": config.alert_on_spam,
        "alert_on_unknown": config.alert_on_unknown,
        "auto_block_spam": config.auto_block_spam,
        "is_active": config.is_active
    }

@router.patch("/config")
async def update_config(
    updates: ConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update BadBot configuration"""
    user_id = 1  # Placeholder
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Update fields
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    return {"success": True, "config": config}

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get BadBot statistics"""
    # TODO: Implement actual stats from call logs
    return {
        "spam_blocked": 42,
        "calls_screened": 156,
        "success_rate": "98%",
        "recent_calls": []
    }

@router.post("/trusted-contacts")
async def add_trusted_contact(
    contact: TrustedContactAdd,
    db: Session = Depends(get_db)
):
    """Add trusted contact"""
    user_id = 1
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if config.trusted_contacts is None:
        config.trusted_contacts = []
    
    if contact.phone_number not in config.trusted_contacts:
        config.trusted_contacts.append(contact.phone_number)
        db.commit()
    
    return {"success": True}

@router.delete("/trusted-contacts/{phone_number}")
async def remove_trusted_contact(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """Remove trusted contact"""
    user_id = 1
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if config.trusted_contacts and phone_number in config.trusted_contacts:
        config.trusted_contacts.remove(phone_number)
        db.commit()
    
    return {"success": True}
