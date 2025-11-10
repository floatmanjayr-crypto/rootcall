from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.services.telnyx_service import TelnyxService
from app.services.retell_service import RetellService

router = APIRouter(prefix="/api/v1/provision", tags=["Provisioning-Finalize"])

tel = TelnyxService()
rtl = RetellService()

class FinalizeRequest(BaseModel):
    client_id: int
    business_name: str
    connection_id: str = Field(..., example="2700292207562195984")
    phone_number: str = Field(..., example="+18135551234")            # DID you just purchased/attached
    ovp_name: str = "runnerb-main-ovp"
    whitelist: List[str] = ["US","CA"]
    agent_prompt: str = "You are a friendly receptionist."
    agent_voice: str = "11labs-Adrian"
    force_ani: Optional[str] = None                                   # defaults to DID

@router.post("/finalize")
def finalize_provision(req: FinalizeRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    # 0) Validate user
    user = db.query(User).filter(User.id == req.client_id).first()
    if not user:
        raise HTTPException(404, "Client not found")

    did = req.phone_number

    # 1) Create OVP + whitelist + attach (safe if run once per client)
    ovp = tel.create_outbound_voice_profile(name=req.ovp_name)
    ovp_id = ovp["id"]
    tel.update_outbound_voice_profile(ovp_id, whitelisted_destinations=req.whitelist, enabled=True)
    tel.attach_ovp_to_connection(req.connection_id, ovp_id)

    # 2) Assign DID to connection (harmless if already done)
    tel.assign_number_to_connection(did, req.connection_id)

    # 3) Retell agent
    agent_name = f"{req.business_name} AI"
    agent_id = rtl.create_agent(name=agent_name, system_prompt=req.agent_prompt, voice=req.agent_voice)
    if not agent_id:
        raise HTTPException(500, "Failed to create Retell agent")

    # 4) Import number to Retell + bind inbound/outbound
    conn = tel.get_connection(req.connection_id)
    sip_user = conn.get("user_name")
    sip_pass = conn.get("password")
    if not (sip_user and sip_pass):
        raise HTTPException(500, "Missing Telnyx SIP credentials on the connection")

    rtl.import_phone_number(
        phone_number=did,
        termination_uri="sip.telnyx.com",
        sip_username=sip_user,
        sip_password=sip_pass,
        inbound_agent_id=agent_id,
        outbound_agent_id=agent_id,
    )

    # 5) Persist AI agent + link number in DB
    ai = AIAgent(
        user_id=req.client_id,
        name=agent_name,
        system_prompt=req.agent_prompt,
        greeting_message="Hello! How can I help you today?",
        voice_model=req.agent_voice,
        ai_model=f"retell:{agent_id}",
        is_active=True,
    )
    db.add(ai); db.commit(); db.refresh(ai)

    phone = db.query(PhoneNumber).filter(PhoneNumber.phone_number == did).first()
    if phone:
        phone.user_id = req.client_id
        phone.ai_agent_id = ai.id
        phone.is_active = True
    else:
        phone = PhoneNumber(user_id=req.client_id, phone_number=did, ai_agent_id=ai.id, is_active=True)
        db.add(phone)
    db.commit()

    # 6) Force caller ID to the DID (prevents CLI policy blocks)
    tel.set_connection_ani(req.connection_id, req.force_ani or did, "always")
    tel.set_connection_transport(req.connection_id, "TCP")

    return {
        "status": "ok",
        "ovp_id": ovp_id,
        "connection_id": req.connection_id,
        "phone_number": did,
        "agent_id": agent_id,
    }
