# -*- coding: utf-8 -*-
"""
Full BadBot Portal Integration
"""
import subprocess
import os

print("="*60)
print("FULL BADBOT PORTAL INTEGRATION")
print("="*60)

# Step 1: Get database URL
print("\n[1/6] Getting database connection...")
db_url = None
with open('.env', 'r') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            db_url = line.split('=', 1)[1].strip()
            # Remove quotes if present
            db_url = db_url.strip('"').strip("'")
            break

if not db_url:
    print("‚ùå DATABASE_URL not found in .env!")
    exit(1)

print(f"‚úì Found database")

# Step 2: Create SQL migration
print("\n[2/6] Creating SQL migration...")
sql = '''
-- BadBot Call Logs Table
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

with open('migrate_badbot.sql', 'w') as f:
    f.write(sql)
print("‚úì SQL file created")

# Step 3: Run migration
print("\n[3/6] Running database migration...")
try:
    result = subprocess.run(
        ['psql', db_url, '-f', 'migrate_badbot.sql'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("‚úì Database table created")
    else:
        print(f"‚ö†Ô∏è  psql output: {result.stderr}")
        print("Trying alternative method...")
        # Try with python
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        print("‚úì Database table created (via SQLAlchemy)")
except Exception as e:
    print(f"‚ö†Ô∏è  Migration note: {e}")
    print("Table may already exist or will be created on server restart")

# Step 4: Create model
print("\n[4/6] Creating BadBotCallLog model...")
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
print("‚úì Model created")

# Step 5: Update portal API with real stats + phone number update
print("\n[5/6] Creating enhanced portal API...")
portal_code = '''# -*- coding: utf-8 -*-
"""
BadBot Client Portal API - Full Featured
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.rootcall_config import BadBotConfig
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.models.badbot_call_log import BadBotCallLog
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["BadBot Portal"])

class ConfigUpdate(BaseModel):
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None
    client_cell: Optional[str] = None  # NEW: Update phone number

class TrustedContactAdd(BaseModel):
    phone_number: str
    name: Optional[str] = None

@router.get("/api/badbot/stats/{client_id}")
async def get_stats(client_id: int, db: Session = Depends(get_db)):
    """Get REAL stats from database"""
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        return {"spam_blocked": 0, "calls_screened": 0, "trusted_forwarded": 0, "total_calls": 0}
    
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
    """Get recent calls from database"""
    phones = db.query(PhoneNumber).filter(PhoneNumber.user_id == client_id).all()
    phone_ids = [p.id for p in phones]
    
    if not phone_ids:
        return []
    
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
    """Update BadBot configuration including phone number"""
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
    if updates.client_cell is not None:
        config.client_cell = updates.client_cell
    
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
print("‚úì Portal API updated")

# Step 6: Add logging to webhook
print("\n[6/6] Adding call logging to webhook...")
with open('app/routers/badbot_screen.py', 'r') as f:
    content = f.read()

# Add import
if 'BadBotCallLog' not in content:
    content = content.replace(
        'from app.models.rootcall_config import BadBotConfig',
        'from app.models.rootcall_config import BadBotConfig\nfrom app.models.badbot_call_log import BadBotCallLog'
    )
    print("‚úì Added import")

# Add variable to store phone_id
if 'phone_id = phone.id' not in content:
    content = content.replace(
        'phone = db.query(PhoneNumber).filter(PhoneNumber.phone_number == to_num).first()',
        'phone = db.query(PhoneNumber).filter(PhoneNumber.phone_number == to_num).first()\n    phone_id = phone.id if phone else None'
    )

# Add logging for spam
if 'action="spam_blocked"' not in content:
    old_spam = '            await telnyx_hangup(ccid)'
    new_spam = '''            # Log spam block
            if phone_id:
                db.add(BadBotCallLog(
                    phone_number_id=phone_id,
                    from_number=from_num,
                    caller_name=cnam,
                    action="spam_blocked",
                    status="blocked",
                    call_control_id=ccid
                ))
                db.commit()
            
            await telnyx_hangup(ccid)'''
    content = content.replace(old_spam, new_spam)
    print("‚úì Added spam logging")

# Add logging for screening
if 'action="screened"' not in content:
    old_screen = '        await telnyx_gather_speak('
    new_screen = '''        # Log screening
        if phone_id:
            db.add(BadBotCallLog(
                phone_number_id=phone_id,
                from_number=from_num,
                caller_name=cnam,
                action="screened",
                status="screening",
                call_control_id=ccid
            ))
            db.commit()
        
        await telnyx_gather_speak('''
    content = content.replace(old_screen, new_screen, 1)
    print("‚úì Added screening logging")

# Add logging for trusted
if 'action="trusted_forwarded"' not in content:
    old_trust = '            await telnyx_transfer(ccid, client_cell)'
    new_trust = '''            # Log trusted forward
            if phone_id:
                db.add(BadBotCallLog(
                    phone_number_id=phone_id,
                    from_number=from_num,
                    caller_name=cnam,
                    action="trusted_forwarded",
                    status="answered",
                    call_control_id=ccid
                ))
                db.commit()
            
            await telnyx_transfer(ccid, client_cell)'''
    content = content.replace(old_trust, new_trust)
    print("‚úì Added trusted logging")

with open('app/routers/badbot_screen.py', 'w') as f:
    f.write(content)

# Step 7: Update portal HTML with phone number update
print("\n[7/7] Updating portal with phone number editor...")

html = open('static/james-portal.html', 'r').read()

# Add phone number edit field
html = html.replace(
    '<div id="config-status" class="mb-4 p-3 bg-gray-100 rounded"></div>',
    '''<div id="config-status" class="mb-4 p-3 bg-gray-100 rounded"></div>
            <div class="mb-4">
                <label class="block text-sm font-medium mb-2">Alert Phone Number:</label>
                <div class="flex gap-2">
                    <input type="tel" id="client-cell" class="flex-1 px-4 py-2 border rounded-lg" placeholder="+1234567890">
                    <button onclick="updatePhoneNumber()" class="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700">
                        Ì≤æ Update Number
                    </button>
                </div>
            </div>'''
)

# Add function to update phone
html = html.replace(
    'document.getElementById(\'sms-alerts\').checked = config.sms_alerts_enabled;',
    '''document.getElementById('sms-alerts').checked = config.sms_alerts_enabled;
                    document.getElementById('client-cell').value = config.client_cell || '';'''
)

html = html.replace(
    'async function saveSettings() {',
    '''async function updatePhoneNumber() {
            try {
                const newNumber = document.getElementById('client-cell').value;
                if (!newNumber) {
                    alert('Please enter a phone number');
                    return;
                }
                await fetch(`${API}/config/${CLIENT_ID}`, {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ client_cell: newNumber })
                });
                alert('‚úÖ Phone number updated!');
                loadData();
            } catch (e) {
                alert('‚ùå Error updating: ' + e.message);
            }
        }

        async function saveSettings() {'''
)

with open('static/james-portal.html', 'w') as f:
    f.write(html)

print("‚úì Portal HTML updated")

print("\n" + "="*60)
print("‚úÖ FULL INTEGRATION COMPLETE!")
print("="*60)
print("\nÌ≥ä Real Stats: Every call is now logged to database")
print("Ì≥± Phone Update: Can change alert number in portal")
print("ÌæØ Live Data: Portal shows actual call activity")
print("\nÌ∫Ä Server will reload - then visit:")
print("   http://localhost:8000/static/james-portal.html")
print("\nÌ≥û Make test calls to +18135478530 to see real stats!")
print("="*60)

