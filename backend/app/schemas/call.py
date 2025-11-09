from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CallBase(BaseModel):
    from_number: str
    to_number: str
    direction: str


class CallCreate(BaseModel):
    to_number: str
    from_number: Optional[str] = None


class CallUpdate(BaseModel):
    status: Optional[str] = None


class CallInDB(CallBase):
    id: int
    user_id: int
    phone_number_id: int
    status: str
    duration: int
    cost: float
    transcription: Optional[str] = None
    summary: Optional[str] = None
    started_at: datetime
    
    class Config:
        from_attributes = True


class Call(CallInDB):
    pass
