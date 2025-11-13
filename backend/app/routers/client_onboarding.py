# app/routers/onboarding.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent

# NEW services (from our earlier messages)
from app.services.retell_service import RetellService
from app.services.telnyx_service import TelnyxService

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])
log = logging.getLogger(__name__)


# ------------------------ Requests / Responses ------------------------

class OnboardClientRequest(BaseModel):
    client_id: int
    business_name: str
    # If agent_id is omitted, we create a new agent with the prompt/voice below
    agent_id: Optional[str] = None

    # Used when creating a *new* agent
    system_prompt: Optional[str] = None
    greeting: Optional[str] = "Hi! How can I help you today?"
    voice: Optional[str] = "11labs-Adrian"
    publish_agent: bool = True

    # Number options: purchase new OR use existing
    purchase_number: bool = True
    area_code: Optional[str] = Field(None, example="813")
    phone_number: Optional[str] = None  # for using an existing number in your Telnyx account

    # SIP trunk credentials for Retell import
    # Required when importing the number to Retell (existing or purchased)
    telnyx_connection_name: str = Field(..., example="runnerb-main-trunk")
    telnyx_sip_username: str = Field(..., example="runnerb813")
    telnyx_sip_password: str = Field(..., example="STRONG-PASSWORD-813")
    telnyx_termination_uri: str = "sip.telnyx.com"

    # Optional: start a few test calls after go-live
    leads: Optional[List[str]] = None

    # Pricing
    rate_per_minute: Optional[float] = 0.35


class OnboardResponse(BaseModel):
    status: str
    business_name: str
    agent_id: str
    llm_id: Optional[str] = None
    phone_number: str
    telnyx_connection_id: Optional[str] = None
    retell_import: Optional[dict] = None
    pricing: dict
    bulk: Optional[List[dict]] = None
    message: str


class EditAgentPromptRequest(BaseModel):
    agent_id: str
    general_prompt: Optional[str] = None
    begin_message: Optional[str] = None
    start_speaker: Optional[str] = None  # "agent" or "user"


class RebindNumberRequest(BaseModel):
    agent_id: str
    outbound_also: bool = True


# ------------------------ Onboarding: one-shot ------------------------

