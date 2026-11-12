import os
import subprocess
import sys
import unittest
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app.config import settings
from app.database import get_db
from app.deployment_checks import (
    UNAVAILABLE_MESSAGE, base_url_warnings, log_deployment_readiness, missing_tables, register_error_handlers,
)
from app.models import User
from app.routers import auth, onboarding, payments

BACKEND = Path(__file__).resolve().parents[1]


class DeploymentChecksTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        User.__table__.create(self.engine)

    def test_reports_missing_onboarding_tables(self):
        self.assertEqual(missing_tables(self.engine), ["customer_onboarding", "activation_jobs"])
        with self.assertLogs("app.deployment_checks", "ERROR") as logs:
            log_deployment_readiness(self.engine, "https://rootcall.onrender.com")
        self.assertIn("alembic upgrade head", logs.output[0])

    def test_base_url_warnings(self):
        self.assertTrue(base_url_warnings(""))
        self.assertTrue(base_url_warnings("http://rootcall.example"))
        self.assertEqual(base_url_warnings("https://rootcall.onrender.com", "https://rootcall.onrender.com"), [])
        self.assertEqual(base_url_warnings("https://rootcall.example"), [])
        mismatch = base_url_warnings("https://getrootcall.com", "https://rootcall.onrender.com")
        self.assertEqual(len(mismatch), 1)
        self.assertIn("getrootcall.com", mismatch[0])

    def test_signup_and_payments_return_json_503_when_schema_is_missing(self):
        app = FastAPI()
        register_error_handlers(app)
        for router in (auth.router, payments.router, onboarding.router):
            app.include_router(router)
        session = sessionmaker(bind=self.engine)()
        self.addCleanup(session.close)
        app.dependency_overrides[get_db] = lambda: session
        client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(client.close)
        with patch.object(settings, "JWT_SECRET_KEY", "test-only-deployment-signing-key"), \
                patch.object(settings, "AUTOMATED_ONBOARDING", True):
            response = client.post("/api/auth/signup", json={"email": "new@example.com", "password": "long-enough-password"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": UNAVAILABLE_MESSAGE})

        # The original flow never touches the onboarding tables, so a missing table cannot break signup.
        # (A real request gets a fresh session; this test shares one, so clear the failed transaction first.)
        session.rollback()
        with patch.object(settings, "JWT_SECRET_KEY", "test-only-deployment-signing-key"), \
                patch.object(settings, "AUTOMATED_ONBOARDING", False):
            response = client.post("/api/auth/signup", json={"email": "classic@example.com", "password": "long-enough-password"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["next_url"], "/static/client-portal.html")

    def test_embedded_activation_runner_survives_errors_and_stops(self):
        from threading import Event

        from app import activation_worker

        stopping = Event()
        calls = []

        def fake_run_once(factory, stopping=None):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("temporary database failure")
            if len(calls) >= 3:
                stopping.set()
            return 0

        with patch.object(activation_worker, "run_once", side_effect=fake_run_once), \
                patch.object(settings, "AUTOMATED_ONBOARDING", True):
            thread = activation_worker.start_embedded(stopping, session_factory=object(), interval=0)
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertGreaterEqual(len(calls), 3)

    def test_activation_runner_stays_idle_in_the_original_flow(self):
        from threading import Event

        from app import activation_worker

        stopping = Event()
        with patch.object(activation_worker, "run_once") as run_once, \
                patch.object(settings, "AUTOMATED_ONBOARDING", False), \
                self.assertLogs("app.activation_worker", "INFO") as logs:
            thread = activation_worker.start_embedded(stopping, session_factory=object(), interval=0.01)
            stopping.wait(0.2)
            stopping.set()
            thread.join(timeout=5)
        run_once.assert_not_called()
        self.assertTrue(any("idle" in line for line in logs.output))

    def test_embedded_runner_can_be_disabled(self):
        from app.activation_worker import embedded_enabled

        self.assertTrue(embedded_enabled({}))
        self.assertTrue(embedded_enabled({"ACTIVATION_EMBEDDED_WORKER": "true"}))
        for value in ("false", "0", "OFF", " no "):
            self.assertFalse(embedded_enabled({"ACTIVATION_EMBEDDED_WORKER": value}))

    def test_readiness_names_missing_settings_without_exposing_values(self):
        from types import SimpleNamespace

        from app.deployment_checks import service_readiness

        env = {"STRIPE_SECRET_KEY": "sk_live_SECRET", "STRIPE_ESSENTIAL_PRICE_ID": "price_1",
               "STRIPE_WEBHOOK_SECRET": "whsec_SECRET", "TELNYX_API_KEY": "KEY_SECRET"}
        settings = SimpleNamespace(APP_BASE_URL="https://rootcall.onrender.com", RETELL_API_KEY="retell_SECRET",
                                   TELNYX_API_KEY="")
        with patch.dict(os.environ, {**env, "TELNYX_API_KEY": ""}, clear=False):
            groups = {group["name"]: group for group in service_readiness(settings, self.engine)}
        self.assertTrue(groups["Payments"]["ok"])
        self.assertTrue(groups["AI assistant"]["ok"])
        self.assertEqual(groups["Phone routing"]["missing"], ["TELNYX_API_KEY"])
        self.assertEqual(groups["Database"]["missing"], ["customer_onboarding", "activation_jobs"])
        rendered = str(list(groups.values()))
        for secret in ("SECRET", "price_1"):
            self.assertNotIn(secret, rendered)
        settings.APP_BASE_URL = "http://insecure.example"
        self.assertEqual(
            [g["missing"] for g in service_readiness(settings) if g["name"] == "Public site address"],
            [["APP_BASE_URL (must start with https://)"]],
        )
        with patch.dict(os.environ, {"TELNYX_API_KEY": ""}), \
                self.assertLogs("app.deployment_checks", "WARNING") as logs:
            log_deployment_readiness(self.engine, "https://rootcall.onrender.com", settings)
        self.assertTrue(any("TELNYX_API_KEY" in line for line in logs.output))

    def test_render_url_is_the_base_url_fallback(self):
        script = "from app.config import settings; print(settings.APP_BASE_URL)"
        env = {key: value for key, value in os.environ.items() if key != "APP_BASE_URL"}
        env.update({"RENDER_EXTERNAL_URL": "https://rootcall.onrender.com", "OPENAI_API_KEY": "x", "DATABASE_URL": "sqlite://"})
        fallback = subprocess.run([sys.executable, "-c", script], cwd=BACKEND, env=env, capture_output=True, text=True)
        self.assertEqual(fallback.stdout.strip().splitlines()[-1], "https://rootcall.onrender.com")
        env["APP_BASE_URL"] = "https://custom.example"
        explicit = subprocess.run([sys.executable, "-c", script], cwd=BACKEND, env=env, capture_output=True, text=True)
        self.assertEqual(explicit.stdout.strip().splitlines()[-1], "https://custom.example")


if __name__ == "__main__":
    unittest.main()
