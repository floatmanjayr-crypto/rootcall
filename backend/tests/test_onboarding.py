import importlib.util
import json
import os
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

import requests
import stripe
import httpx
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from retell.lib.webhook_auth import symmetric
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.models import User
from app.models.onboarding import CustomerOnboarding
from app.models.activation_job import ActivationJob
from app.models.phone_number import PhoneNumber
from app.models.rootcall_config import RootCallConfig
from app.routers import auth, onboarding, payments, rootcall_portal, trusted_inbound
from app.services import customer_onboarding
from app.services import activation_jobs
from app.services.retell_service import RetellService
from app.services.telnyx_service import TelnyxService


class OnboardingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = auth.get_password_hash("test-password")

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(settings, "JWT_SECRET_KEY", "test-only-onboarding-signing-key"))
        # These tests cover the automated paid-onboarding flow, which is opt-in.
        self.stack.enter_context(patch.object(settings, "AUTOMATED_ONBOARDING", True))
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.db.close)
        self.user = User(id=1, email="owner@example.com", hashed_password=self.password_hash)
        self.db.add(self.user)
        self.db.add(User(id=2, email="other@example.com", hashed_password=self.password_hash))
        self.db.flush()
        self.state = customer_onboarding.new_onboarding(1)
        self.state.tier = "essential"
        self.db.add(self.state)
        self.db.commit()
        self.app = FastAPI()
        for router in (auth.router, payments.router, onboarding.router, rootcall_portal.router, trusted_inbound.router):
            self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": f"Bearer {auth.create_token(1)}"}
        for name, value in {
            "APP_BASE_URL": "https://rootcall.example",
            "STRIPE_WEBHOOK_SECRET": "test-webhook",
            "TELNYX_SIP_USERNAME": "test-rootcall",
            "TELNYX_SIP_PASSWORD": "test-sip-password",
            "TELNYX_OUTBOUND_VOICE_PROFILE_ID": "profile-test",
        }.items():
            self.stack.enter_context(patch.object(settings, name, value))
        self.stack.enter_context(patch.object(stripe, "api_key", "test-stripe-key"))
        self.stack.enter_context(patch.dict(payments.PRICE_MAP, {"essential": "price-test"}))
        self.subscription = self.stack.enter_context(patch.object(stripe.Subscription, "retrieve"))
        self.subscription.return_value = {"id": "sub-test", "customer": "cus-test", "status": "active"}
        self.checkout = self.stack.enter_context(patch.object(stripe.checkout.Session, "retrieve"))
        self.checkout.return_value = self.checkout_data()
        self.telnyx = Mock()
        self.retell = Mock()
        self.stack.enter_context(patch.object(customer_onboarding, "TelnyxService", return_value=self.telnyx))
        self.stack.enter_context(patch.object(onboarding, "TelnyxService", return_value=self.telnyx))
        self.stack.enter_context(patch.object(customer_onboarding, "RetellService", return_value=self.retell))
        self.retell.list_voices.return_value = [
            {"voice_id": "voice-test", "voice_name": "Avery", "provider": "elevenlabs",
             "preview_audio_url": "https://example.com/preview.mp3"},
            {"voice_id": "voice-xai", "voice_name": "Unsupported", "provider": "xai"},
        ]
        self.telnyx.search_available_numbers.return_value = [{"phone_number": "+12025550100"}]
        self.telnyx.order_number.return_value = {"data": {"id": "order-test"}}
        self.telnyx.get_or_create_retell_trunk.return_value = ({"id": "connection-test"}, "user", "password")
        self.retell.create_llm.return_value = "llm-test"
        self.retell.create_agent.return_value = "agent-test"
        self.retell.list_phone_numbers.return_value = []
        self.retell.get_phone_number.return_value = {
            "phone_number": "+12025550100",
            "inbound_agents": [{"agent_id": "agent-test", "weight": 1}],
            "sip_outbound_trunk_config": {"auth_username": "test-rootcall_1"},
        }
        self.retell.create_trusted_transfer_flow.return_value = "flow-trusted"
        self.retell.create_trusted_transfer_agent.return_value = "agent-trusted"

    def checkout_data(self, **overrides):
        return {
            "id": "cs-test", "status": "complete", "payment_status": "paid",
            "mode": "subscription", "customer": "cus-test", "subscription": "sub-test",
            "metadata": {"user_id": "1", "tier": "essential", "flow": "rootcall_onboarding_v1",
                         "checkout_key": self.state.checkout_key},
            **overrides,
        }

    def paid(self):
        self.state.stripe_customer_id = "cus-test"
        self.state.stripe_subscription_id = "sub-test"
        self.state.payment_status = "active"
        self.db.commit()

    def ready(self):
        self.paid()
        self.state.first_name = "Jordan"
        self.state.last_name = "Green"
        self.state.forwarding_number = "+12025550123"
        self.state.voice_id = "voice-test"
        self.state.shield_number = "+12025550100"
        self.user.full_name = "Jordan Green"
        self.db.commit()

    def post(self, path, body=None):
        return self.client.post(path, headers=self.headers, json=body)

    def activate(self):
        """Exercise provider checkpoints directly, independently of job scheduling."""
        try:
            return httpx.Response(200, json=customer_onboarding.provision_customer(self.db, self.user))
        except HTTPException as error:
            return httpx.Response(error.status_code, json={"detail": error.detail})

    def profile(self, **overrides):
        return {"first_name": "Jordan", "last_name": "Green", "email": "owner@example.com",
                "forwarding_number": "(202) 555-0123", "voice_id": "voice-test", **overrides}

    def owned_number(self, **overrides):
        return {"id": "number-test", "phone_number": "+12025550100", "connection_id": None, **overrides}

    def test_signup_creates_resumable_onboarding_without_profile(self):
        response = self.client.post("/api/auth/signup", json={
            "email": "new@example.com", "password": "valid-password",
        })
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["next_url"], "/static/onboarding.html")
        state = self.db.get(CustomerOnboarding, data["user"]["id"])
        self.assertEqual(state.payment_status, "pending")
        self.assertIsNone(state.first_name)
        self.assertTrue(state.checkout_key)

    def test_missing_onboarding_table_returns_actionable_service_unavailable(self):
        CustomerOnboarding.__table__.drop(self.engine)
        self.db.expunge_all()
        response = self.client.get("/api/onboarding/status", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Your saved setup is temporarily unavailable. Please try again or contact support.",
        )

    def test_missing_activation_job_table_returns_actionable_service_unavailable(self):
        ActivationJob.__table__.drop(self.engine)
        self.db.expire_all()
        response = self.client.get("/api/onboarding/status", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertIn("saved setup is temporarily unavailable", response.json()["detail"])

    def test_signup_rejects_short_and_multibyte_oversized_passwords(self):
        for password in ("short", "x" * 73, "\u00e9" * 37):
            with self.subTest(password_length=len(password)):
                response = self.client.post("/api/auth/signup", json={
                    "email": "new@example.com", "password": password,
                })
                self.assertEqual(response.status_code, 422)

    def test_auth_routes_new_customers_and_preserves_legacy_users(self):
        for user_id, expected in ((1, "/static/onboarding.html"), (2, "/static/client-portal.html")):
            response = self.client.get("/api/auth/me", headers={
                "Authorization": f"Bearer {auth.create_token(user_id)}",
            })
            self.assertEqual(response.json()["next_url"], expected)
        response = self.client.post("/api/auth/login", data={
            "username": "owner@example.com", "password": "test-password",
        })
        self.assertEqual(response.json()["next_url"], "/static/onboarding.html")

    def test_reset_tokens_cannot_access_paid_apis_or_account(self):
        headers = {"Authorization": f"Bearer {auth.create_reset_token(self.user)}"}
        for path in ("/api/auth/me", "/api/onboarding/status"):
            self.assertEqual(self.client.get(path, headers=headers).status_code, 401)

    def test_payment_and_setup_require_authentication(self):
        self.assertEqual(self.client.post("/api/payments/create-checkout", json={"tier": "essential"}).status_code, 401)
        self.assertEqual(self.client.get("/api/onboarding/status").status_code, 401)
        self.assertEqual(self.client.post("/api/payments/billing-portal").status_code, 401)

    def test_billing_portal_uses_owned_customer_and_configured_return_url(self):
        self.paid()
        self.state.payment_status = "inactive"
        self.db.commit()
        with patch.object(stripe.billing_portal.Session, "create", return_value=SimpleNamespace(
            url="https://billing.stripe.com/test",
        )) as create:
            response = self.client.post("/api/payments/billing-portal", headers={
                **self.headers, "Origin": "https://attacker.example",
            }, json={"customer": "cus-other"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["portal_url"], "https://billing.stripe.com/test")
        create.assert_called_once_with(customer="cus-test",
                                       return_url="https://rootcall.example/static/onboarding.html")
        self.subscription.assert_not_called()

    def test_billing_portal_requires_verified_customer_and_surfaces_stripe_failures(self):
        with patch.object(stripe.billing_portal.Session, "create") as create:
            response = self.post("/api/payments/billing-portal")
            self.assertEqual(response.status_code, 409, response.text)
            create.assert_not_called()
        self.paid()
        with patch.object(stripe.billing_portal.Session, "create", side_effect=stripe.APIConnectionError("offline")):
            response = self.post("/api/payments/billing-portal")
            self.assertEqual(response.status_code, 502, response.text)

    def test_completed_and_legacy_billing_returns_to_dashboard(self):
        self.paid()
        self.state.status = "completed"
        self.db.commit()
        with patch.object(stripe.billing_portal.Session, "create", return_value=SimpleNamespace(
            url="https://billing.stripe.com/test",
        )) as create:
            response = self.post("/api/payments/billing-portal")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(create.call_args.kwargs["return_url"],
                             "https://rootcall.example/static/client-portal.html")
            self.db.delete(self.state)
            self.user.stripe_customer_id = "cus-legacy"
            self.db.commit()
            response = self.post("/api/payments/billing-portal")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(create.call_args.kwargs["customer"], "cus-legacy")

    def test_cannot_checkout_for_another_account(self):
        response = self.post("/api/payments/create-checkout", {"tier": "essential", "user_id": 2})
        self.assertEqual(response.status_code, 403)

    def test_only_single_line_plan_can_start_new_checkout(self):
        with patch.object(stripe.checkout.Session, "create") as create:
            for tier in ("family", "guardian", "unknown"):
                with self.subTest(tier=tier):
                    response = self.post("/api/payments/create-checkout", {"tier": tier})
                    self.assertEqual(response.status_code, 422, response.text)
            create.assert_not_called()

    def test_checkout_uses_configured_origin_and_stable_idempotency(self):
        self.state.tier = None
        self.db.commit()
        with patch.object(stripe.checkout.Session, "create", return_value=SimpleNamespace(
            id="cs-created", url="https://checkout.stripe.com/test",
        )) as create:
            response = self.client.post("/api/payments/create-checkout", headers={
                **self.headers, "Origin": "https://attacker.example",
            }, json={"tier": "essential"})
        self.assertEqual(response.status_code, 200, response.text)
        args = create.call_args.kwargs
        self.assertEqual(args["success_url"], "https://rootcall.example/static/onboarding.html?session_id={CHECKOUT_SESSION_ID}")
        self.assertEqual(args["metadata"]["user_id"], "1")
        self.assertEqual(args["idempotency_key"], f"rootcall-checkout-{self.state.checkout_key}")
        self.db.expire_all()
        self.assertEqual(self.state.checkout_session_id, "cs-created")

    def test_open_checkout_reuses_existing_session(self):
        self.state.checkout_session_id = "cs-test"
        self.db.commit()
        self.checkout.return_value = stripe.StripeObject.construct_from({
            "id": "cs-test", "url": "https://checkout.stripe.com/test", "status": "open",
        }, "test-key")
        with patch.object(stripe.checkout.Session, "create") as create:
            response = self.post("/api/payments/create-checkout", {"tier": "essential"})
        self.assertEqual(response.status_code, 200, response.text)
        create.assert_not_called()

    def test_expired_checkout_rotates_key_and_clears_old_session_before_retry(self):
        old_key = self.state.checkout_key
        self.state.checkout_session_id = "cs-old"
        self.db.commit()
        self.checkout.return_value = {"status": "expired"}
        with patch.object(stripe.checkout.Session, "create", side_effect=stripe.APIConnectionError("timeout")):
            response = self.post("/api/payments/create-checkout", {"tier": "essential"})
        self.assertEqual(response.status_code, 502)
        self.db.expire_all()
        self.assertNotEqual(self.state.checkout_key, old_key)
        self.assertIsNone(self.state.checkout_session_id)

    def test_invalid_public_url_fails_before_checkout(self):
        with patch.object(settings, "APP_BASE_URL", "http://attacker.example"), \
                patch.object(stripe.checkout.Session, "create") as create:
            response = self.post("/api/payments/create-checkout", {"tier": "essential"})
        self.assertEqual(response.status_code, 503)
        create.assert_not_called()

    def test_verified_payment_records_subscription_and_is_repeatable(self):
        self.checkout.return_value = stripe.StripeObject.construct_from(self.checkout_data(), "test-key")
        self.subscription.return_value = stripe.StripeObject.construct_from(
            {"id": "sub-test", "customer": "cus-test", "status": "active"}, "test-key",
        )
        for _ in range(2):
            response = self.post("/api/payments/verify", {"session_id": "cs-test"})
            self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        self.assertEqual(self.state.payment_status, "active")
        self.assertEqual(self.state.stripe_subscription_id, "sub-test")
        self.assertEqual(self.user.stripe_customer_id, "cus-test")

    def test_verification_rejects_unpaid_forged_and_wrong_owner_sessions(self):
        cases = [
            (self.checkout_data(payment_status="unpaid"), 402),
            (self.checkout_data(status="open"), 402),
            (self.checkout_data(mode="payment"), 409),
            (self.checkout_data(metadata={"user_id": "2"}), 403),
            (self.checkout_data(metadata={}), 403),
        ]
        for data, expected in cases:
            with self.subTest(checkout=data):
                self.checkout.return_value = data
                response = self.post("/api/payments/verify", {"session_id": "cs-test"})
                self.assertEqual(response.status_code, expected, response.text)
        self.assertEqual(self.state.payment_status, "pending")

    def test_canceled_subscription_does_not_unlock_onboarding(self):
        self.subscription.return_value["status"] = "canceled"
        response = self.post("/api/payments/verify", {"session_id": "cs-test"})
        self.assertEqual(response.status_code, 402)
        self.assertEqual(self.state.payment_status, "inactive")

    def test_status_recovers_paid_checkout_without_return_page(self):
        self.state.checkout_session_id = "cs-test"
        self.db.commit()
        response = self.client.get("/api/onboarding/status", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "active")

    def test_setup_status_refreshes_billing_recovery_and_cancellation(self):
        self.paid()
        for stripe_status, expected in (("past_due", "inactive"), ("active", "active"),
                                        ("canceled", "inactive")):
            with self.subTest(stripe_status=stripe_status):
                self.subscription.return_value["status"] = stripe_status
                response = self.client.get("/api/onboarding/status", headers=self.headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["payment_status"], expected)
                self.assertTrue(response.json()["billing_available"])

    def test_unsigned_webhook_is_rejected(self):
        response = self.client.post("/api/payments/webhook", json={"type": "checkout.session.completed"})
        self.assertEqual(response.status_code, 400)

    def test_signed_webhooks_are_idempotent_and_use_current_subscription(self):
        event = stripe.StripeObject.construct_from(
            {"type": "checkout.session.completed", "data": {"object": self.checkout_data()}}, "test-key",
        )
        with patch.object(stripe.Webhook, "construct_event", return_value=event):
            for _ in range(2):
                self.assertEqual(self.client.post("/api/payments/webhook", content=b"test").status_code, 200)
        event = {"type": "customer.subscription.updated", "data": {"object": {
            "id": "sub-test", "status": "active",
        }}}
        self.subscription.return_value["status"] = "canceled"
        with patch.object(stripe.Webhook, "construct_event", return_value=event):
            self.assertEqual(self.client.post("/api/payments/webhook", content=b"old-event").status_code, 200)
        self.assertEqual(self.state.payment_status, "inactive")

    def test_unpaid_users_cannot_save_search_or_activate(self):
        for path, method, body in [
            ("/api/onboarding/profile", "put", self.profile()),
            ("/api/onboarding/numbers?area_code=202", "get", None),
            ("/api/onboarding/voices", "get", None),
            ("/api/onboarding/trusted-contacts", "put", {"phone_numbers": []}),
            ("/api/onboarding/complete", "post", None),
        ]:
            with self.subTest(path=path):
                kwargs = {"headers": self.headers}
                if body:
                    kwargs["json"] = body
                response = getattr(self.client, method)(path, **kwargs)
                self.assertEqual(response.status_code, 402, response.text)
        self.telnyx.order_number.assert_not_called()

    def test_optional_contacts_save_normalize_deduplicate_and_resume(self):
        self.ready()
        response = self.client.put("/api/onboarding/trusted-contacts", headers=self.headers,
                                   json={"phone_numbers": ["(202) 555-0145", "+12025550145", "+442079460123"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        self.assertEqual(self.state.trusted_contacts, ["+12025550145", "+442079460123"])
        status = self.client.get("/api/onboarding/status", headers=self.headers).json()
        self.assertTrue(status["contacts_completed"])
        self.assertEqual(status["trusted_contacts"], self.state.trusted_contacts)
        self.telnyx.order_number.assert_not_called()

    def test_optional_contacts_can_be_skipped_and_edited(self):
        self.paid()
        status = self.client.get("/api/onboarding/status", headers=self.headers).json()
        self.assertFalse(status["contacts_completed"])
        for contacts in ([], ["+12025550145"], []):
            response = self.client.put("/api/onboarding/trusted-contacts", headers=self.headers,
                                       json={"phone_numbers": contacts})
            self.assertEqual(response.status_code, 200, response.text)
            self.db.expire_all()
            status = self.client.get("/api/onboarding/status", headers=self.headers).json()
            self.assertTrue(status["contacts_completed"])
            self.assertEqual(status["trusted_contacts"], contacts)

    def test_optional_contacts_reject_invalid_oversized_and_shield_number(self):
        self.ready()
        for contacts in (["bad-number"], [self.state.shield_number], ["+12025550145"] * 101):
            with self.subTest(contacts=contacts):
                response = self.client.put("/api/onboarding/trusted-contacts", headers=self.headers,
                                           json={"phone_numbers": contacts})
                self.assertEqual(response.status_code, 422, response.text)
        self.assertIsNone(self.state.trusted_contacts)

    def test_optional_contacts_are_locked_after_ordering_and_isolated_by_account(self):
        self.ready()
        other = customer_onboarding.new_onboarding(2)
        other.trusted_contacts = ["+12025550147"]
        self.db.add(other)
        self.state.order_attempted = True
        self.db.commit()
        response = self.client.put("/api/onboarding/trusted-contacts", headers=self.headers,
                                   json={"phone_numbers": ["+12025550145"]})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(other.trusted_contacts, ["+12025550147"])

    def test_chosen_number_cannot_be_a_saved_trusted_contact(self):
        self.paid()
        self.state.trusted_contacts = ["+12025550100"]
        self.db.commit()
        response = self.client.put("/api/onboarding/number", headers=self.headers,
                                   json={"phone_number": "+12025550100"})
        self.assertEqual(response.status_code, 422, response.text)

    def test_profile_saves_separate_names_and_actual_forwarding(self):
        self.paid()
        response = self.client.put("/api/onboarding/profile", headers=self.headers, json=self.profile())
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        self.assertEqual(self.state.first_name, "Jordan")
        self.assertEqual(self.state.last_name, "Green")
        self.assertEqual(self.state.forwarding_number, "+12025550123")
        self.assertEqual(self.user.full_name, "Jordan Green")

    def test_profile_rejects_invalid_input_email_change_and_unknown_voice(self):
        self.paid()
        for changes in ({"first_name": " "}, {"forwarding_number": "123"},
                        {"email": "other@example.com"}, {"voice_id": "voice-xai"}):
            with self.subTest(changes=changes):
                response = self.client.put("/api/onboarding/profile", headers=self.headers,
                                           json=self.profile(**changes))
                self.assertEqual(response.status_code, 422, response.text)

    def test_voice_provider_failure_is_not_an_empty_success(self):
        self.paid()
        self.retell.list_voices.side_effect = requests.ConnectionError("offline")
        response = self.client.get("/api/onboarding/voices", headers=self.headers)
        self.assertEqual(response.status_code, 502)

    def test_number_choice_is_available_and_persists(self):
        self.paid()
        response = self.client.put("/api/onboarding/number", headers=self.headers,
                                   json={"phone_number": "+12025550100"})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        self.assertEqual(self.state.shield_number, "+12025550100")
        self.telnyx.order_number.assert_not_called()

    def test_area_code_without_inventory_offers_nearby_numbers_instead_of_failing(self):
        self.paid()

        def search(area_code=None, limit=10, best_effort=False):
            if best_effort and area_code == "754":
                return [{"phone_number": "+17865550142", "locality": "Miami"}]
            return []  # Telnyx "No numbers found" (10031) is an empty result, not an outage

        self.telnyx.search_available_numbers.side_effect = search
        found = self.client.get("/api/onboarding/numbers?area_code=754", headers=self.headers)
        self.assertEqual(found.status_code, 200, found.text)
        self.assertEqual(found.json(), {"numbers": [{"phone_number": "+17865550142", "locality": "Miami"}], "nearby": True})

        # A nearby number is only listed under the searched area code, so the choice must say which.
        rejected = self.client.put("/api/onboarding/number", headers=self.headers,
                                   json={"phone_number": "+17865550142"})
        self.assertEqual(rejected.status_code, 409)
        accepted = self.client.put("/api/onboarding/number", headers=self.headers,
                                   json={"phone_number": "+17865550142", "search_area_code": "754"})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.db.expire_all()
        self.assertEqual(self.state.shield_number, "+17865550142")
        self.telnyx.order_number.assert_not_called()

    def test_exact_matches_are_not_marked_nearby_and_nothing_found_is_empty(self):
        self.paid()
        self.telnyx.search_available_numbers.side_effect = None
        self.telnyx.search_available_numbers.return_value = [{"phone_number": "+12025550100"}]
        self.assertFalse(self.client.get("/api/onboarding/numbers?area_code=202", headers=self.headers).json()["nearby"])
        self.telnyx.search_available_numbers.return_value = []
        empty = self.client.get("/api/onboarding/numbers?area_code=754", headers=self.headers)
        self.assertEqual(empty.json(), {"numbers": [], "nearby": False})
        # The nearby lookup failing must not turn "none found" into an outage.
        self.telnyx.search_available_numbers.side_effect = lambda **kw: (
            (_ for _ in ()).throw(RuntimeError("best effort unsupported")) if kw.get("best_effort") else [])
        self.assertEqual(self.client.get("/api/onboarding/numbers?area_code=754", headers=self.headers).json()["numbers"], [])

    def test_telnyx_no_numbers_found_is_an_empty_result_not_an_error(self):
        from app.services.telnyx_service import TelnyxService

        body = '{"errors": [{"code": "10031", "title": "Invalid request filter", "detail": "No numbers found"}]}'
        service = TelnyxService(api_key="test-key")
        with patch("app.services.telnyx_service.requests.get") as get:
            get.return_value = SimpleNamespace(status_code=400, text=body)
            self.assertEqual(service.search_available_numbers(area_code="754"), [])
            service.search_available_numbers(area_code="754", best_effort=True)
            self.assertEqual(get.call_args.kwargs["params"]["filter[best_effort]"], "true")
            get.return_value = SimpleNamespace(status_code=400, text='{"errors": [{"code": "10015"}]}')
            with self.assertRaises(RuntimeError):
                service.search_available_numbers(area_code="754")
            get.return_value = SimpleNamespace(status_code=200, text="", json=lambda: {"data": [{"phone_number": "+17865550142"}]})
            self.assertEqual(service.search_available_numbers(area_code="786"), [{"phone_number": "+17865550142"}])

    def test_number_selection_rejects_loops_collisions_and_invalid_area(self):
        self.ready()
        self.assertEqual(self.client.get("/api/onboarding/numbers?area_code=abc", headers=self.headers).status_code, 422)
        self.assertEqual(self.client.put("/api/onboarding/number", headers=self.headers,
                                        json={"phone_number": "+12025550123"}).status_code, 422)
        other = customer_onboarding.new_onboarding(2)
        other.shield_number = "+12025550101"
        self.db.add(other)
        self.db.commit()
        self.telnyx.search_available_numbers.return_value = [{"phone_number": "+12025550101"}]
        response = self.client.put("/api/onboarding/number", headers=self.headers,
                                   json={"phone_number": "+12025550101"})
        self.assertEqual(response.status_code, 409)

    def test_successful_activation_wires_chosen_voice_and_forwarding_once(self):
        self.ready()
        self.state.trusted_contacts = ["+12025550145"]
        self.db.commit()
        self.telnyx.list_phone_numbers.side_effect = [[], [self.owned_number()]]
        response = self.activate()
        self.assertEqual(response.status_code, 200, response.text)
        self.retell.create_agent.assert_called_once_with(
            "RootCall-1", "llm-test", voice_id="voice-test", publish=False,
        )
        self.retell.configure_transfer_tool.assert_called_once_with(
            "agent-test", "+12025550123", custom_sip_headers={"X-Telnyx-Username": "testrootcall1"},
        )
        self.retell.configure_call_webhook.assert_called_once_with(
            "agent-test", "https://rootcall.example/retell/webhook",
        )
        self.retell.import_phone_number.assert_called_once_with(
            "+12025550100", "sip.telnyx.com", "testrootcall1", "testsippassword",
            inbound_agent_id="agent-test",
        )
        self.db.expire_all()
        config = self.db.query(RootCallConfig).one()
        self.assertEqual(config.client_cell, "+12025550123")
        self.assertEqual(config.voice_id, "voice-test")
        llm_call = self.retell.create_llm.call_args
        self.assertIn("Jordan Green", llm_call.args[0])
        self.assertIn("ROOTCALL ORIGINAL HANDBOOK BEGIN", llm_call.args[0])
        self.assertEqual(llm_call.kwargs["begin_message"],
                         "Hello, you've reached RootCall AI Assistant. Who would you like to speak with?")
        self.assertEqual(config.trusted_contacts, ["+12025550145"])
        self.assertTrue(config.trusted_routing_enabled)
        self.assertEqual(config.trusted_agent_id, "agent-trusted")
        self.retell.configure_inbound_webhook.assert_called_once_with(
            "+12025550100", "https://rootcall.example/retell/rootcall-inbound",
        )
        contacts = self.client.get("/api/rootcall/config/1", headers=self.headers).json()["trusted_contacts"]
        self.assertEqual([contact["phone_number"] for contact in contacts], ["+12025550145"])
        inbound = json.dumps({"event": "call_inbound", "call_inbound": {
            "from_number": "+12025550145", "to_number": "+12025550100",
        }})
        with patch.object(settings, "RETELL_API_KEY", "inbound-test-key"):
            routed = self.client.post("/retell/rootcall-inbound", content=inbound, headers={
                "x-retell-signature": symmetric["sign"](inbound, "inbound-test-key"),
            })
        self.assertEqual(routed.status_code, 200, routed.text)
        self.assertEqual(routed.json()["call_inbound"]["override_agent_id"], "agent-trusted")
        self.assertEqual(routed.json()["call_inbound"]["dynamic_variables"],
                         {"rootcall_forwarding": "+12025550123"})
        self.assertFalse(config.sms_alerts_enabled)
        self.assertEqual(self.state.status, "completed")
        self.assertEqual(self.activate().status_code, 200)
        self.telnyx.order_number.assert_called_once()

    def test_confirmed_activation_is_durable_idempotent_and_locks_edits(self):
        self.ready()
        for _ in range(2):
            response = self.post("/api/onboarding/complete")
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()["job"]["status"], "queued")
        compatible = self.post("/api/rootcall/provision", {})
        self.assertEqual(compatible.status_code, 202, compatible.text)
        self.assertEqual(compatible.json()["job"]["status"], "queued")
        self.assertEqual(self.db.query(ActivationJob).count(), 1)
        self.telnyx.order_number.assert_not_called()
        response = self.client.put("/api/onboarding/profile", headers=self.headers, json=self.profile())
        self.assertEqual(response.status_code, 409)
        self.subscription.reset_mock()
        status = self.client.get("/api/onboarding/status", headers=self.headers).json()
        self.assertEqual(status["activation_job"]["status"], "queued")
        self.subscription.assert_not_called()
        self.telnyx.list_phone_numbers.side_effect = [[], [self.owned_number()]]
        # A fresh worker session runs independently of the requesting browser.
        self.assertEqual(activation_jobs.run_once(sessionmaker(bind=self.engine)), 1)
        self.db.expire_all()
        self.assertEqual(self.state.status, "completed")
        self.assertEqual(self.db.get(ActivationJob, 1).status, "completed")
        self.assertEqual(activation_jobs.run_once(sessionmaker(bind=self.engine)), 0)
        self.assertEqual(self.post("/api/onboarding/complete").status_code, 202)
        self.telnyx.order_number.assert_called_once()

    def test_activation_needs_no_sip_or_outbound_profile_settings_and_names_the_trunk_like_before(self):
        # Yesterday's dashboard purchase used rootcall_<id> and a generated password with no extra settings.
        self.ready()
        self.telnyx.list_phone_numbers.side_effect = [[], [self.owned_number()]]
        with patch.object(settings, "TELNYX_SIP_USERNAME", ""), patch.object(settings, "TELNYX_SIP_PASSWORD", ""), \
                patch.object(settings, "TELNYX_OUTBOUND_VOICE_PROFILE_ID", ""):
            self.assertEqual(self.post("/api/onboarding/complete").status_code, 202)
            self.assertTrue(activation_jobs.process_job(self.db, 1))
            username, password = customer_onboarding.telnyx_sip_login(1)
            again = customer_onboarding.telnyx_sip_login(1)
            other_password = customer_onboarding.telnyx_sip_login(2)[1]
        self.assertEqual(username, "rootcall1")
        self.assertTrue(password.startswith("rc") and password.isalnum() and len(password) >= 20)
        self.assertEqual(again, (username, password))
        self.assertNotEqual(other_password, password)
        trunk = self.telnyx.get_or_create_retell_trunk.call_args
        self.assertEqual(trunk.args[:3], ("RootCall-Retell-1", "rootcall1", password))
        self.assertIsNone(trunk.kwargs["outbound_voice_profile_id"])
        self.telnyx.order_number.assert_called_once()
        self.retell.import_phone_number.assert_called_once()
        self.assertEqual(self.retell.import_phone_number.call_args.args[:4],
                         ("+12025550100", "sip.telnyx.com", "rootcall1", password))

    def test_explicit_sip_settings_still_win_when_configured(self):
        with patch.object(settings, "TELNYX_SIP_USERNAME", "custom"), patch.object(settings, "TELNYX_SIP_PASSWORD", "chosen"):
            self.assertEqual(customer_onboarding.sip_credentials(7), ("custom_7", "chosen"))

    def test_job_submission_checks_payment_and_profile_without_purchasing(self):
        self.paid()
        self.assertEqual(self.post("/api/onboarding/complete").status_code, 422)
        self.assertIsNone(self.db.get(ActivationJob, 1))
        self.telnyx.order_number.assert_not_called()

    def test_jobs_retry_pending_inventory_without_reordering(self):
        self.ready()
        self.telnyx.list_phone_numbers.return_value = []
        self.assertEqual(self.post("/api/onboarding/complete").status_code, 202)
        self.assertTrue(activation_jobs.process_job(self.db, 1))
        job = self.db.get(ActivationJob, 1)
        self.assertEqual(job.status, "retry")
        self.assertEqual(job.attempts, 1)
        self.assertGreater(job.available_at, datetime.utcnow())
        self.assertFalse(activation_jobs.process_job(self.db, 1))
        job.available_at = datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.assertTrue(activation_jobs.process_job(self.db, 1))
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.attempts, 2)
        self.telnyx.order_number.assert_called_once()

    def test_worker_retries_safe_provider_update_using_saved_agents(self):
        self.ready()
        self.telnyx.list_phone_numbers.side_effect = [[], [self.owned_number()], [self.owned_number()]]
        self.retell.configure_inbound_webhook.side_effect = requests.Timeout("lost update response")
        self.post("/api/onboarding/complete")
        activation_jobs.process_job(self.db, 1)
        job = self.db.get(ActivationJob, 1)
        self.assertEqual(job.status, "retry")
        self.assertIsNone(self.state.uncertain_operation)
        self.assertEqual(self.state.agent_id, "agent-test")
        self.retell.configure_inbound_webhook.side_effect = None
        job.available_at = datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()
        activation_jobs.process_job(self.db, 1)
        self.assertEqual(job.status, "completed")
        self.retell.create_agent.assert_called_once()
        self.retell.create_trusted_transfer_flow.assert_called_once()
        self.retell.create_trusted_transfer_agent.assert_called_once()
        self.telnyx.order_number.assert_called_once()

    def test_worker_shutdown_does_not_start_another_saved_job(self):
        from threading import Event
        self.ready()
        self.post("/api/onboarding/complete")
        stopping = Event()
        stopping.set()
        self.assertEqual(activation_jobs.run_once(sessionmaker(bind=self.engine), stopping), 0)
        self.telnyx.order_number.assert_not_called()
        self.assertEqual(self.db.get(ActivationJob, 1).status, "queued")

    def test_job_uncertain_creation_pauses_and_rejects_customer_retry(self):
        self.ready()
        self.state.order_attempted = True
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.retell.create_agent.side_effect = requests.Timeout("lost create response")
        self.post("/api/onboarding/complete")
        self.assertTrue(activation_jobs.process_job(self.db, 1))
        job = self.db.get(ActivationJob, 1)
        self.assertEqual(job.status, "paused")
        self.assertEqual(self.state.uncertain_operation, "screening_agent")
        self.assertFalse(activation_jobs.process_job(self.db, 1))
        self.assertEqual(self.post("/api/onboarding/complete").status_code, 409)
        self.retell.create_agent.assert_called_once()
        self.telnyx.order_number.assert_not_called()
        self.assertTrue(self.client.get("/api/onboarding/status", headers=self.headers).json()["support_review_required"])

    def test_job_retry_budget_stops_even_pending_orders(self):
        self.ready()
        self.telnyx.list_phone_numbers.return_value = []
        self.post("/api/onboarding/complete")
        job = self.db.get(ActivationJob, 1)
        for _ in range(activation_jobs.MAX_ATTEMPTS):
            job.available_at = datetime.utcnow() - timedelta(seconds=1)
            self.db.commit()
            self.assertTrue(activation_jobs.process_job(self.db, 1))
        self.assertEqual(job.status, "paused")
        self.assertFalse(activation_jobs.process_job(self.db, 1))
        self.telnyx.order_number.assert_called_once()
        self.assertEqual(self.post("/api/onboarding/complete").status_code, 409)

    def test_worker_reclaims_crash_without_duplicating_unknown_creation(self):
        self.ready()
        self.state.order_attempted = True
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.retell.create_agent.side_effect = KeyboardInterrupt("simulate process exit")
        self.post("/api/onboarding/complete")
        with self.assertRaises(KeyboardInterrupt):
            activation_jobs.process_job(self.db, 1)
        job = self.db.get(ActivationJob, 1)
        self.assertEqual(job.status, "running")
        self.assertEqual(self.state.uncertain_operation, "screening_agent")
        self.assertFalse(activation_jobs.process_job(self.db, 1))
        job.updated_at = datetime.utcnow() - timedelta(minutes=6)
        self.db.commit()
        self.assertTrue(activation_jobs.process_job(self.db, 1))
        self.assertEqual(job.status, "paused")
        self.retell.create_agent.assert_called_once()

    def test_stale_worker_restarts_safe_checkpoints_but_never_takes_live_lock(self):
        from app.services.activation_recovery import activation_lock
        self.ready()
        self.state.order_attempted = True
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.post("/api/onboarding/complete")
        job = self.db.get(ActivationJob, 1)
        self.state.status = "provisioning"
        job.status = "running"
        job.updated_at = datetime.utcnow() - timedelta(minutes=6)
        self.db.commit()
        with activation_lock(self.db, 1):
            self.assertFalse(activation_jobs.process_job(self.db, 1))
        self.assertTrue(activation_jobs.process_job(self.db, 1))
        self.assertEqual(job.status, "completed")
        self.telnyx.order_number.assert_not_called()

    def test_review_automatically_requeues_previously_confirmed_job(self):
        from app.services.activation_recovery import reopen_activation
        self.ready()
        self.state.order_attempted = True
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.post("/api/onboarding/complete")
        self.retell.create_agent.side_effect = requests.Timeout()
        activation_jobs.process_job(self.db, 1)
        self.retell.create_agent.side_effect = None
        reopen_activation(self.db, self.state, 2, "Confirmed no unmatched agent remains", True)
        self.assertEqual(self.db.get(ActivationJob, 1).status, "queued")
        self.assertTrue(self.state.order_attempted)
        activation_jobs.process_job(self.db, 1)
        self.assertEqual(self.state.status, "completed")
        self.telnyx.order_number.assert_not_called()

    def test_inactive_accounts_and_expired_payment_do_not_provision(self):
        self.ready()
        self.post("/api/onboarding/complete")
        self.user.is_active = False
        self.db.commit()
        activation_jobs.process_job(self.db, 1)
        self.assertEqual(self.db.get(ActivationJob, 1).status, "paused")
        self.telnyx.order_number.assert_not_called()
        self.user.is_active = True
        job = self.db.get(ActivationJob, 1)
        job.status = "queued"
        self.db.commit()
        self.subscription.return_value["status"] = "canceled"
        activation_jobs.process_job(self.db, 1)
        self.assertEqual(job.status, "paused")
        self.telnyx.order_number.assert_not_called()

    def test_service_setup_persists_reported_checks_and_invalidates_changed_destination(self):
        self.ready()
        self.telnyx.list_phone_numbers.side_effect = [[], [self.owned_number()]]
        self.assertEqual(self.activate().status_code, 200)
        initial = self.client.get("/api/onboarding/service-setup", headers=self.headers)
        self.assertEqual(initial.status_code, 200, initial.text)
        self.assertTrue(initial.json()["self_reported"])
        self.assertTrue(self.client.get("/api/rootcall/config/1", headers=self.headers).json()["setup_guide_available"])
        checks = {
            "shield_number": self.state.shield_number, "forwarding_number": self.state.forwarding_number,
            "mode": "carrier", "screening_tested": True, "audio_tested": True,
            "trusted_tested": False, "carrier_forwarding_confirmed": True,
        }
        saved = self.client.put("/api/onboarding/service-setup", headers=self.headers, json=checks)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertTrue(saved.json()["checks"]["screening_tested"])
        invalid = self.client.put("/api/onboarding/service-setup", headers=self.headers,
                                  json={**checks, "mode": "unsupported"})
        self.assertEqual(invalid.status_code, 422)
        self.db.expire_all()
        self.assertTrue(self.client.get("/api/onboarding/service-setup", headers=self.headers).json()["checks"]["audio_tested"])
        config = self.db.query(RootCallConfig).one()
        config.client_cell = "+12025550199"
        self.db.commit()
        changed = self.client.get("/api/onboarding/service-setup", headers=self.headers).json()
        self.assertFalse(changed["checks"]["screening_tested"])
        self.assertEqual(changed["checks"]["mode"], "direct")
        self.assertEqual(self.client.put("/api/onboarding/service-setup", headers=self.headers, json=checks).status_code, 409)

    def test_service_setup_and_jobs_are_owner_scoped_and_require_authentication(self):
        self.ready()
        self.post("/api/onboarding/complete")
        for path in ("/api/onboarding/service-setup", "/api/onboarding/status"):
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.post("/api/onboarding/complete").status_code, 401)
        checks = {"shield_number": "+12025550100", "forwarding_number": "+12025550123", "mode": "direct"}
        self.assertEqual(self.client.put("/api/onboarding/service-setup", json=checks).status_code, 401)
        other_headers = {"Authorization": f"Bearer {auth.create_access_token({'sub': '2'})}"}
        self.assertEqual(self.client.get("/api/onboarding/service-setup", headers=other_headers).status_code, 409)
        self.assertEqual(self.client.post("/api/onboarding/complete", headers=other_headers).status_code, 402)
        self.assertEqual(self.db.query(ActivationJob).count(), 1)
        self.telnyx.order_number.assert_not_called()

    def test_pending_order_retry_does_not_purchase_twice_and_can_finish(self):
        self.ready()
        self.telnyx.list_phone_numbers.return_value = []
        first = self.activate()
        self.assertEqual(first.status_code, 409, first.text)
        self.assertTrue(self.state.order_attempted)
        self.assertEqual(self.state.status, "error")
        self.assertEqual(self.activate().status_code, 409)
        self.telnyx.order_number.assert_called_once()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        final = self.activate()
        self.assertEqual(final.status_code, 200, final.text)
        self.telnyx.order_number.assert_called_once()

    def test_onboarding_cannot_complete_until_trusted_inbound_webhook_is_connected(self):
        self.ready()
        self.telnyx.list_phone_numbers.side_effect = [[], [self.owned_number()], [self.owned_number()]]
        self.retell.configure_inbound_webhook.side_effect = requests.Timeout("lost response")
        response = self.activate()
        self.assertEqual(response.status_code, 502, response.text)
        self.db.expire_all()
        self.assertEqual(self.state.status, "error")
        self.assertFalse(self.db.query(RootCallConfig).one().trusted_routing_enabled)
        self.retell.configure_inbound_webhook.side_effect = None
        response = self.activate()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(self.db.query(RootCallConfig).one().trusted_routing_enabled)
        self.retell.create_trusted_transfer_flow.assert_called_once()
        self.retell.create_trusted_transfer_agent.assert_called_once()
        self.telnyx.order_number.assert_called_once()

    def test_provider_failure_resumes_checkpoints_without_recreating_agent(self):
        self.ready()
        self.state.order_attempted = True
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.retell.import_phone_number.side_effect = requests.Timeout("lost response")
        first = self.activate()
        self.assertEqual(first.status_code, 502)
        self.assertNotEqual(self.state.status, "completed")
        self.assertEqual(self.state.agent_id, "agent-test")
        self.retell.import_phone_number.side_effect = None
        self.retell.list_phone_numbers.return_value = [{
            "phone_number": "+12025550100", "inbound_agents": [{"agent_id": "agent-test", "weight": 1}],
        }]
        second = self.activate()
        self.assertEqual(second.status_code, 200, second.text)
        self.retell.create_agent.assert_called_once()
        self.retell.import_phone_number.assert_called_once()
        self.telnyx.order_number.assert_not_called()

    def test_lost_agent_creation_requires_review_instead_of_duplicate_creation(self):
        self.ready()
        self.state.order_attempted = True
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.retell.create_agent.side_effect = requests.Timeout("lost create response")
        response = self.activate()
        self.assertEqual(response.status_code, 502)
        self.db.expire_all()
        self.assertEqual(self.state.uncertain_operation, "screening_agent")
        self.assertEqual(self.state.llm_id, "llm-test")
        self.assertEqual(self.activate().status_code, 409)
        self.retell.create_agent.assert_called_once()
        self.retell.create_llm.assert_called_once()
        self.telnyx.order_number.assert_not_called()
        data = self.client.get("/api/onboarding/status", headers=self.headers).json()
        self.assertTrue(data["support_review_required"])
        self.assertEqual(data["activation_stage"], "creating your screening assistant")
        self.assertEqual(self.post("/api/rootcall/trusted-routing/1").status_code, 409)

    def test_lost_trusted_flow_creation_needs_review_and_never_rebuys_number(self):
        self.ready()
        self.state.order_attempted = True
        self.db.commit()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        self.retell.create_trusted_transfer_flow.side_effect = requests.Timeout("lost flow response")
        first = self.activate()
        self.assertEqual(first.status_code, 502)
        self.db.expire_all()
        self.assertEqual(self.state.uncertain_operation, "trusted_flow")
        self.assertEqual(self.state.agent_id, "agent-test")
        self.assertEqual(self.activate().status_code, 409)
        self.retell.create_trusted_transfer_flow.assert_called_once()
        self.telnyx.order_number.assert_not_called()

    def test_reviewed_stale_setup_resumes_without_buying_number_or_recreating_saved_resources(self):
        from app.services.activation_recovery import activation_lock, reopen_activation
        from datetime import datetime, timedelta
        self.ready()
        self.state.status = "provisioning"
        self.state.activation_updated_at = datetime.utcnow() - timedelta(hours=1)
        self.state.order_attempted = True
        self.state.connection_id = "connection-test"
        self.state.llm_id = "llm-test"
        self.state.agent_id = "agent-test"
        self.db.commit()
        with activation_lock(self.db, 1):
            reopen_activation(self.db, self.state, 2, "Verified all resources in provider consoles", True)
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        response = self.activate()
        self.assertEqual(response.status_code, 200, response.text)
        self.telnyx.order_number.assert_not_called()
        self.retell.create_agent.assert_not_called()
        self.retell.create_llm.assert_not_called()
        self.assertEqual(self.state.status, "completed")

    def test_in_progress_or_started_order_cannot_be_edited_or_activated_twice(self):
        self.ready()
        self.state.status = "provisioning"
        self.db.commit()
        self.assertEqual(self.activate().status_code, 409)
        self.telnyx.order_number.assert_not_called()
        self.state.status = "error"
        self.state.order_attempted = True
        self.db.commit()
        response = self.client.put("/api/onboarding/profile", headers=self.headers, json=self.profile())
        self.assertEqual(response.status_code, 409)

    def test_foreign_number_is_not_rebound(self):
        self.ready()
        self.telnyx.list_phone_numbers.return_value = [self.owned_number()]
        response = self.activate()
        self.assertEqual(response.status_code, 409)
        self.telnyx.assign_number_to_connection.assert_not_called()
        self.telnyx.order_number.assert_not_called()

    def test_legacy_provision_and_import_cannot_bypass_paid_setup(self):
        response = self.post("/api/rootcall/provision", {})
        self.assertEqual(response.status_code, 402, response.text)
        response = self.post("/api/rootcall/import-existing/+12025550100")
        self.assertEqual(response.status_code, 409, response.text)
        self.telnyx.order_number.assert_not_called()


class ProvisioningContractTest(unittest.TestCase):
    def test_fqdn_trunk_configures_actual_outbound_authentication(self):
        service = TelnyxService(api_key="test-key")
        with patch.object(service, "_get", side_effect=[{"data": []}, {"data": []}]), \
                patch.object(service, "ensure_outbound_voice_profile") as ensure, \
                patch.object(service, "_post", side_effect=[{"data": {"id": "connection"}}, {}]) as post:
            service.get_or_create_retell_trunk("customer", "sip-user", "sip-pass", "voice-profile")
        payload = post.call_args_list[0].kwargs["json"]
        self.assertEqual(payload["user_name"], "sip-user")
        self.assertEqual(payload["password"], "sip-pass")
        self.assertEqual(payload["outbound"]["ip_authentication_method"], "credential-authentication")
        self.assertEqual(payload["outbound"]["outbound_voice_profile_id"], "voice-profile")
        self.assertEqual(post.call_args_list[1].kwargs["json"]["fqdn"], "sip.retellai.com")
        ensure.assert_called_once_with("connection", profile_id="voice-profile")

    def test_number_assignment_requires_an_exact_match(self):
        service = TelnyxService(api_key="test-key")
        with patch.object(service, "list_phone_numbers", return_value=[
            {"id": "wrong", "phone_number": "+12025550101"},
            {"id": "right", "phone_number": "+12025550100"},
        ]), patch.object(service, "_patch", return_value={}) as update:
            service.assign_number_to_connection("+12025550100", "connection")
        self.assertEqual(update.call_args.args[0], "/phone_numbers/right")

    def test_transfer_update_preserves_sip_authentication_header(self):
        service = RetellService(api_key="test-key")
        with patch.object(service, "_get", side_effect=[
            {"response_engine": {"type": "retell-llm", "llm_id": "llm"}},
            {"general_tools": [{"name": "transfer_call", "type": "transfer_call",
                                "custom_sip_headers": {"X-Telnyx-Username": "sip-user"}}]},
        ]), patch.object(service, "_patch", return_value={}) as update, \
                patch.object(service, "publish_agent"):
            service.configure_transfer_tool("agent", "+12025550123")
        tool = next(item for item in update.call_args.args[1]["general_tools"] if item["type"] == "transfer_call")
        self.assertEqual(tool["custom_sip_headers"], {"X-Telnyx-Username": "sip-user"})

    def test_onboarding_migration_round_trip_matches_model(self):
        path = Path(__file__).parents[1] / "alembic/versions/a813bc21e902_add_customer_onboarding.py"
        spec = importlib.util.spec_from_file_location("onboarding_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        recovery_path = path.with_name("c032ef54d218_billing_and_activation_recovery.py")
        recovery_spec = importlib.util.spec_from_file_location("recovery_migration", recovery_path)
        recovery = importlib.util.module_from_spec(recovery_spec)
        recovery_spec.loader.exec_module(recovery)
        jobs_path = path.with_name("d143fa65e329_automated_activation.py")
        jobs_spec = importlib.util.spec_from_file_location("jobs_migration", jobs_path)
        jobs = importlib.util.module_from_spec(jobs_spec)
        jobs_spec.loader.exec_module(jobs)
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                User.__table__.create(connection)
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                    connection.execute(User.__table__.insert().values(
                        id=1, email="migration@example.com", hashed_password="unused",
                    ))
                    connection.execute(text(
                        "INSERT INTO customer_onboarding "
                        "(user_id, checkout_key, payment_status, status, order_attempted, "
                        "transfer_ready, number_imported, created_at, updated_at) VALUES "
                        "(1, 'saved-checkout-key', 'active', 'provisioning', 1, 0, 0, "
                        "'2026-01-01 00:00:00', '2026-01-02 00:00:00')"
                    ))
                    recovery.upgrade()
                    jobs.upgrade()
                    columns = inspect(connection).get_columns("customer_onboarding")
                    self.assertEqual({column["name"] for column in columns},
                                     set(CustomerOnboarding.__table__.columns.keys()))
                    row = connection.execute(text(
                        "SELECT checkout_key, order_attempted, cancel_at_period_end, "
                        "activation_updated_at FROM customer_onboarding WHERE user_id = 1"
                    )).one()
                    self.assertEqual(row.checkout_key, "saved-checkout-key")
                    self.assertTrue(row.order_attempted)
                    self.assertFalse(row.cancel_at_period_end)
                    self.assertIsNotNone(row.activation_updated_at)
                    from app.models.activation_job import ActivationJob
                    self.assertEqual(
                        {column["name"] for column in inspect(connection).get_columns("activation_jobs")},
                        set(ActivationJob.__table__.columns.keys()),
                    )
                    jobs.downgrade()
                    jobs.upgrade()
                    self.assertEqual(connection.execute(text(
                        "SELECT checkout_key FROM customer_onboarding WHERE user_id = 1"
                    )).scalar(), "saved-checkout-key")
                    jobs.downgrade()
                    recovery.downgrade()
                    migration.downgrade()
                    self.assertNotIn("customer_onboarding", inspect(connection).get_table_names())
        finally:
            engine.dispose()
