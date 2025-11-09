# -*- coding: utf-8 -*-
"""
Setup Real Call Logging and Stats
"""
import subprocess

print("="*60)
print("SETTING UP REAL BADBOT STATS")
print("="*60)

# 1. Create the model
print("\n1. Creating BadBotCallLog model...")
model_code = '''"""
BadBot Call Logs Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class BadBotCallLog(Base):
    __tablename__ = "badbot_call_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"))
    from_number = Column(String(20), nullable=False)
    caller_name = Column(String(255))
    action = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    call_control_id = Column(String(255))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
'''

with open('app/models/badbot_call_log.py', 'w') as f:
    f.write(model_code)
print("   ✓ Model created")

# 2. Update badbot_portal.py to use real stats
print("\n2. Updating API to use real stats...")

portal_code = '''# -*- coding: utf-8 -*-
"""
BadBot Client Portal API Routes - REAL DATA
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.badbot_config import BadBotConfig
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.models.badbot_call_log import BadBotCallLog
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter(tags=["BadBot Portal"])

class ConfigUpdate(BaseModel):
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None

class TrustedContactAdd(BaseModel):
    phone_number: str
    name: Optional[str] = None

@router.get("/api/badbot/stats/{client_id}")
async def get_stats(client_id: int, db: Session = Depends(get_db)):
    """Get REAL BadBot protection stats"""
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
    spam_blocked = db.query(BadBotCallLog).filter(
        BadBotCallLog.phone_number_id.in_(phone_ids),
        BadBotCallLog.action == "spam_blocked"
    ).count()
    
    calls_screened = db.query(BadBotCallLog).filter(
        BadBotCallLog.phone_number_id.in_(phone_ids),
        BadBotCallLog.action == "screened"
    ).count()
    
    trusted_forwarded = db.query(BadBotCallLog).filter(
        BadBotCallLog.phone_number_id.in_(phone_ids),
        BadBotCallLog.action == "trusted_forwarded"
    ).count()
    
    total_calls = db.query(BadBotCallLog).filter(
        BadBotCallLog.phone_number_id.in_(phone_ids)
    ).count()
    
    return {
        "spam_blocked": spam_blocked,
        "calls_screened": calls_screened,
        "trusted_forwarded": trusted_forwarded,
        "total_calls": total_calls
    }

@router.get("/api/badbot/calls/{client_id}")
async def get_recent_calls(client_id: int, db: Session = Depends(get_db)):
    """Get REAL recent call activity"""
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        return []
    
    # Get last 20 calls
    logs = db.query(BadBotCallLog).filter(
        BadBotCallLog.phone_number_id.in_(phone_ids)
    ).order_by(BadBotCallLog.timestamp.desc()).limit(20).all()
    
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

@router.get("/api/badbot/config/{client_id}")
async def get_config(client_id: int, db: Session = Depends(get_db)):
    """Get BadBot configuration"""
    user = db.query(User).filter(User.id == client_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="No phone number")
    
    config = db.query(BadBotConfig).filter(BadBotConfig.phone_number_id == phone.id).first()
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

@router.patch("/api/badbot/config/{client_id}")
async def update_config(client_id: int, updates: ConfigUpdate, db: Session = Depends(get_db)):
    """Update BadBot configuration"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404)
    
    config = db.query(BadBotConfig).filter(BadBotConfig.phone_number_id == phone.id).first()
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

@router.post("/api/badbot/trusted-contacts/{client_id}")
async def add_trusted_contact(client_id: int, contact: TrustedContactAdd, db: Session = Depends(get_db)):
    """Add trusted contact"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404)
    
    config = db.query(BadBotConfig).filter(BadBotConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404)
    
    if not config.trusted_contacts:
        config.trusted_contacts = []
    
    if contact.phone_number not in config.trusted_contacts:
        config.trusted_contacts.append(contact.phone_number)
        db.commit()
    
    return {"success": True}

@router.delete("/api/badbot/trusted-contacts/{client_id}/{phone_number}")
async def remove_trusted_contact(client_id: int, phone_number: str, db: Session = Depends(get_db)):
    """Remove trusted contact"""
    phone = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).first()
    if not phone:
        raise HTTPException(status_code=404)
    
    config = db.query(BadBotConfig).filter(BadBotConfig.phone_number_id == phone.id).first()
    if not config:
        raise HTTPException(status_code=404)
    
    if config.trusted_contacts and phone_number in config.trusted_contacts:
        config.trusted_contacts.remove(phone_number)
        db.commit()
    
    return {"success": True}
'''

