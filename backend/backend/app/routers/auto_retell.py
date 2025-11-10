"""Fully Automated Retell Bridge - No Manual Steps Required"""
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
import httpx
import json
import logging
from datetime import datetime
from app.config import settings
from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent

router = APIRouter(prefix="/auto-retell", tags=["Auto Retell"])
log = logging.getLogger(__name__)

# Store active call mappings
active_calls = {}

@router.post("/webhook")
async def telnyx_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Telnyx webhooks and automatically create Retell calls"""
    
    data = await request.json()
    event_type = data.get("data", {}).get("event_type")
    payload = data.get("data", {}).get("payload", {})
    
    log.info(f"í³ Event: {event_type}")
    
    if event_type == "call.initiated":
        call_control_id = payload.get("call_control_id")
        from_number = payload.get("from")
        to_number = payload.get("to")
        
        log.info(f"í³² Incoming: {from_number} â {to_number}")
        
        # Look up which AI agent to use
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == to_number,
            PhoneNumber.is_active == True
        ).first()
        
        if not phone or not phone.ai_agent_id:
            log.error(f"â No AI agent for {to_number}")
            return {"status": "no_agent"}
        
        # Get AI agent
        agent = db.query(AIAgent).filter(AIAgent.id == phone.ai_agent_id).first()
        
        if not agent or not agent.ai_model or not agent.ai_model.startswith("retell:"):
            log.error(f"â Invalid agent config")
            return {"status": "invalid_agent"}
        
        retell_agent_id = agent.ai_model.replace("retell:", "")
        log.info(f"í´ Using agent: {retell_agent_id}")
        
        # Answer the call
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/answer",
                headers={
                    "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            log.info(f"â Answered call")
        
        # Create Retell phone call
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                retell_response = await client.post(
                    "https://api.retellai.com/v2/create-phone-call",
                    headers={
                        "Authorization": f"Bearer {settings.RETELL_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from_number": to_number,
                        "to_number": from_number,
                        "agent_id": retell_agent_id,
                        "metadata": {
                            "telnyx_call_id": call_control_id,
                            "client_id": str(phone.user_id)
                        }
                    }
                )
                
                log.info(f"Retell: {retell_response.status_code}")
                log.info(f"Body: {retell_response.text}")
                
                if retell_response.status_code in [200, 201]:
                    retell_data = retell_response.json()
                    retell_call_id = retell_data.get("call_id")
                    
                    log.info(f"â Retell call: {retell_call_id}")
                    
                    # Save to database
                    call = Call(
                        user_id=phone.user_id,
                        phone_number_id=phone.id,
                        call_control_id=call_control_id,
                        telnyx_call_id=call_control_id,
                        direction="inbound",
                        from_number=from_number,
                        to_number=to_number,
                        status="in-progress",
                        ai_agent_id=phone.ai_agent_id,
                        started_at=datetime.utcnow()
                    )
                    db.add(call)
                    db.commit()
                    
                    log.info(f"í¾ Call bridged!")
                    
        except Exception as e:
            log.error(f"â Exception: {e}")
            import traceback
            traceback.print_exc()
    
    elif event_type == "call.hangup":
        call_control_id = payload.get("call_control_id")
        log.info(f"í³´ Call ended: {call_control_id}")
        
        # Update database
        call = db.query(Call).filter(Call.call_control_id == call_control_id).first()
        
        if call:
            call.status = "completed"
            call.duration = payload.get("duration_seconds", 0)
            call.ended_at = datetime.utcnow()
            
            # Calculate cost
            minutes = call.duration / 60
            call.cost = round(minutes * 0.13, 4)
            
            db.commit()
            log.info(f"í²° Cost: ${call.cost}")
    
    return {"status": "ok"}

@router.get("/health")
async def health():
    return {"status": "ok", "message": "Auto Retell bridge running"}
