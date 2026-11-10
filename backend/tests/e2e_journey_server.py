"""Serve the real RootCall app on a throwaway SQLite database with only Stripe, Retell and Telnyx faked.

Used by journey.browser.cjs to prove register -> checkout -> setup -> automatic activation works
end to end. Run from anywhere:  python backend/tests/e2e_journey_server.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PORT = int(os.environ.get("E2E_PORT", "8770"))
BACKEND = Path(__file__).resolve().parents[1]
DB = os.environ.get("E2E_DB") or str(Path(tempfile.mkdtemp(prefix="rootcall-e2e-")) / "e2e.db")

os.environ.update({
    "DATABASE_URL": f"sqlite:///{DB}", "JWT_SECRET_KEY": "e2e-only-signing-key-0123456789",
    "OPENAI_API_KEY": "unused", "STRIPE_SECRET_KEY": "sk_test_fake", "STRIPE_ESSENTIAL_PRICE_ID": "price_fake",
    "APP_BASE_URL": "https://rootcall.example", "RETELL_API_KEY": "unused", "TELNYX_API_KEY": "unused",
    "TELNYX_SIP_USERNAME": "e2e", "TELNYX_SIP_PASSWORD": "e2e-pass", "TELNYX_OUTBOUND_VOICE_PROFILE_ID": "profile1",
})
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import stripe  # noqa: E402
import uvicorn  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import onboarding as onboarding_router  # noqa: E402
from app.services import customer_onboarding  # noqa: E402

Base.metadata.create_all(engine)
created = {}
owned = []
sessions = {}


def fake_create(**kwargs):
    session_id = f"cs_e2e_{len(sessions) + 1}"
    sessions[session_id] = kwargs["metadata"]
    return SimpleNamespace(id=session_id, url=f"http://127.0.0.1:{PORT}/__fake_stripe?session_id={session_id}")


def fake_retrieve(session_id, **kwargs):
    suffix = session_id.rsplit("_", 1)[1]
    return {"id": session_id, "status": "complete", "payment_status": "paid", "mode": "subscription",
            "customer": f"cus_e2e_{suffix}", "subscription": f"sub_e2e_{suffix}", "metadata": sessions[session_id]}


def fake_subscription(subscription_id, **kwargs):
    suffix = subscription_id.rsplit("_", 1)[1]
    return {"id": subscription_id, "customer": f"cus_e2e_{suffix}", "status": "active",
            "current_period_end": int(time.time()) + 86400 * 30}


@app.get("/__fake_stripe", include_in_schema=False)
def fake_stripe_page():
    return HTMLResponse("<h1>Fake Stripe Checkout</h1>")


telnyx = MagicMock()
telnyx.search_available_numbers.side_effect = lambda **kwargs: [
    {"phone_number": f"+12025550{100 + len(owned)}", "locality": "Washington"}]
telnyx.list_phone_numbers.side_effect = lambda **kwargs: list(owned)
telnyx.order_number.side_effect = lambda number: (
    owned.append({"id": f"num_{number}", "phone_number": number, "connection_id": None}), {"data": {"id": "order1"}})[1]
telnyx.get_or_create_retell_trunk.return_value = ({"id": "conn1"}, "user", "password")
retell = MagicMock()
retell.list_voices.return_value = [
    {"voice_id": "v1", "voice_name": "Avery", "provider": "elevenlabs", "accent": "American", "gender": "female"}]
retell.create_llm.return_value = "llm1"
retell.create_agent.return_value = "agent1"
retell.list_phone_numbers.return_value = []
retell.get_phone_number.side_effect = lambda number: {
    "phone_number": number, "inbound_agents": [{"agent_id": "agent1", "weight": 1}],
    "sip_outbound_trunk_config": {"auth_username": "user_1"}}
retell.create_trusted_transfer_flow.return_value = "flow1"
retell.create_trusted_transfer_agent.return_value = "agent2"

with patch.object(customer_onboarding, "TelnyxService", return_value=telnyx), \
     patch.object(onboarding_router, "TelnyxService", return_value=telnyx), \
     patch.object(customer_onboarding, "RetellService", return_value=retell), \
     patch.object(stripe.checkout.Session, "create", side_effect=fake_create), \
     patch.object(stripe.checkout.Session, "retrieve", side_effect=fake_retrieve), \
     patch.object(stripe.Subscription, "retrieve", side_effect=fake_subscription):
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
