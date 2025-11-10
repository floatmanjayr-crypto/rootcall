# -*- coding: utf-8 -*-
"""
RootCall Client Portal API Routes - REAL DATA
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.user import User
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


from fastapi.responses import FileResponse

@router.get("/", response_class=FileResponse)
async def landing_page():
    """Serve RootCall landing page"""
    return FileResponse("static/index.html")

@router.post("/provision")
async def provision_rootcall_number(
    data: dict,
    db: Session = Depends(get_db)
):
    """Purchase and configure RootCall number for user"""
    import requests
    
    user_id = data.get("user_id")
    area_code = data.get("area_code", "813")
    client_cell = data.get("client_cell")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # 1. Purchase Telnyx number
        headers = {"Authorization": f"Bearer {settings.TELNYX_API_KEY}"}
        search_response = requests.get(
            "https://api.telnyx.com/v2/available_phone_numbers",
            headers=headers,
            params={
                "filter[country_code]": "US",
                "filter[features]": "sms,voice",
                "filter[national_destination_code]": area_code,
                "filter[limit]": 1
            }
        )
        
        if search_response.status_code != 200 or not search_response.json().get("data"):
            raise HTTPException(status_code=400, detail="No numbers available")
        
        phone_data = search_response.json()["data"][0]
        phone_number = phone_data["phone_number"]
        phone_id = phone_data["id"]
        
        # Purchase
        purchase_response = requests.post(
            f"https://api.telnyx.com/v2/phone_numbers/{phone_id}/actions/purchase",
            headers=headers
        )
        
        if purchase_response.status_code not in [200, 201]:
            raise HTTPException(status_code=400, detail="Purchase failed")
        
        # 2. Create Retell LLM
        retell_headers = {
            "Authorization": f"Bearer {settings.RETELL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        llm_response = requests.post(
            "https://api.retellai.com/create-retell-llm",
            headers=retell_headers,
            json={
                "general_prompt": f"You are RootCall, protecting {user.full_name} from phone scams. Screen calls and detect fraud.",
                "model": "gpt-4o-mini"
            }
        )
        llm_id = llm_response.json()["llm_id"]
        
        # 3. Create Retell Agent
        agent_response = requests.post(
            "https://api.retellai.com/create-agent",
            headers=retell_headers,
            json={
                "agent_name": f"RootCall - {user.full_name}",
                "llm_id": llm_id,
                "voice_id": "11labs-Adrian"
            }
        )
        agent_id = agent_response.json()["agent_id"]
        
        # 4. Import to Retell
        requests.post(
            "https://api.retellai.com/import-phone-number",
            headers=retell_headers,
            json={"phone_number": phone_number, "agent_id": agent_id}
        )
        
        # 5. Save to database
        phone = PhoneNumber(
            user_id=user_id,
            phone_number=phone_number,
            friendly_name=f"RootCall - {user.full_name}",
            is_active=True
        )
        db.add(phone)
        db.flush()
        
        agent = AIAgent(
            user_id=user_id,
            name=f"RootCall Agent",
            retell_agent_id=agent_id,
            retell_llm_id=llm_id,
            is_active=True
        )
        db.add(agent)
        db.flush()
        
        config = RootCallConfig(
            phone_number_id=phone.id,
            user_id=user_id,
            client_name=user.full_name,
            client_cell=client_cell,
            retell_agent_id=agent_id,
            retell_did=phone_number,
            is_active=True
        )
        db.add(config)
        db.commit()
        
        return {
            "success": True,
            "rootcall_number": phone_number,
            "agent_id": agent_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# USER-AUTHENTICATED ENDPOINTS (JWT Required)
# ============================================

from app.core.security import get_current_user

@router.get("/api/rootcall/my-number")
async def get_my_number(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's provisioned RootCall number"""
    
    # Find user's phone number
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.is_active == True
    ).first()
    
    if not phone:
        return {
            "has_number": False,
            "message": "No active RootCall number found. Please complete payment to get started."
        }
    
    # Get associated config
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id
    ).first()
    
    return {
        "has_number": True,
        "number": phone.phone_number,
        "friendly_name": phone.friendly_name,
        "purchased_at": phone.purchased_at.isoformat(),
        "monthly_cost": phone.monthly_cost,
        "config": {
            "screening_enabled": config.is_active if config else True,
            "forwarding_number": config.client_cell if config else None,
            "trusted_contacts": config.trusted_contacts if config else [],
            "sms_alerts_enabled": config.sms_alerts_enabled if config else True
        } if config else None
    }


@router.get("/api/rootcall/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete dashboard data for current user"""
    
    # Get user's phone number
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.is_active == True
    ).first()
    
    if not phone:
        return {
            "has_number": False,
            "user": {
                "name": current_user.full_name,
                "email": current_user.email
            }
        }
    
    # Get config
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id
    ).first()
    
    # Get recent call stats (mock for now - you can add real call logs later)
    return {
        "has_number": True,
        "user": {
            "name": current_user.full_name,
            "email": current_user.email
        },
        "phone": {
            "number": phone.phone_number,
            "friendly_name": phone.friendly_name,
            "purchased_at": phone.purchased_at.isoformat(),
            "status": "active" if phone.is_active else "inactive"
        },
        "config": {
            "screening_enabled": config.is_active if config else True,
            "forwarding_number": config.client_cell if config else None,
            "trusted_contacts": config.trusted_contacts if config else [],
            "sms_alerts": config.sms_alerts_enabled if config else True,
            "auto_block_spam": config.auto_block_spam if config else True
        } if config else None,
        "stats": {
            "calls_today": 0,
            "calls_blocked": 0,
            "calls_forwarded": 0,
            "total_calls": 0
        }
    }


@router.post("/api/rootcall/update-forwarding")
async def update_forwarding_number(
    forwarding_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update where calls should be forwarded"""
    
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="No phone number found")
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id
    ).first()
    
    if config:
        config.client_cell = forwarding_number
    else:
        config = RootCallConfig(
            phone_number_id=phone.id,
            user_id=current_user.id,
            client_name=current_user.full_name,
            client_cell=forwarding_number,
            retell_agent_id=phone.ai_agent.retell_agent_id if phone.ai_agent else "",
            retell_did=phone.phone_number
        )
        db.add(config)
    
    db.commit()
    
    return {"message": "Forwarding number updated", "number": forwarding_number}


@router.post("/api/rootcall/add-trusted-contact")
async def add_trusted_contact_auth(
    phone_number: str,
    name: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a trusted contact (whitelist)"""
    
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="No phone number found")
    
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Add to trusted contacts list
    if not config.trusted_contacts:
        config.trusted_contacts = []
    
    if phone_number not in config.trusted_contacts:
        config.trusted_contacts.append(phone_number)
        db.commit()
    
    return {"message": "Contact added", "contacts": config.trusted_contacts}

