import csv
import io
import json
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from retell.lib.webhook_auth import symmetric
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Call, PhoneNumber, User
from app.models.rootcall_call_log import RootCallCallLog
from app.models.rootcall_config import RootCallConfig, TrustedContact
from app.routers import retell, rootcall_portal
from app.services import client_config


class CustomerActivityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([
            User(id=1, email="owner@example.com", hashed_password="unused"),
            User(id=2, email="other@example.com", hashed_password="unused"),
            PhoneNumber(id=1, user_id=1, phone_number="+12025550100"),
            PhoneNumber(id=2, user_id=2, phone_number="+12025550200"),
        ])
        self.config = RootCallConfig(
            user_id=1, phone_number_id=1, client_name="Owner", client_cell="+12025550102",
            retell_agent_id="screen-agent", retell_did="+12025550100",
            trusted_agent_id="trusted-agent", trusted_contacts=["+12025550101"],
        )
        self.db.add(self.config)
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(rootcall_portal.router)
        self.app.include_router(retell.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[rootcall_portal.get_current_user] = lambda: self.db.get(User, 1)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def event(self, event="call_started", **fields):
        body = json.dumps({"event": event, "call": {
            "call_id": "retell-test", "from_number": "+12025550101",
            "to_number": "+12025550100", "direction": "inbound",
            "agent_id": "screen-agent", **fields,
        }})
        with patch.object(retell.settings, "RETELL_API_KEY", "test-key"):
            return self.client.post("/retell/webhook", content=body, headers={
                "x-retell-signature": symmetric["sign"](body, "test-key"),
                "Content-Type": "application/json",
            })

    def stats(self):
        response = self.client.get("/api/rootcall/stats/1")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_retell_events_appear_once_in_history_totals_and_export(self):
        for event in ("call_started", "call_started", "call_ended", "call_analyzed"):
            self.assertEqual(self.event(event).status_code, 200)
        rows = self.client.get("/api/rootcall/calls/1").json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "screened")
        self.assertEqual(rows[0]["status"], "completed")
        self.assertTrue(rows[0]["timestamp"].endswith("+00:00"))
        self.assertEqual(self.stats()["total_calls"], 1)
        self.assertEqual(self.stats()["calls_screened"], 1)
        response = self.client.get("/api/rootcall/export/1")
        self.assertEqual(response.status_code, 200)
        exported = list(csv.reader(io.StringIO(response.text)))
        self.assertEqual(len(exported), 2)
        self.assertEqual(exported[1][1:], ["'+12025550101", "Unknown", "screened", "completed"])

    def test_trusted_attempt_is_not_reported_as_confirmed_transfer(self):
        self.event(agent_id="trusted-agent")
        self.assertEqual(self.stats()["trusted_calls"], 1)
        self.assertEqual(self.stats()["trusted_forwarded"], 0)
        self.assertEqual(self.stats()["calls_screened"], 0)
        self.event("call_ended", agent_id="trusted-agent", call_status="error")
        self.event("call_analyzed", agent_id="trusted-agent")
        self.assertEqual(self.client.get("/api/rootcall/calls/1").json()[0]["status"], "failed")
        self.assertEqual(self.stats()["trusted_forwarded"], 0)

    def test_only_confirmed_trusted_transfer_counts_as_forwarded(self):
        self.event("call_ended", agent_id="trusted-agent", disconnection_reason="call_transfer")
        self.event("call_analyzed", agent_id="trusted-agent")
        self.event(agent_id="trusted-agent")
        self.assertEqual(self.stats()["trusted_forwarded"], 1)
        self.assertEqual(self.stats()["trusted_calls"], 1)
        self.assertEqual(self.stats()["calls_screened"], 0)
        self.assertEqual(self.client.get("/api/rootcall/calls/1").json()[0]["status"], "transferred")

    def test_spoofed_routing_metadata_does_not_mark_screening_agent_as_trusted(self):
        self.event(metadata={"rootcall_routing": "trusted_bypass"})
        self.assertEqual(self.stats()["trusted_calls"], 0)
        self.assertEqual(self.stats()["calls_screened"], 1)

    def test_legacy_and_retell_deduplicate_only_exact_ids_for_the_owned_line(self):
        self.event()
        self.db.add_all([
            RootCallCallLog(phone_number_id=1, from_number="+12025550101",
                            action="screened", status="screening", call_control_id="retell-test"),
            RootCallCallLog(phone_number_id=1, from_number="+12025550101",
                            action="spam_blocked", status="blocked", call_control_id="another-call"),
            RootCallCallLog(phone_number_id=2, from_number="+12025550201",
                            action="spam_blocked", status="blocked", call_control_id="retell-test"),
            Call(user_id=2, phone_number_id=2, from_number="+12025550202",
                 call_control_id="other-call", status="completed"),
        ])
        self.db.commit()
        self.assertEqual(self.stats()["total_calls"], 2)
        self.assertEqual(self.stats()["spam_blocked"], 1)
        rows = self.client.get("/api/rootcall/calls/1").json()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["from_number"] == "+12025550101" for row in rows))
        for endpoint in ("calls", "stats", "export"):
            self.assertEqual(self.client.get(f"/api/rootcall/{endpoint}/2").status_code, 403)
        self.app.dependency_overrides.pop(rootcall_portal.get_current_user)
        for endpoint in ("calls", "stats", "export"):
            self.assertEqual(self.client.get(f"/api/rootcall/{endpoint}/1").status_code, 401)

    def test_matching_telnyx_id_preserves_legacy_decision(self):
        self.db.add(Call(user_id=1, phone_number_id=1, status="completed",
                         call_control_id="control", telnyx_call_id="session"))
        self.db.add(RootCallCallLog(phone_number_id=1, from_number="+12025550101",
                                   caller_name="Legacy name", action="trusted_forwarded",
                                   status="forwarded", call_control_id="session"))
        self.db.commit()
        self.assertEqual(self.stats()["total_calls"], 1)
        self.assertEqual(self.stats()["trusted_forwarded"], 1)
        self.assertEqual(self.client.get("/api/rootcall/calls/1").json()[0]["caller_name"], "Legacy name")

    def test_scam_detection_alone_is_not_claimed_as_a_blocked_call(self):
        self.db.add(Call(user_id=1, phone_number_id=1, status="completed",
                         retell_call_id="detected", scam_detected=True))
        self.db.commit()
        self.assertEqual(self.stats()["spam_blocked"], 0)
        self.assertEqual(self.stats()["calls_screened"], 1)

    def test_empty_provider_identifiers_do_not_merge_unrelated_calls(self):
        self.db.add(Call(user_id=1, phone_number_id=1, status="completed", call_control_id=""))
        self.db.add(RootCallCallLog(phone_number_id=1, from_number="+12025550101",
                                   action="screened", status="completed", call_control_id=""))
        self.db.commit()
        self.assertEqual(self.stats()["total_calls"], 2)

    def test_no_numbers_and_no_history_have_zero_stats(self):
        self.assertEqual(self.client.get("/api/rootcall/calls/1").json(), [])
        self.assertEqual(self.stats()["total_calls"], 0)
        self.app.dependency_overrides[rootcall_portal.get_current_user] = lambda: self.db.get(User, 2)
        self.db.delete(self.db.get(PhoneNumber, 2))
        self.db.commit()
        self.assertEqual(self.client.get("/api/rootcall/stats/2").json()["total_calls"], 0)

    def test_recent_history_is_bounded_and_export_contains_all_calls(self):
        start = datetime(2026, 1, 1)
        for index in range(25):
            self.db.add(Call(user_id=1, phone_number_id=1, status="completed",
                             direction="outbound", started_at=start + timedelta(minutes=index),
                             from_number="+12025550100", caller_name="=HYPERLINK(\"bad\")"))
        self.db.commit()
        rows = self.client.get("/api/rootcall/calls/1").json()
        self.assertEqual(len(rows), 20)
        self.assertGreater(rows[0]["timestamp"], rows[-1]["timestamp"])
        self.assertEqual(self.stats()["calls_screened"], 0)
        self.assertEqual(self.stats()["total_calls"], 25)
        exported = list(csv.reader(io.StringIO(self.client.get("/api/rootcall/export/1").text)))
        self.assertEqual(len(exported), 26)
        self.assertEqual(exported[1][2], "'=HYPERLINK(\"bad\")")

    def test_contact_names_persist_without_changing_routing_list_shape(self):
        response = self.client.post("/api/rootcall/trusted-contacts/1", json={
            "phone_number": "(202) 555-0101", "name": "  Family  ",
        })
        self.assertEqual(response.status_code, 200)
        self.db.expire_all()
        self.assertEqual(self.config.trusted_contacts, ["+12025550101"])
        contacts = self.client.get("/api/rootcall/config/1").json()["trusted_contacts"]
        self.assertEqual(contacts, [{"phone_number": "+12025550101", "name": "Family"}])
        self.assertTrue(client_config.is_trusted_contact("+12025550100", "+12025550101", self.db))
        self.client.post("/api/rootcall/trusted-contacts/1", json={
            "phone_number": "+12025550101", "name": "Mom",
        })
        self.assertEqual(self.db.query(TrustedContact).count(), 1)
        self.assertEqual(self.client.get("/api/rootcall/config/1").json()["trusted_contacts"][0]["name"], "Mom")
        self.client.post("/api/rootcall/trusted-contacts/1", json={"phone_number": "+12025550101"})
        self.assertEqual(self.client.get("/api/rootcall/config/1").json()["trusted_contacts"][0]["name"], "Mom")
        self.assertEqual(self.client.delete("/api/rootcall/trusted-contacts/1/+12025550101").status_code, 200)
        self.assertEqual(self.db.query(TrustedContact).count(), 0)
        self.db.expire_all()
        self.assertEqual(self.config.trusted_contacts, [])

    def test_contact_limits_and_ownership(self):
        self.assertEqual(self.client.post("/api/rootcall/trusted-contacts/2", json={
            "phone_number": "+12025550101", "name": "Other",
        }).status_code, 403)
        self.assertEqual(self.client.post("/api/rootcall/trusted-contacts/1", json={
            "phone_number": "+12025550101", "name": "x" * 101,
        }).status_code, 422)
        self.config.trusted_contacts = [f"+1202555{index:04d}" for index in range(100)]
        self.db.commit()
        self.assertEqual(self.client.post("/api/rootcall/trusted-contacts/1", json={
            "phone_number": "+12025550999",
        }).status_code, 422)
        self.assertEqual(self.client.post("/api/rootcall/trusted-contacts/1", json={
            "phone_number": "+12025550000", "name": "Updated at capacity",
        }).status_code, 200)

    def test_shared_removal_cleans_up_contact_name(self):
        self.client.post("/api/rootcall/trusted-contacts/1", json={
            "phone_number": "+12025550101", "name": "Family",
        })
        self.assertTrue(client_config.remove_trusted_contact("+12025550100", "+12025550101", self.db))
        self.assertEqual(self.db.query(TrustedContact).count(), 0)

    def test_configured_status_is_not_a_live_provider_health_claim(self):
        self.assertTrue(self.client.get("/api/rootcall/config/1").json()["line_configured"])
        self.config.client_cell = "+12025550100"
        self.db.commit()
        self.assertFalse(self.client.get("/api/rootcall/config/1").json()["line_configured"])
        self.config.client_cell = "+12025550102"
        self.config.is_active = False
        self.db.commit()
        self.assertFalse(self.client.get("/api/rootcall/config/1").json()["line_configured"])
