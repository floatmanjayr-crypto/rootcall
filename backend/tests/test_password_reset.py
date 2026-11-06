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


class PasswordResetTest(unittest.TestCase):
    def setUp(self):
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
        self.assertEqual(response.status_code, 200)
        self.assertIn("If an account exists", response.json()["message"])

    def test_forgot_password_logs_link_when_email_not_configured(self):
        with patch.object(auth.settings, "SENDGRID_API_KEY", ""), \
                self.assertLogs(auth.logger, level="WARNING") as logs:
            response = self.client.post(
                "/api/auth/forgot-password", json={"email": "owner@example.com"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("If an account exists", response.json()["message"])
        self.assertTrue(any("reset-password.html?token=" in line for line in logs.output))

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
            auth.SECRET_KEY,
            algorithms=[auth.ALGORITHM],
        )
        payload["exp"] = 0
        expired = jwt.encode(payload, auth.SECRET_KEY, algorithm=auth.ALGORITHM)
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


if __name__ == "__main__":
    unittest.main()
