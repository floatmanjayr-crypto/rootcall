"""
Telnyx Webhook Handler
Receives real-time events from Telnyx (calls, messages, etc.)
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import hmac
import hashlib
from datetime import datetime

from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.config import settings
from app.services.openai_service import OpenAIService

router = APIRouter()


def verify_telnyx_signature(payload: bytes, signature: str) -> bool:
    """Verify that the webhook came from Telnyx"""
    if not settings.TELNYX_PUBLIC_KEY:
        return True  # Skip verification in development
    
    expected_signature = hmac.new(
        settings.TELNYX_PUBLIC_KEY.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@router.post("/telnyx")
async def handle_telnyx_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Main webhook endpoint for Telnyx events
    
    Handles:
    - call.initiated
    - call.answered
    - call.hangup
    - call.recording.saved
    - message.received
    - message.sent
    """
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("telnyx-signature-ed25519", "")
    
    # Verify signature (optional in dev)
    if settings.DEBUG is False:
        if not verify_telnyx_signature(body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse event
    event_data = await request.json()
    event_type = event_data.get("data", {}).get("event_type")
    payload = event_data.get("data", {}).get("payload", {})
    
    print(f"í³ž Telnyx Event: {event_type}")
    print(f"Payload: {payload}")
    
    # Route to appropriate handler
    if event_type == "call.initiated":
        return await handle_call_initiated(payload, background_tasks)
    elif event_type == "call.answered":
        return await handle_call_answered(payload, background_tasks)
    elif event_type == "call.hangup":
        return await handle_call_hangup(payload, background_tasks)
    elif event_type == "call.recording.saved":
        return await handle_recording_saved(payload, background_tasks)
    elif event_type == "message.received":
        return await handle_message_received(payload, background_tasks)
    elif event_type == "message.sent":
        return await handle_message_sent(payload, background_tasks)
    
    return {"status": "received", "event_type": event_type}


async def handle_call_initiated(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """Handle incoming call initiated"""
    from app.database import SessionLocal
    db = SessionLocal()
    
    try:
        call_control_id = payload.get("call_control_id")
        from_number = payload.get("from")
        to_number = payload.get("to")
        direction = payload.get("direction", "inbound")
        
        # Find the phone number in our system
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == to_number,
            PhoneNumber.is_active == True
        ).first()
        
        if not phone:
            print(f"âŒ Phone number {to_number} not found in system")
            return

cat > app/api/v1/__init__.py << 'EOF'
from fastapi import APIRouter
from app.api.v1 import auth, phone_numbers, calls, ai_agents
from app.api.v1.webhooks import webhooks_router

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(phone_numbers.router, prefix="/phone-numbers", tags=["Phone Numbers"])
api_router.include_router(calls.router, prefix="/calls", tags=["Calls"])
api_router.include_router(ai_agents.router, prefix="/ai-agents", tags=["AI Agents"])
api_router.include_router(webhooks_router, prefix="/webhooks")
