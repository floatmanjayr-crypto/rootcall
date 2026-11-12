"""The original customer flow must keep working by default:
sign up -> Stripe checkout -> success page -> sign in -> dashboard -> buy a number.
The automated onboarding is opt-in (AUTOMATED_ONBOARDING=true) and must not interfere."""
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")
os.environ.setdefault("TELNYX_API_KEY", "test-unused-key")
os.environ.setdefault("RETELL_API_KEY", "test-unused-key")

import stripe
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.models import User
from app.models.activation_job import ActivationJob
from app.models.onboarding import CustomerOnboarding
from app.models.phone_number import PhoneNumber
from app.routers import auth, onboarding, payments, rootcall_portal
from app.services import customer_onboarding


class ClassicFlowTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(settings, "JWT_SECRET_KEY", "test-only-classic-signing-key"))
        self.stack.enter_context(patch.object(settings, "AUTOMATED_ONBOARDING", False))
        self.stack.enter_context(patch.object(settings, "APP_BASE_URL", "https://rootcall.example"))
        self.stack.enter_context(patch.object(stripe, "api_key", "sk_test_fake"))
        self.stack.enter_context(patch.dict(payments.PRICE_MAP, {
            "essential": "price_e", "family": "price_f", "guardian": "price_g"}))
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.db.close)
        app = FastAPI()
        for router in (auth.router, payments.router, onboarding.router, rootcall_portal.router):
            app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.session = self.stack.enter_context(patch.object(stripe.checkout.Session, "create"))
        self.session.return_value = SimpleNamespace(id="cs_1", url="https://checkout.stripe.test/cs_1")
        self.telnyx, self.retell = Mock(), Mock()
        self.telnyx.list_phone_numbers.return_value = []
        self.telnyx.order_number.return_value = {"data": {"id": "order-1"}}
        self.telnyx.get_or_create_retell_trunk.return_value = ({"id": "conn-1"}, "u", "p")
        self.retell.create_llm.return_value = "llm-1"
        self.retell.create_agent.return_value = "agent-1"
        self.retell.list_phone_numbers.return_value = []
        for module in (rootcall_portal,):
            self.stack.enter_context(patch.object(module, "TelnyxService", return_value=self.telnyx))
            self.stack.enter_context(patch.object(module, "RetellService", return_value=self.retell))

    def signup(self, email="owner@example.com"):
        response = self.client.post("/api/auth/signup", json={
            "full_name": "Jordan Green", "email": email, "password": "valid-password"})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        return data, {"Authorization": f"Bearer {data['access_token']}"}

    def test_signup_does_not_start_the_automated_onboarding(self):
        data, _ = self.signup()
        self.assertEqual(data["next_url"], "/static/client-portal.html")
        self.assertIsNone(self.db.get(CustomerOnboarding, data["user"]["id"]))

    def test_login_goes_to_the_dashboard_even_for_a_stuck_onboarding_record(self):
        data, _ = self.signup()
        self.db.add(customer_onboarding.new_onboarding(data["user"]["id"]))
        self.db.commit()
        login = self.client.post("/api/auth/login", data={"username": "owner@example.com", "password": "valid-password"})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.json()["next_url"], "/static/client-portal.html")

    def test_checkout_matches_the_original_contract_for_every_plan(self):
        data, headers = self.signup()
        for tier, price in (("essential", "price_e"), ("family", "price_f"), ("guardian", "price_g")):
            response = self.client.post("/api/payments/create-checkout", headers={**headers, "Origin": "https://rootcall.onrender.com"},
                                        json={"tier": tier, "user_id": data["user"]["id"]})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {"checkout_url": "https://checkout.stripe.test/cs_1", "session_id": "cs_1"})
            kwargs = self.session.call_args.kwargs
            self.assertEqual(kwargs["line_items"], [{"price": price, "quantity": 1}])
            self.assertEqual(kwargs["mode"], "subscription")
            self.assertEqual(kwargs["customer_email"], "owner@example.com")
            self.assertEqual(kwargs["metadata"], {"user_id": str(data["user"]["id"]), "tier": tier})
            self.assertEqual(kwargs["success_url"],
                             "https://rootcall.onrender.com/static/success.html?session_id={CHECKOUT_SESSION_ID}")
            self.assertEqual(kwargs["cancel_url"], "https://rootcall.onrender.com/")
        # Checkout never creates onboarding state.
        self.assertIsNone(self.db.get(CustomerOnboarding, data["user"]["id"]))

    def test_checkout_without_an_origin_header_uses_the_configured_public_url_not_a_dead_domain(self):
        data, headers = self.signup()
        self.client.post("/api/payments/create-checkout", headers=headers, json={"tier": "essential"})
        self.assertTrue(self.session.call_args.kwargs["success_url"].startswith("https://rootcall.example/static/success.html"))

    def test_checkout_rejects_unknown_plans_and_other_accounts_and_reports_stripe_outages(self):
        data, headers = self.signup()
        self.assertEqual(self.client.post("/api/payments/create-checkout", headers=headers, json={"tier": "gold"}).status_code, 400)
        self.assertEqual(self.client.post("/api/payments/create-checkout", headers=headers,
                                          json={"tier": "essential", "user_id": data["user"]["id"] + 1}).status_code, 403)
        self.assertEqual(self.client.post("/api/payments/create-checkout", json={"tier": "essential"}).status_code, 401)
        self.session.side_effect = stripe.APIConnectionError("offline")
        outage = self.client.post("/api/payments/create-checkout", headers=headers, json={"tier": "essential"})
        self.assertEqual(outage.status_code, 502)
        self.assertIn("retry", outage.json()["detail"].lower())

    def test_buying_a_number_from_the_dashboard_works_even_with_a_stale_onboarding_record(self):
        data, headers = self.signup()
        user_id = data["user"]["id"]
        # An account that began the automated setup earlier must not be locked out of the original purchase.
        stale = customer_onboarding.new_onboarding(user_id)
        stale.status = "error"
        self.db.add(stale)
        self.db.add(ActivationJob(user_id=user_id, status="retry", attempts=1,
                                  available_at=__import__("datetime").datetime.utcnow(),
                                  updated_at=__import__("datetime").datetime.utcnow()))
        self.db.commit()
        self.telnyx.search_available_numbers.return_value = [{"phone_number": "+12025550100", "locality": "Washington"}]
        found = self.client.get("/api/rootcall/available-numbers?area_code=202", headers=headers)
        self.assertEqual(found.status_code, 200, found.text)
        bought = self.client.post("/api/rootcall/provision", headers=headers,
                                  json={"phone_number": "+12025550100", "area_code": "202"})
        self.assertEqual(bought.status_code, 200, bought.text)
        self.telnyx.order_number.assert_called_once_with("+12025550100")
        owned = self.db.query(PhoneNumber).filter(PhoneNumber.user_id == user_id).all()
        self.assertEqual([item.phone_number for item in owned], ["+12025550100"])

    def test_success_page_is_the_original_page_and_the_shortcut_points_to_it(self):
        from app.services import telnyx_service

        # The provider key is read when the module is first imported, which other tests may do without one.
        with patch.object(telnyx_service, "TLX_API_KEY", "test-unused-key"):
            from app.main import app as main_app

        client = TestClient(main_app)
        redirect = client.get("/success.html?session_id=cs_9", follow_redirects=False)
        self.assertEqual(redirect.headers["location"], "/static/success.html?session_id=cs_9")
        with patch.object(settings, "AUTOMATED_ONBOARDING", True):
            self.assertEqual(client.get("/success.html", follow_redirects=False).headers["location"], "/static/onboarding.html")
        page = client.get("/static/success.html")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Welcome to RootCall", page.text)
        self.assertNotIn("onboarding.html", page.text)

    def test_checkout_webhook_remembers_the_stripe_customer_for_billing(self):
        data, _ = self.signup()
        event = {"type": "checkout.session.completed", "data": {"object": {
            "id": "cs_1", "customer": "cus_77", "payment_status": "paid",
            "metadata": {"user_id": str(data["user"]["id"]), "tier": "essential"}}}}
        with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test"), \
                patch.object(stripe.Webhook, "construct_event", return_value=event):
            response = self.client.post("/api/payments/webhook", content=b"{}", headers={"stripe-signature": "x"})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        self.assertEqual(self.db.get(User, data["user"]["id"]).stripe_customer_id, "cus_77")


if __name__ == "__main__":
    unittest.main()
