import re
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.rootcall_config import RootCallConfig
from app.services.retell_service import RetellService
from app.services.activation_recovery import resource_creation


def normalize_caller(value: str) -> str | None:
    value = re.sub(r"[\s().-]", "", value)
    if re.fullmatch(r"\d{10}", value):
        value = "+1" + value
    elif re.fullmatch(r"1\d{10}", value):
        value = "+" + value
    return value if re.fullmatch(r"\+[1-9]\d{1,14}", value) else None


def enable_trusted_routing(db: Session, config: RootCallConfig, number: str, service=None, onboarding=None):
    base = settings.APP_BASE_URL.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail="Trusted call routing requires public HTTPS configuration.")
    if not config.is_active or not normalize_caller(config.client_cell) or config.client_cell == number:
        raise HTTPException(status_code=422, detail="Save a valid forwarding number before enabling trusted routing.")
    retell = service or RetellService()
    imported = retell.get_phone_number(number)
    if imported.get("phone_number") != number:
        raise HTTPException(status_code=409, detail="Imported number does not match your Shield line.")
    bindings = imported.get("inbound_agents") or []
    if len(bindings) != 1 or bindings[0].get("agent_id") != config.retell_agent_id:
        raise HTTPException(status_code=409, detail="Number agent bindings need review before enabling trusted routing.")
    webhook_url = f"{base}/retell/rootcall-inbound"
    if imported.get("inbound_webhook_url") not in (None, "", webhook_url):
        raise HTTPException(status_code=409, detail="This number already has an inbound webhook. Contact support before replacing it.")
    config = db.query(RootCallConfig).filter(
        RootCallConfig.id == config.id,
    ).populate_existing().with_for_update().one()
    if not config.trusted_flow_id:
        with resource_creation(db, onboarding, "trusted_flow"):
            config.trusted_flow_id = retell.create_trusted_transfer_flow(
                (imported.get("sip_outbound_trunk_config") or {}).get("auth_username"),
            )
            if not config.trusted_flow_id:
                raise RuntimeError("Retell did not return a trusted flow ID")
        db.commit()
        config = db.query(RootCallConfig).filter(
            RootCallConfig.id == config.id,
        ).populate_existing().with_for_update().one()
    if not config.trusted_agent_id:
        with resource_creation(db, onboarding, "trusted_agent"):
            config.trusted_agent_id = retell.create_trusted_transfer_agent(
                f"RootCall-Trusted-{config.user_id}-{config.id}", config.trusted_flow_id,
                config.retell_agent_id, f"{base}/retell/webhook",
            )
            if not config.trusted_agent_id:
                raise RuntimeError("Retell did not return a trusted agent ID")
        db.commit()
        config = db.query(RootCallConfig).filter(
            RootCallConfig.id == config.id,
        ).populate_existing().with_for_update().one()
    retell.publish_agent(config.trusted_agent_id)
    retell.configure_inbound_webhook(number, webhook_url)
    config.trusted_routing_enabled = True
    db.commit()