@router.post("/start", response_model=OnboardResponse)
def onboard_client(req: OnboardClientRequest, db: Session = Depends(get_db)):
    """
    Full onboarding:
      1) Verify client
      2) Create/publish Retell Agent (or reuse existing)
      3) Purchase Telnyx number (or use existing)
      4) Import number into Retell + bind inbound/outbound to the agent
      5) Persist to DB
      6) (Optional) start a few test calls via Retell
    """
    try:
        # 1) Verify client
        client = db.query(User).filter(User.id == req.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        telnyx = TelnyxService()
        retell = RetellService()

        # 2) Agent
        agent_id = req.agent_id
        llm_id = None
        if not agent_id:
            if not req.system_prompt:
                raise HTTPException(status_code=400, detail="system_prompt required when creating a new agent")

            # Create LLM + Agent + optional publish
            llm_id = retell.create_llm(
                general_prompt=req.system_prompt,
                begin_message=req.greeting or "Hi! How can I help you today?",
                start_speaker="agent",
            )
            agent_name = f"{req.business_name} AI"
            agent_id = retell.create_agent(
                name=agent_name,
                llm_id=llm_id,
                voice_id=req.voice or "11labs-Adrian",
                publish=req.publish_agent,
            )

        # 3) Telnyx: purchase OR use existing
        telnyx_number = req.phone_number
        telnyx_connection_id = None

        if req.purchase_number:
            prov = telnyx.provision_number_with_credentials(
                desired_area_code=req.area_code,
                connection_name=req.telnyx_connection_name,
                sip_username=req.telnyx_sip_username,
                sip_password=req.telnyx_sip_password,
                webhook_url=None,  # optional: your Telnyx Call Control webhook if you still use it
            )
            telnyx_number = prov["phone_number"]
            telnyx_connection_id = prov["connection"]["id"]
        else:
            # using existing number from your Telnyx account
            if not telnyx_number:
                raise HTTPException(status_code=400, detail="phone_number required when purchase_number=false")

            # ensure it exists, then attach to the named connection
            con, usern, _pass = telnyx.get_or_create_credential_connection(
                connection_name=req.telnyx_connection_name,
                sip_username=req.telnyx_sip_username,
                sip_password=req.telnyx_sip_password,
            )
            telnyx.assign_number_to_connection(telnyx_number, con["id"])
            telnyx_connection_id = con["id"]

        # 4) Import number into Retell and bind inbound/outbound to the agent
        retell_import = retell.import_phone_number(
            phone_number=telnyx_number,
            termination_uri=req.telnyx_termination_uri,
            sip_username=req.telnyx_sip_username,
            sip_password=req.telnyx_sip_password,
            inbound_agent_id=agent_id,
            outbound_agent_id=agent_id,
        )

        # 5) Persist to DB: AIAgent + PhoneNumber
        #    (links your logical agent record to Retell agent id and number)
        ai_agent = AIAgent(
            user_id=req.client_id,
            name=f"{req.business_name} AI",
            system_prompt=req.system_prompt or "",
            greeting_message=req.greeting or "",
            voice_model=req.voice or "11labs-Adrian",
            ai_model=f"retell:{agent_id}",
            is_active=True,
        )
        db.add(ai_agent)
        db.commit()
        db.refresh(ai_agent)

        phone = db.query(PhoneNumber).filter(PhoneNumber.phone_number == telnyx_number).first()
        if phone:
            phone.ai_agent_id = ai_agent.id
            phone.user_id = req.client_id
            phone.is_active = True
        else:
            phone = PhoneNumber(
                user_id=req.client_id,
                phone_number=telnyx_number,
                ai_agent_id=ai_agent.id,
                is_active=True,
            )
            db.add(phone)
        db.commit()

        # 6) Optional: a couple of test calls
        bulk = None
        if req.leads:
            bulk = retell.bulk_create_phone_calls(
                from_number=telnyx_number,
                to_numbers=req.leads,
                override_agent_id=agent_id,
            )

        # Pricing: your internal cost vs. sell rate
        cost_per_min = 0.13
        profit_per_min = (req.rate_per_minute or 0.35) - cost_per_min

        return OnboardResponse(
            status="live",
            business_name=req.business_name,
            agent_id=agent_id,
            llm_id=llm_id,
            phone_number=telnyx_number,
            telnyx_connection_id=telnyx_connection_id,
            retell_import=retell_import,
            pricing={
                "cost_per_min": cost_per_min,
                "rate_per_min": req.rate_per_minute or 0.35,
                "profit_per_min": profit_per_min,
            },
            bulk=bulk,
            message=f"{req.business_name} is live with inbound + outbound AI.",
        )

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Onboarding failed")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------ Edit Agent Prompt ------------------------

@router.patch("/agents/prompt")
def edit_agent_prompt(req: EditAgentPromptRequest):
    """
    Resolve the agent's llm_id and patch the LLM with updated prompt/greeting.
    """
    try:
        retell = RetellService()

        # Find the agent in Retell to get llm_id
        agents = retell.list_agents()
        agent = next((a for a in agents if a.get("agent_id") == req.agent_id), None)
        if not agent:
            raise HTTPException(status_code=404, detail="agent_id not found")

        resp_engine = agent.get("response_engine") or {}
        llm_id = resp_engine.get("llm_id")
        if not llm_id:
            raise HTTPException(status_code=400, detail="Agent is not backed by a Retell LLM")

        updated = retell.update_llm(
            llm_id=llm_id,
            general_prompt=req.general_prompt,
            begin_message=req.begin_message,
            start_speaker=req.start_speaker,
        )
        return {"ok": True, "llm_id": llm_id, "updated": updated}
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Edit prompt failed")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------ Rebind Number -> Agent ------------------------

@router.patch("/numbers/{phone_number}/agent")
def rebind_number_agent(phone_number: str, req: RebindNumberRequest):
    """
    Bind a phone number in Retell to a different agent (inbound + optional outbound).
    """
    try:
        retell = RetellService()
        patch = retell.update_phone_number(
            phone_number=phone_number,
            inbound_agent_id=req.agent_id,
            outbound_agent_id=req.agent_id if req.outbound_also else None,
        )
        return {"ok": True, "phone_number": phone_number, "agent_id": req.agent_id, "retell_update": patch}
    except Exception as e:
        logging.exception("Rebind failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health():
    return {"status": "ok"}

