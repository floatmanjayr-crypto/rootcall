from __future__ import annotations
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, time
import pytz

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/retell", tags=["retell-inbound"])

# --- Config ---
RETELL_WEBHOOK_TOKEN = os.getenv("RETELL_WEBHOOK_TOKEN")  # set a long random string
BUSINESS_TZ = os.getenv("BUSINESS_TZ", "America/New_York")

# Map inbound DIDs to a "brand" or default agent
NUMBER_TO_AGENT: Dict[str, str] = {
    # "+18135551234": "agent_cde1ba4c8efa2aba5665a77b91",  # Joes Pizza AI
}

# Optional: map specific campaigns (by DID) to agents
NUMBER_TO_CAMPAIGN: Dict[str, str] = {
    # "+18135551234": "pizza_fall_2025",
}

# Simple DNC / blocklist
DNC_NUMBERS = {
    # "+13051234567"
}

# Business hours by weekday (0=Mon ... 6=Sun)
BUSINESS_HOURS = {
    0: (time(11, 0), time(22, 0)),
    1: (time(11, 0), time(22, 0)),
    2: (time(11, 0), time(22, 0)),
    3: (time(11, 0), time(22, 0)),
    4: (time(11, 0), time(23, 0)),
    5: (time(11, 0), time(23, 0)),
    6: (time(12, 0), time(21, 0)),
}

# Optional after-hours fallback agent
AFTER_HOURS_AGENT_ID: Optional[str] = None
# Example:
# AFTER_HOURS_AGENT_ID = "agent_14bc57ee5d06776fb989e2db77"  # Support Agent


class CallInbound(BaseModel):
    from_number: str
    to_number: str


class InboundEvent(BaseModel):
    event: str = Field(..., example="call_inbound")
    call_inbound: CallInbound


def verify_bearer(authorization: str) -> None:
    if not RETELL_WEBHOOK_TOKEN:
        raise HTTPException(status_code=500, detail="Server missing RETELL_WEBHOOK_TOKEN")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1].strip()
    if token != RETELL_WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def is_business_hours(now: Optional[datetime] = None) -> bool:
    tz = pytz.timezone(BUSINESS_TZ)
    now = now.astimezone(tz) if now else datetime.now(tz)
    wd = now.weekday()
    hours = BUSINESS_HOURS.get(wd)
    if not hours:
        return False
    start, end = hours
    return start <= now.time() <= end


def pick_agent_for_call(to_number: str, from_number: str) -> Optional[str]:
    if from_number in DNC_NUMBERS:
        return None
    agent_id = NUMBER_TO_AGENT.get(to_number)
    if not is_business_hours() and AFTER_HOURS_AGENT_ID:
        agent_id = AFTER_HOURS_AGENT_ID
    return agent_id


def compute_dynamic_variables(to_number: str, from_number: str) -> Dict[str, Any]:
    campaign = NUMBER_TO_CAMPAIGN.get(to_number)
    return {
        "caller_number": from_number,
        "called_did": to_number,
        "campaign": campaign,
    }


@router.post("/inbound")
def inbound_call_webhook(payload: InboundEvent, authorization: str = Header(default="")):
    verify_bearer(authorization)
    if payload.event != "call_inbound":
        return {"ok": True}

    to_number = payload.call_inbound.to_number
    from_number = payload.call_inbound.from_number

    agent_id = pick_agent_for_call(to_number, from_number)
    if not agent_id:
        return {"call_inbound": {}}

    dynamic_vars = compute_dynamic_variables(to_number, from_number)
    return {"call_inbound": {"override_agent_id": agent_id, "dynamic_variables": dynamic_vars}}

# --- Added mapping for live inbound routing
NUMBER_TO_AGENT["+18135478530"] = "agent_cde1ba4c8efa2aba5665a77b91"
# AFTER_HOURS_AGENT_ID = "agent_14bc57ee5d06776fb989e2db77"  # optional fallback agent
