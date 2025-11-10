from fastapi import APIRouter
from pydantic import BaseModel
import telnyx
from app.config import settings

telnyx.api_key = settings.TELNYX_API_KEY
router = APIRouter(prefix="/sms", tags=["sms"])

class SendSMS(BaseModel):
    to_number: str
    message: str

class BulkSMS(BaseModel):
    numbers: list[str]
    message: str

@router.post("/send")
def send_sms(data: SendSMS):
    """Send a single SMS"""
    message = telnyx.Message.create(
        from_=settings.TELNYX_FROM_NUMBER,
        to=data.to_number,
        text=data.message,
        messaging_profile_id=settings.TELNYX_MESSAGING_PROFILE_ID,
    )
    return {"ok": True, "message_id": message.id}

@router.post("/send-bulk")
def send_bulk_sms(data: BulkSMS):
    """Send the same SMS to multiple numbers"""
    results = []
    for num in data.numbers:
        try:
            msg = telnyx.Message.create(
                from_=settings.TELNYX_FROM_NUMBER,
                to=num,
                text=data.message,
                messaging_profile_id=settings.TELNYX_MESSAGING_PROFILE_ID,
            )
            results.append({"to": num, "status": "sent", "message_id": msg.id})
        except Exception as e:
            results.append({"to": num, "status": f"failed: {str(e)}"})
    return {"ok": True, "results": results}
