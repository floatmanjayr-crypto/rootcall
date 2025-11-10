from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import httpx
import asyncio

from openai import OpenAI
from app.config import settings
from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent

router = APIRouter(prefix="/telnyx/webhooks", tags=["Telnyx Webhooks"])
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TELNYX_BASE = "https://api.telnyx.com/v2"
HEADERS_JSON = {
    "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
    "Content-Type": "application/json",
}
deepgram = None  # deepgram disabled
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Cache agent data as dict (not SQLAlchemy objects)
agent_cache = {}
conversation_history = {}
call_states = {}

async def _post(url: str, json_data: dict):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, headers=HEADERS_JSON, json=json_data)
    if r.status_code >= 300:
        log.error("Telnyx error: %s", r.text)
        raise HTTPException(r.status_code, f"Telnyx error: {r.text}")
    return r

async def transcribe_with_deepgram(audio_url: str) -> str:
    """Deepgram disabled; return empty transcript."""
    return ""

async def speak_text(text: str, call_control_id: str):
    try:
        await _post(
            f"{TELNYX_BASE}/calls/{call_control_id}/actions/speak",
            {"payload": text, "voice": "female", "language": "en-US"}
        )
    except Exception as e:
        log.error("Speak failed: %s", e)

async def start_listening(call_control_id: str):
    try:
        call_states[call_control_id] = "listening"
        await _post(
            f"{TELNYX_BASE}/calls/{call_control_id}/actions/record_start",
            {"format": "mp3", "channels": "single", "max_length": 8, "play_beep": False}
        )
        
        await asyncio.sleep(2)
        if call_states.get(call_control_id) == "listening":
            await _post(f"{TELNYX_BASE}/calls/{call_control_id}/actions/record_stop", {})
    except Exception as e:
        log.error("Listen failed: %s", e)

async def get_ai_response(user_message: str, call_control_id: str, system_prompt: str) -> str:
    try:
        if call_control_id not in conversation_history:
            conversation_history[call_control_id] = [{"role": "system", "content": system_prompt}]
        
        conversation_history[call_control_id].append({"role": "user", "content": user_message})
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history[call_control_id],
            temperature=0.7,
            max_tokens=80
        )
        
        ai_response = response.choices[0].message.content
        conversation_history[call_control_id].append({"role": "assistant", "content": ai_response})
        
        log.info("AI: %s", ai_response[:50])
        return ai_response
    except Exception as e:
        log.error("OpenAI failed: %s", e)
        return "I'm sorry, could you repeat that?"

@router.post("/voice")
async def telnyx_voice_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    
    data = body.get("data", {})
    event_type = data.get("event_type")
    payload = data.get("payload", {})
    call_control_id = payload.get("call_control_id")
    from_number = payload.get("from")
    to_number = payload.get("to")
    
    log.info("%s - %s", event_type, call_control_id[:20])
    
    if event_type == "call.initiated":
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == to_number,
            PhoneNumber.is_active.is_(True),
        ).first()
        
        if not phone:
            return {"ok": False}
        
        # Cache agent data as dict
        if phone.ai_agent_id:
            agent = db.query(AIAgent).filter(AIAgent.id == phone.ai_agent_id).first()
            if agent:
                agent_cache[call_control_id] = {
                    "greeting_message": agent.greeting_message,
                    "system_prompt": agent.system_prompt
                }
        
        call = Call(
            user_id=phone.user_id,
            phone_number_id=phone.id,
            call_control_id=call_control_id,
            telnyx_call_id=payload.get("call_session_id"),
            direction="inbound",
            from_number=from_number,
            to_number=to_number,
            status="initiated",
            ai_agent_id=phone.ai_agent_id,
        )
        db.add(call)
        db.commit()
        
        await _post(f"{TELNYX_BASE}/calls/{call_control_id}/actions/answer", {})
        return {"ok": True}
    
    elif event_type == "call.answered":
        call = db.query(Call).filter(Call.call_control_id == call_control_id).first()
        if call:
            call.status = "answered"
            call.answered_at = datetime.utcnow()
            db.commit()
        
        agent_data = agent_cache.get(call_control_id, {})
        greeting = agent_data.get("greeting_message")
        if greeting:
            await speak_text(greeting, call_control_id)
        
        return {"ok": True}
    
    elif event_type == "call.speak.ended":
        if call_states.get(call_control_id) != "listening":
            await start_listening(call_control_id)
        return {"ok": True}
    
    elif event_type == "call.recording.saved":
        recording_url = payload.get("recording_urls", {}).get("mp3")
        
        if recording_url and call_states.get(call_control_id) == "listening":
            call_states[call_control_id] = "processing"
            
            agent_data = agent_cache.get(call_control_id, {})
            
            transcript = await transcribe_with_deepgram(recording_url)
            
            if transcript and len(transcript.strip()) > 3 and agent_data:
                system_prompt = agent_data.get("system_prompt") or "You are a helpful, concise phone assistant."
                ai_response = await get_ai_response(transcript, call_control_id, system_prompt)
                await speak_text(ai_response, call_control_id)
            else:
                call_states[call_control_id] = "ready"
        
        return {"ok": True}
    
    elif event_type == "call.hangup":
        if call_control_id in conversation_history:
            del conversation_history[call_control_id]
        if call_control_id in call_states:
            del call_states[call_control_id]
        if call_control_id in agent_cache:
            del agent_cache[call_control_id]
        
        call = db.query(Call).filter(Call.call_control_id == call_control_id).first()
        if call:
            call.status = "completed"
            call.ended_at = datetime.utcnow()
            if call.answered_at:
                call.duration = int((call.ended_at - call.answered_at).total_seconds())
            db.commit()
        return {"ok": True}
    
    return {"ok": True}

@router.post("/messaging")
async def telnyx_msg_webhook(request: Request):
    return {"ok": True}
