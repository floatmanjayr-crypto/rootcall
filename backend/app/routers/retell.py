"""Retell.ai Router for Conversational AI"""
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import json
import logging
from retell.lib.webhook_auth import verify
from app.config import settings
from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.services.retell_service import RetellService

router = APIRouter(prefix="/retell", tags=["Retell"])
log = logging.getLogger(__name__)

@router.post("/webhook")
async def handle_retell_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Retell webhooks (call events)"""
    
    body = await request.body()
    if not settings.RETELL_API_KEY:
        raise HTTPException(status_code=503, detail="Retell is not configured")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    if not verify(
        text, settings.RETELL_API_KEY,
        request.headers.get("x-retell-signature", "")
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    if not isinstance(data, dict) or not isinstance(data.get("call"), dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    payload = data["call"]
    event_type = data.get("event")
    call_id = payload.get("call_id")
    if not call_id:
        raise HTTPException(status_code=400, detail="Missing call ID")
    
    log.info(f"Retell webhook: {event_type} - {call_id}")
    
    if event_type not in {"call_started", "transcript_updated", "call_ended", "call_analyzed"}:
        return {"status": "ignored"}

    call = db.query(Call).filter(Call.retell_call_id == call_id).first()
    if not call:
        number = payload.get("from_number") if payload.get("direction") == "outbound" else payload.get("to_number")
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == number,
            PhoneNumber.is_active.is_(True)
        ).first()
        if not phone:
            return {"status": "ignored"}
        call = Call(
            user_id=phone.user_id,
            phone_number_id=phone.id,
            ai_agent_id=phone.ai_agent_id,
            retell_call_id=call_id,
            call_control_id=call_id,
            direction=payload.get("direction", "inbound"),
            from_number=payload.get("from_number"),
            to_number=payload.get("to_number"),
            status="in-progress",
            started_at=datetime.utcnow()
        )
        db.add(call)

    if "transcript" in payload and (call.ended_at is None or event_type in {"call_ended", "call_analyzed"}):
        call.transcription = payload["transcript"]
    if event_type == "call_ended":
        call.duration = int((payload.get("duration_ms") or 0) / 1000)
        if payload.get("disconnection_reason") == "call_take_over":
            call.status = "human-connected"
        else:
            call.status = "completed"
            call.ended_at = datetime.utcnow()
    elif event_type == "call_analyzed":
        analysis = payload.get("call_analysis") or {}
        call.summary = analysis.get("call_summary", "")
        call.sentiment = analysis.get("user_sentiment", "")
        if call.status not in {"takeover-pending", "human-connected"}:
            call.status = "completed"
            call.ended_at = call.ended_at or datetime.utcnow()
    db.commit()

    return {"status": "ok"}

@router.post("/agents/create")
async def create_agent(request: Request, db: Session = Depends(get_db)):
    """Create a new Retell agent"""
    
    data = await request.json()
    name = data.get("name", "Assistant")
    prompt = data.get("system_prompt", "You are a helpful assistant.")
    voice = data.get("voice", "11labs-Adrian")
    
    service = RetellService()
    llm_id = service.create_llm(prompt)
    agent_id = service.create_agent(name, llm_id, voice)
    
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
    
    result = RetellService().update_phone_number(phone_number, inbound_agent_id=agent_id)
    
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
    
    call_id = RetellService().create_phone_call(from_number, to_number, agent_id)
    
    if not call_id:
        raise HTTPException(status_code=500, detail="Failed to create call")
    
    return {"call_id": call_id, "status": "calling"}
