import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

import requests
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from retell.lib.webhook_auth import symmetric
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.models import PhoneNumber, User
from app.models.rootcall_config import RootCallConfig
from app.routers import rootcall_portal, trusted_inbound
from app.services.retell_service import RetellService
from app.services.trusted_routing import enable_trusted_routing


class TrustedInboundTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.db.close)
        self.user = User(id=1, email="owner@example.com", hashed_password="unused")
        self.phone = PhoneNumber(id=1, user_id=1, phone_number="+12025550100", is_active=True)
        self.config = RootCallConfig(
            id=1, user_id=1, phone_number_id=1, client_name="Owner", client_cell="+12025550102",
            retell_agent_id="agent-screen", retell_did="+12025550100",
            trusted_contacts=["+12025550101"], trusted_agent_id="agent-trusted",
            trusted_flow_id="flow-trusted", trusted_routing_enabled=True, is_active=True,
        )
        self.db.add_all([self.user, self.phone, self.config])
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(trusted_inbound.router)
        self.app.include_router(rootcall_portal.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[rootcall_portal.get_current_user] = lambda: self.user
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        for name, value in (("RETELL_API_KEY", "test-key"), ("APP_BASE_URL", "https://rootcall.example")):
            mocked = patch.object(settings, name, value)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.retell = Mock()
        self.retell.get_phone_number.return_value = {
            "phone_number": "+12025550100",
            "inbound_agents": [{"agent_id": "agent-screen", "weight": 1}],
            "sip_outbound_trunk_config": {"auth_username": "existing-sip-user"},
        }
        self.retell.create_trusted_transfer_flow.return_value = "flow-created"
        self.retell.create_trusted_transfer_agent.return_value = "agent-created"

    def inbound(self, caller="+12025550101", number="+12025550100", **extra):
        body = json.dumps({"event": "call_inbound", "call_inbound": {
            "from_number": caller, "to_number": number, **extra,
        }})
        return self.client.post("/retell/rootcall-inbound", content=body, headers={
            "x-retell-signature": symmetric["sign"](body, "test-key"),
            "Content-Type": "application/json",
        })

    def test_trusted_uses_silent_transfer_agent_and_database_destination(self):
        response = self.inbound(rootcall_forwarding="+19999999999",
                                dynamic_variables={"rootcall_forwarding": "+19999999999"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"call_inbound": {
            "override_agent_id": "agent-trusted",
            "dynamic_variables": {"rootcall_forwarding": "+12025550102"},
            "metadata": {"rootcall_routing": "trusted_bypass"},
        }})

    def test_unknown_and_hidden_caller_keep_existing_screening_agent(self):
        for caller in ("+12025550199", "anonymous", "", "<script>trusted</script>"):
            with self.subTest(caller=caller):
                self.assertEqual(self.inbound(caller).json(), {
                    "call_inbound": {"override_agent_id": "agent-screen"},
                })

    def test_duplicate_inbound_deliveries_are_side_effect_free(self):
        with patch.object(RetellService, "_post") as provider:
            first = self.inbound().json()
            self.assertEqual(self.inbound().json(), first)
            provider.assert_not_called()

    def test_normalizes_caller_and_legacy_saved_contact_formats(self):
        self.config.trusted_contacts = ["202-555-0101"]
        self.db.commit()
        for caller in ("+12025550101", "12025550101", "(202) 555-0101"):
            self.assertEqual(self.inbound(caller).json()["call_inbound"]["override_agent_id"], "agent-trusted")

    def test_contact_removal_and_addition_change_next_call_without_provider_updates(self):
        response = self.client.delete("/api/rootcall/trusted-contacts/1/+12025550101")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.inbound().json()["call_inbound"]["override_agent_id"], "agent-screen")
        response = self.client.post("/api/rootcall/trusted-contacts/1", json={"phone_number": "202-555-0101"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.inbound().json()["call_inbound"]["override_agent_id"], "agent-trusted")

    def test_forwarding_updates_are_used_on_next_inbound_call(self):
        with patch.object(rootcall_portal, "RetellService") as provider:
            response = self.client.patch("/api/rootcall/config/1", json={"client_cell": "+12025550109"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.inbound().json()["call_inbound"]["dynamic_variables"],
                         {"rootcall_forwarding": "+12025550109"})
        provider.return_value.configure_transfer_tool.assert_called_once()

    def test_other_accounts_contacts_do_not_grant_bypass(self):
        self.db.add(User(id=2, email="other@example.com", hashed_password="unused"))
        self.db.add(PhoneNumber(id=2, user_id=2, phone_number="+12025550110", is_active=True))
        self.db.add(RootCallConfig(
            user_id=2, phone_number_id=2, client_name="Other", client_cell="+12025550112",
            retell_agent_id="other-screen", retell_did="+12025550110", trusted_contacts=[],
            trusted_agent_id="other-trusted", trusted_routing_enabled=True,
        ))
        self.db.commit()
        self.assertEqual(self.inbound(number="+12025550110").json(), {
            "call_inbound": {"override_agent_id": "other-screen"},
        })
        self.assertEqual(self.client.post("/api/rootcall/trusted-routing/2").status_code, 403)

    def test_unsigned_and_tampered_inbound_are_rejected(self):
        self.assertEqual(self.client.post("/retell/rootcall-inbound", json={
            "event": "call_inbound",
        }).status_code, 401)
        body = '{"event":"call_inbound"}'
        response = self.client.post("/retell/rootcall-inbound", content=body + " ", headers={
            "x-retell-signature": symmetric["sign"](body, "test-key"),
        })
        self.assertEqual(response.status_code, 401)

    def test_signed_malformed_payloads_fail_explicitly(self):
        for body in ("bad-json", "[]", '{"event":"chat_inbound"}',
                     '{"event":"call_inbound","call_inbound":{"to_number":5}}'):
            with self.subTest(body=body):
                response = self.client.post("/retell/rootcall-inbound", content=body, headers={
                    "x-retell-signature": symmetric["sign"](body, "test-key"),
                })
                self.assertIn(response.status_code, (400, 422))

    def test_inactive_and_unknown_lines_reject(self):
        self.assertEqual(self.inbound(number="+12025550999").json(), {"call_inbound": {"reject": True}})
        for instance in (self.phone, self.config, self.user):
            instance.is_active = False
            self.db.commit()
            self.assertEqual(self.inbound().json(), {"call_inbound": {"reject": True}})
            instance.is_active = True
            self.db.commit()

    def test_incomplete_enabled_routing_does_not_transfer(self):
        for forwarding in ("", "bad", self.phone.phone_number):
            self.config.client_cell = forwarding
            self.db.commit()
            self.assertEqual(self.inbound().json(), {"call_inbound": {"reject": True}})

    def test_setup_wires_number_webhook_without_replacing_screening_binding(self):
        self.config.trusted_flow_id = None
        self.config.trusted_agent_id = None
        self.config.trusted_routing_enabled = False
        self.db.commit()
        enable_trusted_routing(self.db, self.config, self.phone.phone_number, self.retell)
        self.retell.create_trusted_transfer_flow.assert_called_once_with("existing-sip-user")
        self.retell.create_trusted_transfer_agent.assert_called_once_with(
            "RootCall-Trusted-1-1", "flow-created", "agent-screen", "https://rootcall.example/retell/webhook",
        )
        self.retell.configure_inbound_webhook.assert_called_once_with(
            "+12025550100", "https://rootcall.example/retell/rootcall-inbound",
        )
        self.assertTrue(self.config.trusted_routing_enabled)

    def test_enable_failure_retains_checkpoints_and_retry_does_not_duplicate_resources(self):
        self.config.trusted_flow_id = None
        self.config.trusted_agent_id = None
        self.config.trusted_routing_enabled = False
        self.db.commit()
        self.retell.configure_inbound_webhook.side_effect = requests.Timeout("offline")
        with patch("app.services.trusted_routing.RetellService", return_value=self.retell):
            response = self.client.post("/api/rootcall/trusted-routing/1")
            self.assertEqual(response.status_code, 502, response.text)
            self.db.expire_all()
            self.assertFalse(self.config.trusted_routing_enabled)
            self.assertEqual(self.config.trusted_agent_id, "agent-created")
            self.retell.configure_inbound_webhook.side_effect = None
            response = self.client.post("/api/rootcall/trusted-routing/1")
            self.assertEqual(response.status_code, 200, response.text)
        self.retell.create_trusted_transfer_agent.assert_called_once()
        self.retell.create_trusted_transfer_flow.assert_called_once()
        self.assertEqual(self.inbound().json()["call_inbound"]["override_agent_id"], "agent-created")

    def test_existing_custom_webhook_or_foreign_binding_is_not_overwritten(self):
        for changes in ({"inbound_webhook_url": "https://other.example/inbound"},
                        {"inbound_agents": [{"agent_id": "foreign"}]}):
            with self.subTest(changes=changes):
                original = self.retell.get_phone_number.return_value.copy()
                self.retell.get_phone_number.return_value.update(changes)
                with patch("app.services.trusted_routing.RetellService", return_value=self.retell):
                    response = self.client.post("/api/rootcall/trusted-routing/1")
                    self.assertEqual(response.status_code, 409, response.text)
                self.retell.configure_inbound_webhook.assert_not_called()
                self.retell.get_phone_number.return_value = original


class TrustedTransferContractTest(unittest.TestCase):
    def test_trusted_agent_uses_existing_voice_flow_engine_and_signed_event_url(self):
        service = RetellService(api_key="test-key")
        with patch.object(service, "_get", return_value={"voice_id": "selected-voice", "language": "en-US"}), \
                patch.object(service, "_post", return_value={"agent_id": "trusted-agent"}) as post:
            result = service.create_trusted_transfer_agent(
                "Trusted", "flow", "screen-agent", "https://rootcall.example/retell/webhook",
            )
        self.assertEqual(result, "trusted-agent")
        payload = post.call_args.args[1]
        self.assertEqual(payload["response_engine"], {"type": "conversation-flow", "conversation_flow_id": "flow"})
        self.assertEqual(payload["voice_id"], "selected-voice")
        self.assertEqual(payload["webhook_url"], "https://rootcall.example/retell/webhook")
        self.assertFalse(payload["enable_backchannel"])

    def test_transfer_flow_starts_at_silent_transfer_not_an_llm_conversation(self):
        service = RetellService(api_key="test-key")
        with patch.object(service, "_post", return_value={"conversation_flow_id": "flow"}) as post:
            self.assertEqual(service.create_trusted_transfer_flow("actual-sip-user"), "flow")
        path, payload = post.call_args.args
        self.assertEqual(path, "/create-conversation-flow")
        start = next(node for node in payload["nodes"] if node["id"] == payload["start_node_id"])
        self.assertEqual(start["type"], "transfer_call")
        self.assertFalse(start["speak_during_execution"])
        self.assertEqual(start["transfer_option"], {"type": "cold_transfer"})
        self.assertEqual(start["transfer_destination"]["number"], "{{rootcall_forwarding}}")
        self.assertEqual(start["custom_sip_headers"], {"X-Telnyx-Username": "actual-sip-user"})
        self.assertFalse(payload["flex_mode"])
        end = next(node for node in payload["nodes"] if node["id"] == start["edge"]["destination_node_id"])
        self.assertEqual(end["type"], "end")
        self.assertIn("could not connect", end["instruction"]["text"])

    def test_ip_authenticated_transfer_does_not_invent_sip_credentials(self):
        service = RetellService(api_key="test-key")
        with patch.object(service, "_post", return_value={"conversation_flow_id": "flow"}) as post:
            service.create_trusted_transfer_flow()
        self.assertNotIn("custom_sip_headers", post.call_args.args[1]["nodes"][0])

    def test_trusted_routing_migration_preserves_existing_configs(self):
        path = Path(__file__).parents[1] / "alembic/versions/b921df43c107_add_trusted_inbound_routing.py"
        spec = importlib.util.spec_from_file_location("trusted_routing_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql("CREATE TABLE rootcall_configs (id INTEGER PRIMARY KEY)")
                connection.exec_driver_sql("INSERT INTO rootcall_configs (id) VALUES (1)")
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                    self.assertEqual(connection.exec_driver_sql(
                        "SELECT trusted_routing_enabled FROM rootcall_configs WHERE id=1",
                    ).scalar(), 0)
                    migration.downgrade()
                    self.assertEqual({column["name"] for column in inspect(connection).get_columns("rootcall_configs")}, {"id"})
        finally:
            engine.dispose()
