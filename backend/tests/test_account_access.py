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

from app.config import settings
from app.core import security
from app.database import Base, get_db
from app.models import User
from app.routers import admin, auth, rootcall_portal


class AccountAccessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = auth.get_password_hash("test-password")

    def setUp(self):
        self.key = patch.object(settings, "JWT_SECRET_KEY", "test-only-signing-key-not-for-production")
        self.key.start()
        self.addCleanup(self.key.stop)
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.db.close)
        self.db.add_all([
            User(id=1, email="admin@example.com", hashed_password=self.password_hash,
                 is_superuser=True, is_active=True),
            User(id=2, email="customer@example.com", hashed_password=self.password_hash,
                 is_active=True),
            User(id=3, email="inactive@example.com", hashed_password=self.password_hash,
                 is_superuser=True, is_active=False),
        ])
        self.db.commit()
        self.app = FastAPI()
        for router in (admin.router, auth.router, rootcall_portal.router):
            self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def token(self, user_id=1, **claims):
        return security.create_access_token({"sub": str(user_id), **claims})

    def headers(self, user_id=1):
        return {"Authorization": f"Bearer {self.token(user_id)}"}

    def test_existing_admin_urls_require_bearer_auth_not_an_admin_id(self):
        for path in ("/api/admin/dashboard/1", "/api/admin/users/1"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
                self.assertEqual(self.client.get(path, headers=self.headers(2)).status_code, 403)
                self.assertEqual(self.client.get(path, headers=self.headers(3)).status_code, 401)
                self.assertEqual(self.client.get(path, headers=self.headers()).status_code, 200)

    def test_canonical_admin_urls_and_role_revocation(self):
        for path in ("/api/admin/dashboard", "/api/admin/users"):
            self.assertEqual(self.client.get(path, headers=self.headers()).status_code, 200)
            self.assertEqual(self.client.get(path, headers=self.headers(2)).status_code, 403)
        headers = self.headers()
        self.db.get(User, 1).is_superuser = False
        self.db.commit()
        self.assertEqual(self.client.get("/api/admin/dashboard", headers=headers).status_code, 403)

    def test_legacy_admin_id_must_match_authenticated_admin(self):
        self.assertEqual(self.client.get("/api/admin/users/2", headers=self.headers()).status_code, 403)

    def test_admin_pagination_is_bounded(self):
        headers = self.headers()
        for query in ("skip=-1", "limit=0", "limit=101"):
            self.assertEqual(self.client.get(f"/api/admin/users?{query}", headers=headers).status_code, 422)
        response = self.client.get("/api/admin/users?skip=1&limit=1", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["users"]), 1)
        self.assertEqual(response.json()["total"], 3)

    def test_public_auth_debug_routes_are_removed(self):
        for path in ("/api/auth/debug-jwt", "/api/auth/test-token-decode?token=example"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_malformed_subjects_expiry_and_purpose_fail_closed(self):
        for subject in ("not-a-number", "", "-1", "0", "1.5", "9" * 100, None, [], {}, True):
            with self.subTest(subject=subject):
                token = self.token(sub=subject)
                response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(response.status_code, 401)
                response = self.client.get("/api/rootcall/stats/1", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(response.status_code, 401)
        for claims in ({"exp": 0}, {"purpose": "pwd_reset"}):
            payload = jwt.decode(self.token(), settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            token = jwt.encode({**payload, **claims}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
            self.assertEqual(self.client.get("/api/auth/me", headers={
                "Authorization": f"Bearer {token}",
            }).status_code, 401)
        no_expiry = jwt.encode({"sub": "1"}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        self.assertEqual(self.client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {no_expiry}",
        }).status_code, 401)

    def test_inactive_accounts_cannot_login_or_use_existing_tokens(self):
        login = self.client.post("/api/auth/login", data={
            "username": "inactive@example.com", "password": "test-password",
        })
        self.assertEqual(login.status_code, 401)
        for path in ("/api/auth/me", "/api/rootcall/stats/3"):
            self.assertEqual(self.client.get(path, headers=self.headers(3)).status_code, 401)

    def test_reset_tokens_and_invalid_signatures_cannot_access_administration(self):
        reset_token = auth.create_reset_token(self.db.get(User, 1))
        invalid_signature = jwt.encode(
            {"sub": "1", "exp": 9999999999}, "different-test-key",
            algorithm=settings.JWT_ALGORITHM,
        )
        for token in (reset_token, invalid_signature, "not-a-token"):
            for path in ("/api/admin/dashboard", "/api/admin/users", "/api/admin/dashboard/1"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path, headers={
                        "Authorization": f"Bearer {token}",
                    }).status_code, 401)

    def test_customer_login_me_and_existing_sessions_remain_compatible(self):
        login = self.client.post("/api/auth/login", data={
            "username": "customer@example.com", "password": "test-password",
        })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["next_url"], "/static/client-portal.html")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        profile = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(profile.status_code, 200)
        self.assertFalse(profile.json()["is_superuser"])
        self.assertEqual(self.client.get("/api/rootcall/stats/2", headers=headers).status_code, 200)
        profile = self.client.get("/api/auth/me", headers=self.headers())
        self.assertTrue(profile.json()["is_superuser"])

    def test_missing_or_placeholder_signing_key_does_not_issue_or_accept_tokens(self):
        token = self.token()
        for key in ("", " ", "your-secret-key-change-in-production"):
            with self.subTest(key=key), patch.object(settings, "JWT_SECRET_KEY", key):
                response = self.client.post("/api/auth/login", data={
                    "username": "customer@example.com", "password": "test-password",
                })
                self.assertEqual(response.status_code, 503)
                self.assertEqual(self.client.get("/api/auth/me", headers={
                    "Authorization": f"Bearer {token}",
                }).status_code, 503)
                response = self.client.post("/api/auth/signup", json={
                    "email": "new@example.com", "password": "test-password",
                })
                self.assertEqual(response.status_code, 503)
                self.assertIsNone(self.db.query(User).filter(User.email == "new@example.com").first())
