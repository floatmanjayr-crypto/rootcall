"""
Outbound Calling Router - Telnyx + Retell Integration
Handles programmatic outbound calls for clients
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
from datetime import datetime

from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.models.user import User
from app.services.retell_service import retell_service
from app.config import settings

router = APIRouter(prefix="/api/v1/outbound", tags=["Outbound Calls"])
log = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class OutboundCallRequest(BaseModel):
    """Request to make an outbound call"""
    from_number: str = Field(..., description="Client's phone number (E.164 format)")
    to_number: str = Field(..., description="Destination number (E.164 format)")
    agent_id: Optional[str] = Field(None, description="Retell agent ID (optional, uses number's default)")
    user_id: int = Field(..., description="User ID making the call")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")


class BulkOutboundCallRequest(BaseModel):
    """Request to make multiple outbound calls"""
    from_number: str = Field(..., description="Client's phone number")
    to_numbers: List[str] = Field(..., description="List of destination numbers")
    agent_id: Optional[str] = Field(None, description="Retell agent ID")
    user_id: int = Field(..., description="User ID")
    delay_between_calls: int = Field(default=5, description="Seconds between calls")


class CallStatusResponse(BaseModel):
    """Response for call status"""
    call_id: str
    status: str
    direction: str
    from_number: str
    to_number: str
    started_at: Optional[datetime]
    duration: Optional[int]


# ============================================================================
# Helper Functions
# ============================================================================

def verify_user_owns_number(db: Session, user_id: int, phone_number: str) -> PhoneNumber:
    """Verify user owns the phone number"""
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == user_id,
        PhoneNumber.phone_number == phone_number,
        PhoneNumber.is_active == True
    ).first()
    
    if not phone:
        raise HTTPException(
            status_code=403, 
            detail=f"User does not own active phone number {phone_number}"
        )
    
    return phone


def create_call_record(
    db: Session,
    user_id: int,
    phone_number_id: int,
    from_number: str,
    to_number: str,
    agent_id: Optional[str] = None,
    retell_call_id: Optional[str] = None,
    telnyx_call_id: Optional[str] = None
) -> Call:
    """Create a call record in the database"""
    call = Call(
        user_id=user_id,
        phone_number_id=phone_number_id,
        direction="outbound",
        from_number=from_number,
        to_number=to_number,
        status="initiated",
        started_at=datetime.utcnow(),
        call_control_id=telnyx_call_id or retell_call_id,
        telnyx_call_id=telnyx_call_id
    )
    
    if agent_id:
        # Find the AI agent
        ai_agent = db.query(AIAgent).filter(
            AIAgent.retell_agent_id == agent_id
        ).first()
        if ai_agent:
            call.ai_agent_id = ai_agent.id
    
    db.add(call)
    db.commit()
    db.refresh(call)
    
    return call


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/call", response_model=CallStatusResponse)
async def make_outbound_call(
    request: OutboundCallRequest,
    db: Session = Depends(get_db)
):
    """
    Make an outbound call using Retell AI
    
    This endpoint:
    1. Verifies user owns the from_number
    2. Uses the number's assigned agent (or override)
    3. Initiates call via Retell API
    4. Creates call record in database
    """
    try:
        # Verify user owns the number
        phone = verify_user_owns_number(db, request.user_id, request.from_number)
        
        # Determine which agent to use
        agent_id = request.agent_id
        if not agent_id and phone.ai_agent:
            agent_id = phone.ai_agent.retell_agent_id
        
        if not agent_id:
            raise HTTPException(
                status_code=400,
                detail="No agent assigned to number and no agent_id provided"
            )
        
        log.info(
            f"Initiating outbound call: {request.from_number} -> {request.to_number} "
            f"(user={request.user_id}, agent={agent_id})"
        )
        
        # Attempt to create call via Retell
        try:
            call_response = retell_service.create_phone_call(
                from_number=request.from_number,
                to_number=request.to_number,
                override_agent_id=agent_id
            )
            
            retell_call_id = call_response.get("call_id")
            call_status = call_response.get("call_status", "initiated")
            
        except Exception as retell_error:
            error_msg = str(retell_error)
            
            # Check if it's the permission error
            if "telephony_provider_permission_denied" in error_msg or "permission" in error_msg.lower():
                log.warning(
                    f"Retell permission denied for {request.from_number}. "
                    "Number may not be properly registered with Retell for outbound calling."
                )
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Phone number {request.from_number} is not configured for outbound calling with Retell. "
                        "Please ensure the number is properly imported and bound in your Retell dashboard."
                    )
                )
            else:
                log.error(f"Retell call creation failed: {error_msg}")
                raise HTTPException(status_code=500, detail=f"Failed to create call: {error_msg}")
        
        # Create call record
        call = create_call_record(
            db=db,
            user_id=request.user_id,
            phone_number_id=phone.id,
            from_number=request.from_number,
            to_number=request.to_number,
            agent_id=agent_id,
            retell_call_id=retell_call_id
        )
        
        return CallStatusResponse(
            call_id=retell_call_id,
            status=call_status,
            direction="outbound",
            from_number=request.from_number,
            to_number=request.to_number,
            started_at=call.started_at,
            duration=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Outbound call failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-call")
async def make_bulk_outbound_calls(
    request: BulkOutboundCallRequest,
    db: Session = Depends(get_db)
):
    """Make multiple outbound calls (bulk dialing)"""
    try:
        phone = verify_user_owns_number(db, request.user_id, request.from_number)
        
        agent_id = request.agent_id
        if not agent_id and phone.ai_agent:
            agent_id = phone.ai_agent.retell_agent_id
        
        if not agent_id:
            raise HTTPException(
                status_code=400,
                detail="No agent assigned to number and no agent_id provided"
            )
        
        log.info(
            f"Starting bulk outbound campaign: {request.from_number} -> "
            f"{len(request.to_numbers)} numbers (user={request.user_id})"
        )
        
        results = []
        
        for to_number in request.to_numbers:
            try:
                call_response = retell_service.create_phone_call(
                    from_number=request.from_number,
                    to_number=to_number,
                    override_agent_id=agent_id
                )
                
                retell_call_id = call_response.get("call_id")
                
                call = create_call_record(
                    db=db,
                    user_id=request.user_id,
                    phone_number_id=phone.id,
                    from_number=request.from_number,
                    to_number=to_number,
                    agent_id=agent_id,
                    retell_call_id=retell_call_id
                )
                
                results.append({
                    "to_number": to_number,
                    "status": "success",
                    "call_id": retell_call_id
                })
                
            except Exception as e:
                log.error(f"Failed to call {to_number}: {str(e)}")
                results.append({
                    "to_number": to_number,
                    "status": "failed",
                    "error": str(e)
                })
            
            if request.delay_between_calls > 0:
                import time
                time.sleep(request.delay_between_calls)
        
        success_count = sum(1 for r in results if r["status"] == "success")
        
        return {
            "total_calls": len(request.to_numbers),
            "successful": success_count,
            "failed": len(request.to_numbers) - success_count,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Bulk outbound calls failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_id}", response_model=CallStatusResponse)
async def get_call_status(call_id: str, db: Session = Depends(get_db)):
    """Get the status of an outbound call"""
    call = db.query(Call).filter(Call.call_control_id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return CallStatusResponse(
        call_id=call.call_control_id,
        status=call.status,
        direction=call.direction,
        from_number=call.from_number,
        to_number=call.to_number,
        started_at=call.started_at,
        duration=call.duration
    )


@router.get("/numbers/{phone_number}/outbound-status")
async def check_outbound_status(
    phone_number: str,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Check if a phone number is properly configured for outbound calling"""
    phone = verify_user_owns_number(db, user_id, phone_number)
    
    has_agent = phone.ai_agent_id is not None
    agent_name = phone.ai_agent.name if phone.ai_agent else None
    retell_agent_id = phone.ai_agent.retell_agent_id if phone.ai_agent else None
    
    has_telnyx_config = bool(phone.telnyx_connection_id)
    
    return {
        "phone_number": phone_number,
        "is_active": phone.is_active,
        "has_agent_assigned": has_agent,
        "agent_name": agent_name,
        "retell_agent_id": retell_agent_id,
        "has_telnyx_config": has_telnyx_config,
        "telnyx_connection_id": phone.telnyx_connection_id,
        "ready_for_outbound": has_agent and has_telnyx_config and phone.is_active,
        "notes": (
            "Ready for outbound calling" if (has_agent and has_telnyx_config and phone.is_active)
            else "Configuration incomplete - check missing requirements above"
        )
    }
