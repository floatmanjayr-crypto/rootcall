"""TeXML Router with Streaming OpenAI"""
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from app.config import settings
from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.services.openai_streaming_service import streaming_service

router = APIRouter(prefix="/texml", tags=["TeXML Streaming"])
log = logging.getLogger(__name__)

@router.post("/voice")
async def handle_incoming_call(request: Request, db: Session = Depends(get_db)):
    """Handle incoming call with streaming TTS"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    
    log.info(f"Call: {from_number} -> {to_number}")
    
    greeting = "Hello! How can I help you today?"
    
    # Look up custom greeting
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == to_number,
        PhoneNumber.is_active == True
    ).first()
    
    if phone and phone.ai_agent_id:
        agent = db.query(AIAgent).filter(AIAgent.id == phone.ai_agent_id).first()
        if agent and agent.greeting_message:
            greeting = agent.greeting_message
    
    try:
        # Stream TTS
        audio_url = await streaming_service.text_to_speech_streaming(greeting, voice="nova")
        host = str(request.url.scheme) + "://" + str(request.url.netloc)
        full_url = host + audio_url
        
        xml = '<?xml version="1.0"?>'
        xml += '<Response>'
        xml += f'<Play>{full_url}</Play>'
        xml += '<Record timeout="2" speechTimeout="auto" action="/texml/process" method="POST" />'
        xml += '</Response>'
        return Response(content=xml, media_type="application/xml")
    
    except Exception as e:
        log.error(f"Error: {e}")
        xml = '<?xml version="1.0"?>'
        xml += '<Response><Say>Hello</Say>'
        xml += '<Record timeout="2" action="/texml/process" method="POST" />'
        xml += '</Response>'
        return Response(content=xml, media_type="application/xml")

@router.post("/process")
async def process_speech(request: Request, db: Session = Depends(get_db)):
    """Process speech with streaming"""
    form_data = await request.form()
    recording_url = form_data.get("RecordingUrl", "")
    call_sid = form_data.get("CallSid", "")
    
    if not recording_url:
        xml = '<?xml version="1.0"?><Response><Say>No audio</Say></Response>'
        return Response(content=xml, media_type="application/xml")
    
    try:
        # Transcribe (parallel processing)
        transcript = await streaming_service.transcribe_audio(recording_url)
        log.info(f"User: {transcript}")
        
        if not transcript or len(transcript.strip()) < 2:
            raise Exception("Empty transcript")
        
        # Get AI response
        call = db.query(Call).filter(Call.call_control_id == call_sid).first()
        system_prompt = None
        if call and call.ai_agent_id:
            agent = db.query(AIAgent).filter(AIAgent.id == call.ai_agent_id).first()
            if agent:
                system_prompt = agent.system_prompt
        
        ai_response = await streaming_service.get_ai_response_streaming(
            transcript, call_sid, system_prompt
        )
        log.info(f"AI: {ai_response}")
        
        # Stream TTS response
        audio_url = await streaming_service.text_to_speech_streaming(ai_response, voice="nova")
        host = str(request.url.scheme) + "://" + str(request.url.netloc)
        full_url = host + audio_url
        
        xml = '<?xml version="1.0"?>'
        xml += '<Response>'
        xml += f'<Play>{full_url}</Play>'
        xml += '<Record timeout="2" speechTimeout="auto" action="/texml/process" method="POST" />'
        xml += '</Response>'
        return Response(content=xml, media_type="application/xml")
    
    except Exception as e:
        log.error(f"Error: {e}")
        xml = '<?xml version="1.0"?><Response><Say>Sorry, try again</Say>'
        xml += '<Record timeout="2" action="/texml/process" method="POST" /></Response>'
        return Response(content=xml, media_type="application/xml")

@router.post("/status")
async def handle_status(request: Request, db: Session = Depends(get_db)):
    """Handle call status"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    call_status = form_data.get("CallStatus", "")
    
    log.info(f"Status: {call_sid} - {call_status}")
    streaming_service.clear_conversation(call_sid)
    
    if call_status == "completed":
        call = db.query(Call).filter(Call.call_control_id == call_sid).first()
        if call:
            call.status = "completed"
            call.ended_at = datetime.utcnow()
            db.commit()
    
    return {"ok": True}
