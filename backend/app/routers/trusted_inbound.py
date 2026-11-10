import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from retell.lib.webhook_auth import verify
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig
from app.models.user import User
from app.services.trusted_routing import normalize_caller

router = APIRouter(prefix="/retell", tags=["Trusted Inbound Routing"])
log = logging.getLogger(__name__)


@router.post("/rootcall-inbound")
async def route_inbound(request: Request, db: Session = Depends(get_db)):
    if not settings.RETELL_API_KEY:
        raise HTTPException(status_code=503, detail="Retell is not configured.")
    try:
        text = (await request.body()).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid inbound payload.")
    if not verify(text, settings.RETELL_API_KEY, request.headers.get("x-retell-signature", "")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")
    try:
        data = json.loads(text)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid inbound payload.")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid inbound payload.")
    if data.get("event") != "call_inbound":
        raise HTTPException(status_code=422, detail="Only inbound phone calls are supported.")
    call = data.get("call_inbound")
    if (not isinstance(call, dict) or not isinstance(call.get("to_number"), str)
            or not isinstance(call.get("from_number"), str)):
        raise HTTPException(status_code=422, detail="Missing inbound phone numbers.")
    number = normalize_caller(call["to_number"])
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == number, PhoneNumber.is_active.is_(True),
    ).first() if number else None
    config = db.query(RootCallConfig).filter(
        RootCallConfig.phone_number_id == phone.id, RootCallConfig.user_id == phone.user_id,
        RootCallConfig.is_active.is_(True),
    ).first() if phone else None
    owner = db.get(User, phone.user_id) if phone else None
    if not config or not owner or not owner.is_active:
        log.warning("Rejected inbound call for an unconfigured or inactive Shield line")
        return {"call_inbound": {"reject": True}}
    caller = normalize_caller(call["from_number"])
    trusted = caller is not None and caller in {
        normalize_caller(value) for value in (config.trusted_contacts or []) if isinstance(value, str)
    }
    if not trusted or not config.trusted_routing_enabled:
        return {"call_inbound": {"override_agent_id": config.retell_agent_id}}
    forwarding = normalize_caller(config.client_cell)
    if not config.trusted_agent_id or not forwarding or forwarding == number:
        log.error("Trusted routing is enabled but incomplete for config %s", config.id)
        return {"call_inbound": {"reject": True}}
    return {"call_inbound": {
        "override_agent_id": config.trusted_agent_id,
        "dynamic_variables": {
            "rootcall_forwarding": forwarding,
        },
        "metadata": {"rootcall_routing": "trusted_bypass"},
    }}
