from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests

from app.config import settings

TELNYX_API = "https://api.telnyx.com/v2"
RETELL_API = "https://api.retellai.com"

router = APIRouter(prefix="/api/v1/provision", tags=["Provisioning-Inbound"])

class InboundRequest(BaseModel):
    phone_number: str                  # E.164, e.g. +18135478530
    retell_agent_id: str               # e.g. agent_xxx
    inbound_sip_username: str          # your Telnyx credential username (for Retell to REGISTER)
    inbound_sip_password: str          # your Telnyx credential password
    webhook_url: Optional[str] = None  # optional Retell webhook
    webhook_token: Optional[str] = None

def _tx_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
        "Content-Type": "application/json",
    }

def _rt_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.RETELL_API_KEY}",
        "Content-Type": "application/json",
    }

def get_or_create_external_connection(name: str, sip_uri: str) -> Dict[str, Any]:
    # find by name
    r = requests.get(f"{TELNYX_API}/external_connections",
                     headers=_tx_headers(),
                     params={"filter[connection_name]": name},
                     timeout=30)
    r.raise_for_status()
    items = r.json().get("data", [])
    if items:
        ec_id = items[0]["id"]
        # patch to ensure sip_uri is correct
        p = requests.patch(f"{TELNYX_API}/external_connections/{ec_id}",
                           headers=_tx_headers(),
                           json={"external_sip_connection": {"sip_uri": sip_uri}},
                           timeout=30)
        p.raise_for_status()
        return p.json()["data"]

    # create
    c = requests.post(f"{TELNYX_API}/external_connections",
                      headers=_tx_headers(),
                      json={"connection_name": name,
                            "external_sip_connection": {"sip_uri": sip_uri}},
                      timeout=30)
    c.raise_for_status()
    return c.json()["data"]

def lookup_phone_number_id(e164: str) -> str:
    r = requests.get(f"{TELNYX_API}/phone_numbers",
                     headers=_tx_headers(),
                     params={"filter[phone_number]": e164},
                     timeout=30)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        raise HTTPException(status_code=404, detail=f"DID not found in Telnyx: {e164}")
    return data[0]["id"]

def assign_did_to_connection(e164: str, connection_id: str) -> Dict[str, Any]:
    pn_id = lookup_phone_number_id(e164)
    r = requests.patch(f"{TELNYX_API}/phone_numbers/{pn_id}",
                       headers=_tx_headers(),
                       json={"connection_id": connection_id},
                       timeout=30)
    r.raise_for_status()
    return r.json()["data"]

def retell_update_number(req: InboundRequest) -> Dict[str, Any]:
    payload = {
        "inbound_agent_id": req.retell_agent_id,
        "outbound_agent_id": req.retell_agent_id,
        "termination_uri": "sip.telnyx.com",
        "sip_trunk_auth_username": req.inbound_sip_username,
        "sip_trunk_auth_password": req.inbound_sip_password,
    }
    if req.webhook_url and req.webhook_token:
        payload["webhook_url"] = req.webhook_url
        payload["webhook_headers"] = {"Authorization": f"Bearer {req.webhook_token}"}

    r = requests.patch(f"{RETELL_API}/update-phone-number/{req.phone_number}",
                       headers=_rt_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

@router.post("/inbound")
def provision_inbound(req: InboundRequest):
    try:
        # 1) Ensure External Connection -> Retell
        ec = get_or_create_external_connection(
            name="retell-inbound",
            sip_uri="sip:sip.retellai.com;transport=tcp"
        )

        # 2) Point your DID to that External Connection (inbound to Retell)
        assigned = assign_did_to_connection(req.phone_number, ec["id"])

        # 3) Make sure Retell has SIP auth + agent + webhook
        retell = retell_update_number(req)

        return {
            "status": "ok",
            "external_connection": {"id": ec["id"], "name": ec["connection_name"]},
            "inbound_routing": {"did": assigned.get("phone_number"), "connection_id": ec["id"]},
            "retell_number": retell,
            "message": f"Inbound wired: {req.phone_number} → Retell agent {req.retell_agent_id}"
        }
    except requests.HTTPError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
