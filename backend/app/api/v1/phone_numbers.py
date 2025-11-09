from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.deps import get_db
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.schemas.phone_number import PhoneNumber as PhoneNumberSchema, PhoneNumberCreate
from app.core.deps import get_current_active_user
from app.services.telnyx_service import TelnyxService

router = APIRouter()

@router.get("/search")
def search_numbers(
    area_code: str = None,
    country_code: str = "US",
    limit: int = 10,
    current_user: User = Depends(get_current_active_user)
):
    """Search for available phone numbers"""
    numbers = TelnyxService.search_available_numbers(area_code, country_code, limit)
    return {"numbers": numbers}

@router.post("/", response_model=PhoneNumberSchema)
def purchase_number(
    phone_in: PhoneNumberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Purchase a phone number"""
    # Search for a number if not provided
    if not hasattr(phone_in, 'phone_number'):
        available = TelnyxService.search_available_numbers(
            area_code=phone_in.area_code,
            country_code=phone_in.country_code,
            limit=1
        )
        if not available:
            raise HTTPException(status_code=404, detail="No numbers available")
        phone_number_str = available[0].get("phone_number")
    else:
        phone_number_str = phone_in.phone_number
    
    # Purchase from Telnyx
    result = TelnyxService.purchase_phone_number(phone_number_str)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to purchase number")
    
    # Save to database
    phone_number = PhoneNumber(
        user_id=current_user.id,
        phone_number=phone_number_str,
        friendly_name=phone_in.friendly_name,
        country_code=phone_in.country_code,
        telnyx_phone_number_id=result.get("id")
    )
    db.add(phone_number)
    db.commit()
    db.refresh(phone_number)
    return phone_number

@router.get("/", response_model=List[PhoneNumberSchema])
def list_numbers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List user's phone numbers"""
    return db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.is_active == True
    ).all()

@router.delete("/{phone_id}")
def release_number(
    phone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Release a phone number"""
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    # Release from Telnyx
    TelnyxService.release_phone_number(phone.telnyx_phone_number_id)
    
    # Update database
    phone.is_active = False
    db.commit()
    return {"message": "Phone number released"}
