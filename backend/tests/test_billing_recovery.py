import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

import stripe
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.core.deps import get_current_active_user, require_operator
from app.models import PhoneNumber, User
from app.models.onboarding import CustomerOnboarding
from app.models.activation_job import ActivationJob
from app.models.rootcall_config import RootCallConfig
from app.routers import admin, payments
from app.services import payment_verification
from app.services.activation_recovery import activation_lock, resource_creation
from app.services.customer_onboarding import new_onboarding


class BillingRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.db.close)
        self.db.add_all([
            User(id=1, email="owner@example.com", hashed_password="unused", is_active=True),
            User(id=2, email="admin@example.com", hashed_password="unused", is_active=True, is_superuser=True),
            User(id=3, email="legacy@example.com", hashed_password="unused", is_active=True),
            PhoneNumber(user_id=1, phone_number="+12025550100", is_active=True),
        ])
        self.state = new_onboarding(1)
        self.state.status = "completed"
        self.state.stripe_customer_id = "cus-test"
        self.state.stripe_subscription_id = "sub-test"
        self.state.payment_status = "active"
        self.db.add(self.state)
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(payments.router)
        self.app.include_router(admin.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_active_user] = lambda: self.db.get(User, 1)
        self.app.dependency_overrides[require_operator] = lambda: self.db.get(User, 2)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        retrieve = patch.object(stripe.Subscription, "retrieve", return_value={
            "id": "sub-test", "customer": "cus-test", "status": "active",
            "current_period_end": 1800000000, "cancel_at_period_end": False,
        })
        self.subscription = retrieve.start()
        self.addCleanup(retrieve.stop)

    def status(self):
        return self.client.get("/api/payments/status")

    def review(self, **body):
        return self.client.post("/api/admin/customers/1/reopen-activation", json={
            "provider_reconciled": True,
            "note": "Checked Telnyx order and Retell resources; saved checkpoints match, no unmatched resources.",
            **body,
        })

    def stale(self):
        self.state.status = "provisioning"
        self.state.activation_stage = "configuring call forwarding"
        self.state.activation_updated_at = datetime.utcnow() - timedelta(hours=1)
        self.state.order_attempted = True
        self.state.connection_id = "connection-saved"
        self.state.llm_id = "llm-saved"
        self.state.agent_id = "agent-saved"
        self.state.shield_number = "+12025550100"
        self.db.commit()

    def test_attention_includes_queued_jobs_and_review_resumes_confirmed_work(self):
        self.state.status = "draft"
        self.state.subscription_status = "active"
        self.db.add(ActivationJob(user_id=1))
        self.db.commit()
        attention = self.client.get("/api/admin/attention").json()
        self.assertEqual(attention["total"], 1)
        self.assertEqual(attention["items"][0]["activation_job"]["status"], "queued")
        self.assertFalse(attention["items"][0]["can_review_recovery"])
        self.subscription.assert_not_called()
        self.stale()
        self.state.uncertain_operation = "screening_agent"
        job = self.db.get(ActivationJob, 1)
        job.status = "paused"
        job.attempts = 6
        self.db.commit()
        response = self.review()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.attempts, 0)
        self.assertIsNone(self.state.uncertain_operation)
        self.assertTrue(self.state.order_attempted)
        self.assertEqual(self.state.agent_id, "agent-saved")
        self.subscription.assert_not_called()

    def test_customer_billing_reports_dates_and_scheduled_cancellation_without_restricting_service(self):
        self.subscription.return_value.update(cancel_at_period_end=True, cancel_at=1800000000)
        result = self.status()
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["service_policy"], "warnings_only")
        self.assertTrue(data["cancel_at_period_end"])
        self.assertTrue(data["current_period_end"].endswith("+00:00"))
        self.assertEqual(data["current_period_end"], data["cancel_at"])
        self.assertFalse(data["needs_attention"])
        self.assertTrue(self.db.query(PhoneNumber).one().is_active)
        self.assertEqual(self.state.status, "completed")

    def test_payment_issue_first_seen_is_stable_and_recovery_clears_it(self):
        self.subscription.return_value["status"] = "past_due"
        first = self.status().json()
        self.assertTrue(first["needs_attention"])
        self.assertEqual(first["payment_status"], "inactive")
        self.assertIsNotNone(first["payment_issue_since"])
        second = self.status().json()
        self.assertEqual(first["payment_issue_since"], second["payment_issue_since"])
        self.assertTrue(self.db.query(PhoneNumber).one().is_active)
        self.subscription.return_value["status"] = "active"
        data = self.status().json()
        self.assertFalse(data["needs_attention"])
        self.assertIsNone(data["payment_issue_since"])

    def test_actual_cancellation_records_provider_date_without_releasing_line(self):
        self.subscription.return_value.update(status="canceled", canceled_at=1800000000)
        data = self.status().json()
        self.assertEqual(data["canceled_at"], "2027-01-15T08:00:00+00:00")
        self.assertTrue(data["needs_attention"])
        self.assertTrue(self.db.query(PhoneNumber).one().is_active)

    def test_stripe_current_period_dates_support_subscription_item_schema(self):
        del self.subscription.return_value["current_period_end"]
        self.subscription.return_value["items"] = {"data": [
            {"current_period_end": 1800000000}, {"current_period_end": 1800000300},
        ]}
        data = self.status().json()
        self.assertEqual(data["current_period_end"], "2027-01-15T08:00:00+00:00")

    def test_legacy_and_unpaid_accounts_do_not_get_fabricated_subscription_status(self):
        self.app.dependency_overrides[get_current_active_user] = lambda: self.db.get(User, 3)
        data = self.status().json()
        self.assertFalse(data["managed"])
        self.assertIsNone(data["status"])
        self.subscription.assert_not_called()
        self.db.add(new_onboarding(3))
        self.db.commit()
        self.assertFalse(self.status().json()["managed"])

    def test_stripe_failure_and_wrong_customer_are_explicit_and_do_not_erase_snapshot(self):
        self.status()
        checked_at = self.state.billing_checked_at
        self.subscription.side_effect = stripe.APIConnectionError("test offline")
        self.assertEqual(self.status().status_code, 502)
        self.assertEqual(self.state.billing_checked_at, checked_at)
        self.assertEqual(self.state.subscription_status, "active")
        self.subscription.side_effect = None
        self.subscription.return_value["customer"] = "different-customer"
        self.assertEqual(self.status().status_code, 409)

    def test_invalid_provider_dates_and_unknown_status_fail_without_partial_snapshot(self):
        self.status()
        for update in ({"current_period_end": "invalid"}, {"current_period_end": 10**30},
                       {"status": "unrecognized"}):
            with self.subTest(update=update):
                original = self.subscription.return_value.copy()
                self.subscription.return_value.update(update)
                self.assertEqual(self.status().status_code, 502)
                self.assertEqual(self.state.subscription_status, "active")
                self.subscription.return_value = original

    def test_signed_webhook_reads_current_state_for_warnings_and_recovery(self):
        with patch.object(payments.settings, "STRIPE_WEBHOOK_SECRET", "test-webhook"), \
                patch.object(stripe.Webhook, "construct_event") as event:
            event.return_value = {"type": "invoice.payment_failed", "data": {"object": {
                "id": "invoice-test", "parent": {"subscription_details": {"subscription": "sub-test"}},
            }}}
            self.subscription.return_value["status"] = "past_due"
            for _ in range(2):
                self.assertEqual(self.client.post("/api/payments/webhook", content=b"signed-test").status_code, 200)
            first_seen = self.state.payment_issue_since
            self.assertIsNotNone(first_seen)
            self.assertEqual(self.state.subscription_status, "past_due")
            self.subscription.return_value["status"] = "active"
            self.client.post("/api/payments/webhook", content=b"out-of-order-test")
            self.assertEqual(self.state.subscription_status, "active")
            self.assertIsNone(self.state.payment_issue_since)
            self.assertTrue(self.db.query(PhoneNumber).one().is_active)

    def test_billing_routes_and_admin_attention_require_auth_and_role(self):
        self.app.dependency_overrides.pop(get_current_active_user)
        self.app.dependency_overrides.pop(require_operator)
        self.assertEqual(self.status().status_code, 401)
        self.assertEqual(self.client.get("/api/admin/attention").status_code, 401)
        self.assertEqual(self.review().status_code, 401)
        self.app.dependency_overrides[get_current_active_user] = lambda: self.db.get(User, 1)
        self.assertEqual(self.client.get("/api/admin/attention").status_code, 403)
        self.assertEqual(self.review().status_code, 403)

    def test_attention_queue_is_paginated_and_has_no_provider_side_effects(self):
        self.stale()
        self.db.add(RootCallConfig(
            user_id=1, phone_number_id=self.db.query(PhoneNumber).one().id,
            client_name="Owner", client_cell="+12025550102", retell_did="+12025550100",
            retell_agent_id="agent-saved", trusted_flow_id="flow-saved",
            trusted_agent_id="trusted-agent-saved",
        ))
        self.db.commit()
        data = self.client.get("/api/admin/attention?skip=0&limit=1").json()
        self.assertEqual(data["total"], 1)
        row = data["items"][0]
        self.assertTrue(row["can_review_recovery"])
        self.assertEqual(row["checkpoints"]["agent_id"], "agent-saved")
        self.assertEqual(row["checkpoints"]["trusted_flow_id"], "flow-saved")
        self.assertEqual(row["checkpoints"]["trusted_agent_id"], "trusted-agent-saved")
        self.subscription.assert_not_called()
        self.assertEqual(self.client.get("/api/admin/attention?skip=1&limit=1").json()["items"], [])
        self.assertEqual(self.client.get("/api/admin/attention?limit=101").status_code, 422)

    def test_review_preserves_all_purchase_checkpoints_and_records_operator(self):
        self.stale()
        self.state.uncertain_operation = "trusted_agent"
        self.db.commit()
        response = self.review()
        self.assertEqual(response.status_code, 200, response.text)
        self.db.expire_all()
        self.assertEqual(self.state.status, "error")
        self.assertIsNone(self.state.uncertain_operation)
        self.assertEqual(self.state.agent_id, "agent-saved")
        self.assertEqual(self.state.llm_id, "llm-saved")
        self.assertEqual(self.state.connection_id, "connection-saved")
        self.assertTrue(self.state.order_attempted)
        self.assertEqual(self.state.shield_number, "+12025550100")
        self.assertEqual(self.state.recovery_reviewed_by, 2)
        self.assertIsNotNone(self.state.recovery_reviewed_at)
        self.assertIn("saved checkpoints", self.state.recovery_note)
        self.subscription.assert_not_called()

    def test_review_rejects_live_completed_unreconciled_and_inactive_accounts(self):
        self.assertEqual(self.review().status_code, 409)
        self.state.status = "provisioning"
        self.state.activation_updated_at = datetime.utcnow()
        self.db.commit()
        self.assertEqual(self.review().status_code, 409)
        self.stale()
        self.assertEqual(self.review(provider_reconciled=False).status_code, 422)
        self.assertEqual(self.review(note=" ").status_code, 422)
        with activation_lock(self.db, 1):
            self.assertEqual(self.review().status_code, 409)
        self.db.get(User, 1).is_active = False
        self.db.commit()
        self.assertEqual(self.review().status_code, 409)
        self.assertEqual(self.client.post("/api/admin/customers/999/reopen-activation", json={
            "provider_reconciled": True, "note": "Reviewed",
        }).status_code, 404)

    def test_billing_refresh_does_not_hide_stale_activation(self):
        self.stale()
        progress_at = self.state.activation_updated_at
        self.status()
        self.assertEqual(self.state.activation_updated_at, progress_at)
        self.assertTrue(self.client.get("/api/admin/attention").json()["items"][0]["can_review_recovery"])

    def test_resource_checkpoint_survives_unknown_creation_response(self):
        with self.assertRaises(RuntimeError):
            with resource_creation(self.db, self.state, "screening_agent"):
                raise RuntimeError("lost response")
        self.db.expire_all()
        self.assertEqual(self.state.uncertain_operation, "screening_agent")
        with resource_creation(self.db, self.state, "screening_agent"):
            self.state.agent_id = "agent-confirmed"
        self.db.expire_all()
        self.assertIsNone(self.state.uncertain_operation)
        self.assertEqual(self.state.agent_id, "agent-confirmed")

    def test_postgres_lock_is_nonblocking_survives_checkpoint_commits_and_releases(self):
        db = MagicMock()
        engine = db.get_bind.return_value
        engine.dialect.name = "postgresql"
        connection = engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.scalar.return_value = True
        with self.assertRaises(RuntimeError):
            with activation_lock(db, 1):
                db.commit()
                raise RuntimeError("worker failed")
        queries = [str(call.args[0]) for call in connection.execute.call_args_list]
        self.assertIn("pg_try_advisory_lock", queries[0])
        self.assertIn("pg_advisory_unlock", queries[1])
        connection.execute.reset_mock()
        connection.execute.return_value.scalar.return_value = False
        with self.assertRaises(HTTPException) as error:
            with activation_lock(db, 1):
                self.fail("An active worker must prevent recovery")
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(connection.execute.call_count, 1)
