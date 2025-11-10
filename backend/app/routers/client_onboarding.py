"""Complete Automated Client Onboarding - Using Working Retell Service"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import httpx
import logging
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.services.retell_service import retell_service

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])
log = logging.getLogger(__name__)

class OnboardClientRequest(BaseModel):
    client_id: int
    business_name: str
    phone_number: str
    system_prompt: str
    greeting: Optional[str] = "Hello! How can I help you?"
    voice: Optional[str] = "11labs-Adrian"
    rate_per_minute: Optional[float] = 0.35

@router.post("/start")
async def onboard_client(request: OnboardClientRequest, db: Session = Depends(get_db)):
    """Complete automated onboarding using working Retell service"""
    
    try:
        log.info(f"íº Onboarding: {request.business_name}")
        
        # Verify client exists
        client = db.query(User).filter(User.id == request.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Create AI agent using the working service
        log.info("í´ Creating AI agent...")
        
        agent_id = retell_service.create_agent(
            name=f"{request.business_name} AI",
            system_prompt=request.system_prompt,
            voice=request.voice
        )
        
        if not agent_id:
            raise HTTPException(status_code=500, detail="Failed to create agent")
        
        log.info(f"â Agent: {agent_id}")
        
        # Save to database
        ai_agent = AIAgent(
            user_id=request.client_id,
            name=f"{request.business_name} AI",
            system_prompt=request.system_prompt,
            greeting_message=request.greeting,
            voice_model=request.voice,
            ai_model=f"retell:{agent_id}",
            is_active=True
        )
        db.add(ai_agent)
        db.commit()
        db.refresh(ai_agent)
        
        # Configure phone number
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == request.phone_number
        ).first()
        
        if phone:
            phone.ai_agent_id = ai_agent.id
            phone.user_id = request.client_id
            phone.is_active = True
        else:
            phone = PhoneNumber(
                user_id=request.client_id,
                phone_number=request.phone_number,
                ai_agent_id=ai_agent.id,
                is_active=True
            )
            db.add(phone)
        
        db.commit()
        
        # Auto-configure Telnyx
        webhook_url = f"https://{settings.PUBLIC_DOMAIN}/auto-retell/webhook"
        telnyx_configured = await configure_telnyx(request.phone_number, webhook_url)
        
        # Calculate pricing
        cost_per_min = 0.13
        profit_per_min = request.rate_per_minute - cost_per_min
        
        log.info(f"í¾ {request.business_name} is LIVE!")
        
        return {
            "status": "live",
            "business_name": request.business_name,
            "agent_id": agent_id,
            "phone_number": request.phone_number,
            "webhook_url": webhook_url,
            "telnyx_auto_configured": telnyx_configured,
            "pricing": {
                "cost_per_min": cost_per_min,
                "rate_per_min": request.rate_per_minute,
                "profit_per_min": profit_per_min
            },
            "message": f"â {request.business_name} is live with AI!",
            "manual_step": None if telnyx_configured else f"Set Telnyx webhook to: {webhook_url}"
        }
        
    except Exception as e:
        log.error(f"â Failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def configure_telnyx(phone_number: str, webhook_url: str) -> bool:
    """Auto-configure Telnyx"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Find number
            search = await client.get(
                "https://api.telnyx.com/v2/phone_numbers",
                headers={"Authorization": f"Bearer {settings.TELNYX_API_KEY}"},
                params={"filter[phone_number]": phone_number}
            )
            
            if search.status_code != 200:
                return False
            
            numbers = search.json().get("data", [])
            if not numbers:
                return False
            
            number_id = numbers[0].get("id")
            
            # Create call control app
            app = await client.post(
                "https://api.telnyx.com/v2/call_control_applications",
                headers={
                    "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "application_name": "AI Voice Assistant",
                    "webhook_event_url": webhook_url,
                    "webhook_api_version": "2"
                }
            )
            
            if app.status_code == 201:
                connection_id = app.json().get("data", {}).get("id")
                
                # Update number
                await client.patch(
                    f"https://api.telnyx.com/v2/phone_numbers/{number_id}",
                    headers={
                        "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={"connection_id": connection_id}
                )
                
                log.info(f"â Telnyx configured")
                return True
        
        return False
    except Exception as e:
        log.error(f"Telnyx error: {e}")
        return False

@router.get("/health")
async def health():
    return {"status": "ok"}
