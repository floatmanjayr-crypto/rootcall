import json
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import PhoneNumber, User
from app.models.rootcall_config import RootCallConfig
from app.routers import rootcall_portal, rootcall_screen
from app.services import client_config


class CallRoutingTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(User(id=1, email="owner@example.com", hashed_password="unused"))
        self.db.add(PhoneNumber(id=1, user_id=1, phone_number="+12025550100",
                                telnyx_connection_id="connection-test"))
        self.config = RootCallConfig(
            phone_number_id=1, user_id=1, client_name="Test",
            client_cell="+12025550102", retell_agent_id="agent-test",
            retell_did="+12025550100", trusted_contacts=["+12025550101"],
            sms_alerts_enabled=False,
        )
        self.db.add(self.config)
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(rootcall_portal.router)
        self.app.include_router(rootcall_screen.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[rootcall_portal.get_current_user] = lambda: self.db.get(User, 1)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_trusted_contact_edits_persist_after_reload(self):
        response = self.client.post("/api/rootcall/trusted-contacts/1", json={
            "phone_number": "+12025550103", "name": "Family",
        })
        self.assertEqual(response.status_code, 200)
        self.db.expire_all()
        self.assertIn("+12025550103", self.config.trusted_contacts)
        response = self.client.delete("/api/rootcall/trusted-contacts/1/+12025550101")
        self.assertEqual(response.status_code, 200)
        self.db.expire_all()
        self.assertNotIn("+12025550101", self.config.trusted_contacts)

    def test_failed_transfer_configuration_does_not_save_forwarding_number(self):
        with patch.object(rootcall_portal, "RetellService") as service, \
                patch.object(rootcall_portal, "TelnyxService") as telnyx:
            service.return_value.configure_transfer_tool.side_effect = RuntimeError("Provider rejected")
            response = self.client.patch("/api/rootcall/config/1", json={
                "client_cell": "+12025550103",
            })
        self.assertEqual(response.status_code, 502)
        self.db.expire_all()
        self.assertEqual(self.config.client_cell, "+12025550102")
        telnyx.return_value.ensure_outbound_voice_profile.assert_called_once_with("connection-test")

    def test_trunk_without_login_is_repaired_and_transfer_names_the_login(self):
        with patch.object(rootcall_portal, "RetellService") as retell, \
                patch.object(rootcall_portal, "TelnyxService") as telnyx:
            telnyx.return_value.trunk_username.return_value = None
            response = self.client.patch("/api/rootcall/config/1", json={"client_cell": "+12025550103"})
        self.assertEqual(response.status_code, 200, response.text)
        login = retell.return_value.update_phone_number.call_args.kwargs
        self.assertTrue(login["auth_username"].isalnum() and login["auth_password"].isalnum())
        telnyx.return_value.set_trunk_credentials.assert_called_once_with(
            "connection-test", login["auth_username"], login["auth_password"]
        )
        self.assertEqual(
            retell.return_value.configure_transfer_tool.call_args.kwargs["custom_sip_headers"],
            {"X-Telnyx-Username": login["auth_username"]},
        )

    def test_trunk_with_login_is_not_changed_and_its_login_is_sent(self):
        with patch.object(rootcall_portal, "RetellService") as retell, \
                patch.object(rootcall_portal, "TelnyxService") as telnyx:
            telnyx.return_value.trunk_username.return_value = "existinglogin"
            response = self.client.patch("/api/rootcall/config/1", json={"client_cell": "+12025550103"})
        self.assertEqual(response.status_code, 200, response.text)
        retell.return_value.update_phone_number.assert_not_called()
        telnyx.return_value.set_trunk_credentials.assert_not_called()
        self.assertEqual(
            retell.return_value.configure_transfer_tool.call_args.kwargs["custom_sip_headers"],
            {"X-Telnyx-Username": "existinglogin"},
        )

    def test_shared_contact_helpers_persist_after_reload(self):
        self.assertTrue(client_config.add_trusted_contact(
            "+12025550100", "+12025550103", self.db
        ))
        self.db.expire_all()
        self.assertIn("+12025550103", self.config.trusted_contacts)
        self.assertTrue(client_config.remove_trusted_contact(
            "+12025550100", "+12025550103", self.db
        ))
        self.db.expire_all()
        self.assertNotIn("+12025550103", self.config.trusted_contacts)

    def test_missing_sip_connection_blocks_forwarding_before_provider_changes(self):
        self.db.get(PhoneNumber, 1).telnyx_connection_id = None
        self.db.commit()
        with patch.object(rootcall_portal, "RetellService") as retell:
            response = self.client.patch("/api/rootcall/config/1", json={"client_cell": "+12025550103"})
        self.assertEqual(response.status_code, 409)
        retell.assert_not_called()
        self.assertEqual(self.config.client_cell, "+12025550102")

    def test_forwarding_never_accepts_own_shield_number(self):
        with patch.object(rootcall_portal, "TelnyxService") as telnyx:
            response = self.client.patch("/api/rootcall/config/1", json={"client_cell": "+12025550100"})
        self.assertEqual(response.status_code, 422)
        telnyx.assert_not_called()

    def test_voice_failure_preserves_saved_preference_and_success_persists(self):
        with patch.object(rootcall_portal, "RetellService") as retell:
            retell.return_value.list_voices.return_value = [{"voice_id": "voice-test"}]
            retell.return_value.update_voice.side_effect = RuntimeError("Provider rejected")
            response = self.client.patch("/api/rootcall/config/1", json={"voice_id": "voice-test"})
            self.assertEqual(response.status_code, 502)
            self.db.expire_all()
            self.assertEqual(self.config.voice_id, "11labs-Adrian")
            retell.return_value.update_voice.side_effect = None
            response = self.client.patch("/api/rootcall/config/1", json={"voice_id": "voice-test"})
            self.assertEqual(response.status_code, 200)
            self.db.expire_all()
            self.assertEqual(self.config.voice_id, "voice-test")

    def test_account_name_and_identity_sync_keep_owner_from_database(self):
        response = self.client.patch("/api/rootcall/config/1", json={"full_name": "Jordan Example"})
        self.assertEqual(response.status_code, 200)
        with patch.object(rootcall_portal, "RetellService") as retell:
            response = self.client.post("/api/rootcall/sync-agent-identity/1")
        self.assertEqual(response.status_code, 200)
        retell.return_value.update_screening_identity.assert_called_once_with("agent-test", "Jordan Example")
        self.db.expire_all()
        self.assertEqual(self.config.client_name, "Jordan Example")

    def test_voice_migration_handles_old_and_already_upgraded_databases(self):
        path = Path(__file__).parents[1] / "alembic/versions/e254ab76f430_preserve_retell_voice_preference.py"
        spec = importlib.util.spec_from_file_location("voice_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with self.engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            connection.execute(text("ALTER TABLE rootcall_configs DROP COLUMN voice_id"))
            migration.upgrade()
            self.assertEqual(connection.execute(text(
                "SELECT voice_id FROM rootcall_configs WHERE id = 1"
            )).scalar(), "11labs-Adrian")
            connection.execute(text("UPDATE rootcall_configs SET voice_id='voice-test' WHERE id=1"))
            migration.upgrade()
            migration.downgrade()
            self.assertEqual(connection.execute(text(
                "SELECT voice_id FROM rootcall_configs WHERE id = 1"
            )).scalar(), "voice-test")

    def answered(self, caller="+12025550101", name=""):
        return self.client.post("/telnyx/rootcall/webhook", json={"data": {
            "event_type": "call.answered",
            "payload": {
                "call_control_id": "test-control", "from": caller,
                "to": "+12025550100", "caller_id_name": name,
            },
        }})

    def config_values(self):
        return {
            "client_cell": "+12025550102", "trusted_contacts": ["+12025550101"],
            "sms_alerts_enabled": False,
        }

    def test_trusted_caller_bypasses_screening_even_with_spam_cnam(self):
        with patch.object(rootcall_screen, "get_client_config", return_value=self.config_values()), \
                patch.object(rootcall_screen, "telnyx_transfer", new_callable=AsyncMock, return_value={}) as transfer, \
                patch.object(rootcall_screen, "telnyx_gather_speak", new_callable=AsyncMock) as screen, \
                patch.object(rootcall_screen, "telnyx_hangup", new_callable=AsyncMock) as hangup:
            response = self.answered(name="Spam Risk")
        self.assertEqual(response.json()["status"], "trusted_forwarded")
        transfer.assert_awaited_once_with("test-control", "+12025550102")
        screen.assert_not_awaited()
        hangup.assert_not_awaited()

    def test_unknown_caller_still_screened(self):
        with patch.object(rootcall_screen, "get_client_config", return_value=self.config_values()), \
                patch.object(rootcall_screen, "telnyx_transfer", new_callable=AsyncMock) as transfer, \
                patch.object(rootcall_screen, "telnyx_gather_speak", new_callable=AsyncMock) as screen:
            response = self.answered(caller="+12025550104")
        self.assertEqual(response.json()["status"], "screening_started")
        screen.assert_awaited_once()
        transfer.assert_not_awaited()

    def test_trusted_transfer_failure_is_not_reported_as_forwarded(self):
        with patch.object(rootcall_screen, "get_client_config", return_value=self.config_values()), \
                patch.object(rootcall_screen, "telnyx_transfer", new_callable=AsyncMock) as transfer:
            transfer.side_effect = HTTPException(status_code=502, detail="Call transfer failed")
            response = self.answered()
        self.assertEqual(response.status_code, 502)

    def test_telnyx_transfer_sends_destination_and_authorization(self):
        async def respond(request):
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(request.url.path, "/v2/calls/test-control/actions/transfer")
            self.assertEqual(json.loads(request.content), {"to": "+12025550102"})
            return httpx.Response(200, json={"data": {"result": "ok"}})

        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch.object(rootcall_screen, "TELNYX_API_KEY", "test-key"), \
                patch.object(rootcall_screen, "DRY_RUN", False), \
                patch.object(rootcall_screen, "get_client_config", return_value=self.config_values()), \
                patch.object(rootcall_screen.httpx, "AsyncClient", return_value=client):
            response = self.answered()
        self.assertEqual(response.json()["status"], "trusted_forwarded")

    def test_telnyx_rejection_is_visible(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(422, json={"errors": [{"detail": "Cannot transfer"}]})
        ))
        with patch.object(rootcall_screen, "TELNYX_API_KEY", "test-key"), \
                patch.object(rootcall_screen, "DRY_RUN", False), \
                patch.object(rootcall_screen, "get_client_config", return_value=self.config_values()), \
                patch.object(rootcall_screen.httpx, "AsyncClient", return_value=client):
            response = self.answered()
        self.assertEqual(response.status_code, 502)