with open('app/routers/badbot_portal.py', 'w') as f:
    f.write(portal_code)
print("   ✓ API updated with real stats")

# 3. Add logging to badbot_screen.py
print("\n3. Adding call logging to webhook...")

with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add import
if 'BadBotCallLog' not in content:
    content = content.replace(
        'from app.models.badbot_config import BadBotConfig',
        'from app.models.badbot_config import BadBotConfig\nfrom app.models.badbot_call_log import BadBotCallLog'
    )
    print("   ✓ Added import")

# Add logging after spam block
spam_log = '''            # Log spam block
            log_entry = BadBotCallLog(
                phone_number_id=phone_id,
                from_number=from_num,
                caller_name=cnam,
                action="spam_blocked",
                status="blocked",
                call_control_id=ccid
            )
            db.add(log_entry)
            db.commit()
            
            await telnyx_hangup(ccid)'''

if 'BadBotCallLog' in content and 'spam_blocked' not in content:
    content = content.replace(
        'await telnyx_hangup(ccid)\n            return {"status": "spam_blocked"}',
        spam_log + '\n            return {"status": "spam_blocked"}'
    )
    print("   ✓ Added spam block logging")

# Add logging for screening
screening_log = '''        # Log screening
        log_entry = BadBotCallLog(
            phone_number_id=phone_id,
            from_number=from_num,
            caller_name=cnam,
            action="screened",
            status="screening",
            call_control_id=ccid
        )
        db.add(log_entry)
        db.commit()
        
        await telnyx_gather_speak('''

if 'screened' not in content:
    content = content.replace(
        'await telnyx_gather_speak(\n            ccid,',
        screening_log + '\n            ccid,'
    )
    print("   ✓ Added screening logging")

# Add logging for trusted forward
trusted_log = '''            # Log trusted forward
            log_entry = BadBotCallLog(
                phone_number_id=phone_id,
                from_number=from_num,
                caller_name=cnam,
                action="trusted_forwarded",
                status="answered",
                call_control_id=ccid
            )
            db.add(log_entry)
            db.commit()
            
            await telnyx_transfer(ccid, client_cell)'''

if 'trusted_forwarded' not in content:
    content = content.replace(
        'await telnyx_transfer(ccid, client_cell)\n            return {"status": "trusted_forwarded"}',
        trusted_log + '\n            return {"status": "trusted_forwarded"}'
    )
    print("   ✓ Added trusted forward logging")

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

print("\n4. Creating database table...")

# Create SQL
sql = '''
CREATE TABLE IF NOT EXISTS badbot_call_logs (
    id SERIAL PRIMARY KEY,
    phone_number_id INTEGER REFERENCES phone_numbers(id),
    from_number VARCHAR(20) NOT NULL,
    caller_name VARCHAR(255),
    action VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    call_control_id VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_badbot_logs_phone ON badbot_call_logs(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_badbot_logs_timestamp ON badbot_call_logs(timestamp);
'''

with open('create_badbot_logs.sql', 'w') as f:
    f.write(sql)

print("   ✓ SQL file created: create_badbot_logs.sql")

print("\n" + "="*60)
print("SETUP COMPLETE!")
print("="*60)
print("\nNext steps:")
print("1. Run SQL migration:")
print("   Get database URL from .env and run:")
print("   psql <your-db-url> < create_badbot_logs.sql")
print("")
print("2. Server will reload automatically")
print("3. Make test calls to +18135478530")
print("4. Portal will show REAL stats!")
print("="*60)

# Show DB command
with open('.env', 'r') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            db_url = line.split('=', 1)[1].strip()
            print(f"\nQuick command:")
            print(f'psql "{db_url}" < create_badbot_logs.sql')
            break

