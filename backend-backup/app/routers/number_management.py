# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.phone_number import PhoneNumber
from app.models.badbot_config import BadBotConfig
from pydantic import BaseModel
import telnyx
import os

router = APIRouter(tags=["Numbers"])

telnyx.api_key = os.getenv("TELNYX_API_KEY")

class SearchNumbers(BaseModel):
    area_code: str
    limit: int = 10

class PurchaseNumber(BaseModel):
    phone_number: str
    user_id: int
    nickname: str

@router.post("/api/numbers/search")
async def search_numbers(data: SearchNumbers):
    try:
        available = telnyx.AvailablePhoneNumber.list(
            filter={
                "country_code": "US",
                "national_destination_code": data.area_code,
                "features": ["sms", "voice"],
                "limit": data.limit
            }
        )
        
        return {
            "numbers": [
                {
                    "phone_number": num.phone_number,
                    "region": num.region_information[0].region_name if num.region_information else "Unknown",
                    "cost": "1.00"
                }
                for num in available.data
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/numbers/purchase")
async def purchase_number(data: PurchaseNumber, db: Session = Depends(get_db)):
    try:
        order = telnyx.NumberOrder.create(
            phone_numbers=[{"phone_number": data.phone_number}],
            connection_id=os.getenv("TELNYX_CONNECTION_ID")
        )
        
        phone = PhoneNumber(
            user_id=data.user_id,
            phone_number=data.phone_number,
            friendly_name=data.nickname,
            telnyx_connection_id=os.getenv("TELNYX_CONNECTION_ID"),
            is_active=True
        )
        db.add(phone)
        db.flush()
        
        config = BadBotConfig(
            phone_number_id=phone.id,
            user_id=data.user_id,
            client_name=data.nickname,
            sms_alerts_enabled=True,
            alert_on_spam=True,
            auto_block_spam=True,
            is_active=True
        )
        db.add(config)
        db.commit()
        
        return {"success": True, "phone_number": data.phone_number}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/numbers/my-numbers/{user_id}")
async def get_my_numbers(user_id: int, db: Session = Depends(get_db)):
    phones = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == user_id,
        PhoneNumber.is_active == True
    ).all()
    
    result = []
    for phone in phones:
        config = db.query(BadBotConfig).filter(
            BadBotConfig.phone_number_id == phone.id
        ).first()
        
        result.append({
            "id": phone.id,
            "phone_number": phone.phone_number,
            "nickname": phone.friendly_name,
            "active": phone.is_active
        })
    
    return {"numbers": result}
