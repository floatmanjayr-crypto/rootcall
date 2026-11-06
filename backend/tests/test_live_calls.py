import json
import os
import unittest
from unittest.mock import AsyncMock, patch

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
from app.routers import retell, live_calls
from app.core.deps import get_current_active_user


class LiveCallsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(User(id=1, email="owner@example.com", hashed_password="unused"))
        self.db.add(PhoneNumber(id=1, user_id=1, phone_number="+12025550100"))
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(retell.router)
        self.app.include_router(live_calls.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_active_user] = lambda: self.db.get(User, 1)
        self.client = TestClient(self.app)
        self.key_patch = patch.object(retell.settings, "RETELL_API_KEY", "test-key")
        self.key_patch.start()

    def tearDown(self):
        self.key_patch.stop()
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def event(self, event="call_started", **fields):
        body = json.dumps({"event": event, "call": {
            "call_id": "call_test", "from_number": "+12025550101",
            "to_number": "+12025550100", "direction": "inbound", **fields
        }})
        return self.client.post("/retell/webhook", content=body, headers={
            "x-retell-signature": symmetric["sign"](body, "test-key"),
            "Content-Type": "application/json",
        })

    def test_requires_valid_signature(self):
        response = self.client.post("/retell/webhook", json={"event": "call_started"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.query(Call).count(), 0)

    def test_start_is_owned_and_idempotent(self):
        self.assertEqual(self.event().status_code, 200)
        self.assertEqual(self.event().status_code, 200)
        call = self.db.query(Call).one()
        self.assertEqual((call.user_id, call.phone_number_id), (1, 1))
        self.assertEqual(call.retell_call_id, "call_test")

    def test_live_transcript_and_end(self):
        self.event("transcript_updated", transcript="Agent: Who is calling?\nUser: Sam.")
        call = self.db.query(Call).one()
        self.assertIn("Agent: Who is calling?", call.transcription)
        self.event("call_ended", transcript="Final transcript", duration_ms=42000)
        self.assertEqual(call.status, "completed")
        self.assertEqual(call.duration, 42)
        self.event("transcript_updated", transcript="Stale transcript")
        self.event()
        self.assertEqual(call.status, "completed")
        self.assertEqual(call.transcription, "Final transcript")

    def test_unknown_phone_is_ignored(self):
        self.assertEqual(self.event(to_number="+12025550999").json()["status"], "ignored")
        self.assertEqual(self.db.query(Call).count(), 0)

    def test_analysis_uses_nested_fields(self):
        self.event("call_analyzed", call_analysis={
            "call_summary": "Appointment reminder", "user_sentiment": "Positive"
        })
        call = self.db.query(Call).one()
        self.assertEqual(call.summary, "Appointment reminder")
        self.assertEqual(call.sentiment, "Positive")
        self.assertIsNotNone(call.ended_at)

    def test_feed_and_controls_require_auth(self):
        self.app.dependency_overrides.pop(get_current_active_user)
        self.assertEqual(self.client.get("/api/rootcall/live-calls").status_code, 401)
        self.assertEqual(self.client.post("/api/rootcall/live-calls/1/listen").status_code, 401)

    def test_other_user_cannot_view_or_control_call(self):
        self.event()
        self.db.add(User(id=2, email="other@example.com", hashed_password="unused"))
        self.db.commit()
        self.app.dependency_overrides[get_current_active_user] = lambda: self.db.get(User, 2)
        self.assertEqual(self.client.get("/api/rootcall/live-calls").json(), [])
        for action in ("listen", "end", "takeover"):
            response = self.client.post(f"/api/rootcall/live-calls/1/{action}", json={"participant_id": "listener"})
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/api/rootcall/live-calls/1/transcript").status_code, 404)

    def test_takeover_calls_provider_once(self):
        self.event()
        with patch.object(live_calls, "provider_action", new_callable=AsyncMock) as action:
            action.return_value = {"success": True}
            response = self.client.post("/api/rootcall/live-calls/1/takeover", json={"participant_id": "listener"})
            self.assertEqual(response.status_code, 200)
            action.assert_awaited_once_with("call_test", "take-over-live-call", {"participant_id": "listener"})
            self.assertEqual(self.client.post("/api/rootcall/live-calls/1/takeover", json={"participant_id": "listener"}).status_code, 409)
        self.db.expire_all()
        self.assertEqual(self.db.query(Call).one().status, "human-connected")

    def test_takeover_failure_does_not_claim_success(self):
        self.event()
        with patch.object(live_calls, "provider_action", new_callable=AsyncMock) as action:
            action.return_value = {"success": False}
            response = self.client.post("/api/rootcall/live-calls/1/takeover", json={"participant_id": "listener"})
            self.assertEqual(response.status_code, 502)
        self.db.expire_all()
        self.assertEqual(self.db.query(Call).one().status, "in-progress")

    def test_ended_call_cannot_be_controlled(self):
        self.event("call_ended")
        self.assertEqual(self.client.get("/api/rootcall/live-calls").json(), [])
        self.assertEqual(self.client.post("/api/rootcall/live-calls/1/listen").status_code, 409)

    def test_ai_leg_end_does_not_end_human_conversation(self):
        self.event("call_ended", disconnection_reason="call_take_over")
        self.event("call_analyzed", call_analysis={"call_summary": "Human took over"})
        call = self.db.query(Call).one()
        self.assertEqual(call.status, "human-connected")
        self.assertIsNone(call.ended_at)
        self.assertEqual(len(self.client.get("/api/rootcall/live-calls").json()), 1)
        with patch.object(live_calls, "provider_action", new_callable=AsyncMock) as action:
            self.assertEqual(self.client.post("/api/rootcall/live-calls/1/end").status_code, 409)
            self.assertEqual(self.client.post("/api/rootcall/live-calls/1/release").status_code, 200)
            action.assert_not_awaited()
        self.assertEqual(self.client.get("/api/rootcall/live-calls").json(), [])


if __name__ == "__main__":
    unittest.main()