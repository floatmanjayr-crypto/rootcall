"""Retell.ai Router for Conversational AI"""
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from app.config import settings
from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.services.retell_service import retell_service

router = APIRouter(prefix="/retell", tags=["Retell"])
log = logging.getLogger(__name__)

@router.post("/webhook")
async def handle_retell_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Retell webhooks (call events)"""
    
    data = await request.json()
    event_type = data.get("event")
    call_id = data.get("call_id")
    
    log.info(f"Retell webhook: {event_type} - {call_id}")
    
    if event_type == "call_started":
        # Log call start
        call = Call(
            call_control_id=call_id,
            telnyx_call_id=call_id,
            direction="inbound",
            from_number=data.get("from_number"),
            to_number=data.get("to_number"),
            status="in-progress",
            started_at=datetime.utcnow()
        )
        db.add(call)
        db.commit()
    
    elif event_type == "call_ended":
        # Update call record
        call = db.query(Call).filter(Call.call_control_id == call_id).first()
        if call:
            call.status = "completed"
            call.duration = data.get("call_duration", 0)
            call.ended_at = datetime.utcnow()
            call.transcription = data.get("transcript", "")
            db.commit()
    
    elif event_type == "call_analyzed":
        # Store analysis data
        call = db.query(Call).filter(Call.call_control_id == call_id).first()
        if call:
            call.summary = data.get("call_summary", "")
            call.sentiment = data.get("sentiment", "")
            db.commit()
    
    return {"status": "ok"}

@router.post("/agents/create")
async def create_agent(request: Request, db: Session = Depends(get_db)):
    """Create a new Retell agent"""
    
    data = await request.json()
    name = data.get("name", "Assistant")
    prompt = data.get("system_prompt", "You are a helpful assistant.")
    voice = data.get("voice", "11labs-Adrian")
    
    agent_id = retell_service.create_agent(name, prompt, voice)
    
    if not agent_id:
        raise HTTPException(status_code=500, detail="Failed to create agent")
    
    return {"agent_id": agent_id, "status": "created"}

@router.post("/phone-numbers/register")
async def register_number(request: Request, db: Session = Depends(get_db)):
    """Register Telnyx number with Retell"""
    
    data = await request.json()
    phone_number = data.get("phone_number")
    agent_id = data.get("agent_id")
    
    if not phone_number or not agent_id:
        raise HTTPException(status_code=400, detail="Missing phone_number or agent_id")
    
    result = retell_service.register_phone_number(phone_number, agent_id)
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to register number")
    
    return {"status": "registered", "phone_number": phone_number}

@router.post("/calls/create")
async def create_outbound_call(request: Request):
    """Create outbound call via Retell"""
    
    data = await request.json()
    from_number = data.get("from_number")
    to_number = data.get("to_number")
    agent_id = data.get("agent_id")
    
    call_id = retell_service.create_phone_call(from_number, to_number, agent_id)
    
    if not call_id:
        raise HTTPException(status_code=500, detail="Failed to create call")
    
    return {"call_id": call_id, "status": "calling"}
