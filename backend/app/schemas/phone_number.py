from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PhoneNumberBase(BaseModel):
    phone_number: str
    friendly_name: Optional[str] = None
    country_code: str = "US"


class PhoneNumberCreate(BaseModel):
    area_code: Optional[str] = None
    country_code: str = "US"
    friendly_name: Optional[str] = None


class PhoneNumberUpdate(BaseModel):
    friendly_name: Optional[str] = None


class PhoneNumberInDB(PhoneNumberBase):
    id: int
    user_id: int
    is_active: bool
    monthly_cost: float
    purchased_at: datetime
    
    class Config:
        from_attributes = True


class PhoneNumber(PhoneNumberInDB):
    pass
