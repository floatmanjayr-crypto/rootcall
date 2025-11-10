from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.deps import get_db
from app.models.user import User
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.schemas.call import Call as CallSchema, CallCreate
from app.core.deps import get_current_active_user
from app.services.telnyx_service import TelnyxService

router = APIRouter()

@router.post("/", response_model=CallSchema)
def make_call(
    call_in: CallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Make an outbound call"""
    # Get user's phone number
    if call_in.from_number:
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == call_in.from_number,
            PhoneNumber.user_id == current_user.id,
            PhoneNumber.is_active == True
        ).first()
    else:
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.user_id == current_user.id,
            PhoneNumber.is_active == True
        ).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="No active phone number found")
    
    # Make call via Telnyx
    result = TelnyxService.make_call(
        to_number=call_in.to_number,
        from_number=phone.phone_number,
        connection_id=phone.telnyx_connection_id
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Failed to initiate call")
    
    # Save to database
    call = Call(
        user_id=current_user.id,
        phone_number_id=phone.id,
        call_control_id=result.get("call_control_id"),
        telnyx_call_id=result.get("call_session_id"),
        direction="outbound",
        from_number=phone.phone_number,
        to_number=call_in.to_number,
        status="initiated"
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call

@router.get("/", response_model=List[CallSchema])
def list_calls(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List user's calls"""
    return db.query(Call).filter(
        Call.user_id == current_user.id
    ).order_by(Call.started_at.desc()).offset(skip).limit(limit).all()

@router.get("/{call_id}", response_model=CallSchema)
def get_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get call details"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return call

@router.post("/{call_id}/hangup")
def hangup_call(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Hangup an active call"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Hangup via Telnyx
    success = TelnyxService.hangup_call(call.call_control_id)
    
    if success:
        call.status = "completed"
        call.ended_at = datetime.utcnow()
        db.commit()
    
    return {"message": "Call ended"}
