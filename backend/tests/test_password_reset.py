import os
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import User
from app.routers import auth
from python_http_client.exceptions import HTTPError as EmailHTTPError


class PasswordResetTest(unittest.TestCase):
    def setUp(self):
        for name, value in {
            "JWT_SECRET_KEY": "test-only-password-reset-signing-key",
            "APP_BASE_URL": "https://rootcall.example",
            "SENDGRID_API_KEY": "test-email-key",
            "SENDER_EMAIL": "support@rootcall.example",
        }.items():
            override = patch.object(auth.settings, name, value)
            override.start()
            self.addCleanup(override.stop)
        email = patch.object(auth.EmailService, "send_email", return_value={"status": 202})
        self.email = email.start()
        self.addCleanup(email.stop)
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(
            id=1,
            email="owner@example.com",
            hashed_password=auth.get_password_hash("old-password"),
        )
        self.db.add(self.user)
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(auth.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def test_forgot_password_returns_generic_message_for_unknown_email(self):
        response = self.client.post(
            "/api/auth/forgot-password", json={"email": "nobody@example.com"}
        )
        self.assertEqual(response.status_code, 202)
        self.assertIn("If an account exists", response.json()["message"])

    def test_forgot_password_configuration_failure_is_explicit_and_never_logs_a_link(self):
        with patch.object(auth.settings, "SENDGRID_API_KEY", ""), \
                self.assertLogs(auth.logger, level="ERROR") as logs:
            response = self.client.post(
                "/api/auth/forgot-password", json={"email": "owner@example.com"}
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("token=", "".join(logs.output))
        self.assertNotIn("owner@example.com", "".join(logs.output))
        self.email.assert_not_called()

    def test_reset_email_uses_configured_origin_not_request_host(self):
        response = self.client.post(
            "/api/auth/forgot-password", json={"email": "owner@example.com"},
            headers={"Host": "untrusted.example"},
        )
        self.assertEqual(response.status_code, 202)
        self.email.assert_called_once()
        html = self.email.call_args.args[2]
        self.assertIn("https://rootcall.example/static/reset-password.html#token=", html)
        self.assertNotIn("?token=", html)
        self.assertNotIn("untrusted.example", html)

    def test_missing_email_configuration_fails_equally_for_unknown_accounts(self):
        with patch.object(auth.settings, "SENDGRID_API_KEY", ""):
            known = self.client.post("/api/auth/forgot-password", json={"email": "owner@example.com"})
            unknown = self.client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        self.assertEqual((known.status_code, known.json()), (unknown.status_code, unknown.json()))
        self.assertEqual(known.status_code, 503)

    def test_invalid_reset_origins_are_rejected_without_sending(self):
        for base in ("", "http://rootcall.example", "https://user:pass@rootcall.example",
                     "https://rootcall.example/path", "https://rootcall.example?bad=1"):
            with self.subTest(base=base), patch.object(auth.settings, "APP_BASE_URL", base):
                response = self.client.post("/api/auth/forgot-password", json={"email": "owner@example.com"})
                self.assertEqual(response.status_code, 503)
        self.email.assert_not_called()

    def test_email_delivery_rejection_and_provider_errors_are_visible_and_sanitized(self):
        self.email.return_value = {"status": 400}
        with self.assertLogs(auth.logger, level="ERROR"):
            response = self.client.post("/api/auth/forgot-password", json={"email": "owner@example.com"})
        unknown = self.client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual((response.status_code, response.json()), (unknown.status_code, unknown.json()))
        self.assertNotIn("has been sent", response.json()["message"])
        for error in (EmailHTTPError(400, "bad request", b"secret reset token=private-value", {}),
                      OSError("secret reset token=private-value")):
            with self.subTest(error=type(error).__name__), self.assertLogs(auth.logger, level="ERROR") as logs:
                self.email.side_effect = error
                response = self.client.post("/api/auth/forgot-password", json={"email": "owner@example.com"})
                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.json(), unknown.json())
                self.assertNotIn("private-value", "".join(logs.output) + response.text)

    def test_reset_password_with_valid_token(self):
        token = auth.create_reset_token(self.user)
        response = self.client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "new-password-123"},
        )
        self.assertEqual(response.status_code, 200)
        self.db.refresh(self.user)
        self.assertTrue(auth.verify_password("new-password-123", self.user.hashed_password))
        # Login works with the new password
        login = self.client.post(
            "/api/auth/login",
            data={"username": "owner@example.com", "password": "new-password-123"},
        )
        self.assertEqual(login.status_code, 200)

    def test_reset_token_is_single_use(self):
        token = auth.create_reset_token(self.user)
        first = self.client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "new-password-123"},
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "another-password"},
        )
        self.assertEqual(second.status_code, 400)

    def test_reset_rejects_login_token(self):
        login_token = auth.create_token(self.user.id)
        response = self.client.post(
            "/api/auth/reset-password",
            json={"token": login_token, "new_password": "new-password-123"},
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_rejects_expired_token(self):
        payload = jwt.decode(
            auth.create_reset_token(self.user),
            auth.settings.JWT_SECRET_KEY,
            algorithms=[auth.settings.JWT_ALGORITHM],
        )
        payload["exp"] = 0
        expired = jwt.encode(payload, auth.settings.JWT_SECRET_KEY, algorithm=auth.settings.JWT_ALGORITHM)
        response = self.client.post(
            "/api/auth/reset-password",
            json={"token": expired, "new_password": "new-password-123"},
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_rejects_short_password(self):
        token = auth.create_reset_token(self.user)
        response = self.client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "short"},
        )
        self.assertEqual(response.status_code, 422)

    def test_reset_rejects_garbage_token(self):
        response = self.client.post(
            "/api/auth/reset-password",
            json={"token": "not-a-token", "new_password": "new-password-123"},
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_rejects_overlong_utf8_password_without_truncating_it(self):
        for password in ("x" * 73, "\u00e9" * 37):
            with self.subTest(password_bytes=len(password.encode("utf-8"))):
                response = self.client.post("/api/auth/reset-password", json={
                    "token": auth.create_reset_token(self.user), "new_password": password,
                })
                self.assertEqual(response.status_code, 422)
                self.db.refresh(self.user)
                self.assertTrue(auth.verify_password("old-password", self.user.hashed_password))

    def test_reset_accepts_exact_72_utf8_bytes(self):
        password = "\u00e9" * 36
        response = self.client.post("/api/auth/reset-password", json={
            "token": auth.create_reset_token(self.user), "new_password": password,
        })
        self.assertEqual(response.status_code, 200)
        self.db.refresh(self.user)
        self.assertTrue(auth.verify_password(password, self.user.hashed_password))

    def test_reset_cannot_reactivate_an_inactive_account(self):
        token = auth.create_reset_token(self.user)
        self.user.is_active = False
        self.db.commit()
        self.assertEqual(self.client.post("/api/auth/reset-password", json={
            "token": token, "new_password": "new-password",
        }).status_code, 400)
        self.assertEqual(self.client.post("/api/auth/forgot-password", json={
            "email": "owner@example.com",
        }).status_code, 202)
        self.email.assert_not_called()

    def test_reset_rejects_missing_expiration_and_malformed_subjects(self):
        original = jwt.decode(
            auth.create_reset_token(self.user), auth.settings.JWT_SECRET_KEY,
            algorithms=[auth.settings.JWT_ALGORITHM],
        )
        payloads = [{key: value for key, value in original.items() if key != "exp"}]
        payloads.extend({**original, "sub": subject} for subject in ("invalid", "9" * 100, "-1", "0"))
        for payload in payloads:
            with self.subTest(subject=payload.get("sub")):
                token = jwt.encode(payload, auth.settings.JWT_SECRET_KEY, algorithm=auth.settings.JWT_ALGORITHM)
                self.assertEqual(self.client.post("/api/auth/reset-password", json={
                    "token": token, "new_password": "new-password",
                }).status_code, 400)


if __name__ == "__main__":
    unittest.main()
