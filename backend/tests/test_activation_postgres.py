"""Opt-in integration checks against an isolated PostgreSQL test database."""
import multiprocessing
import os
import importlib.util
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-unused-key")

import pytest
from fastapi import HTTPException
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.models.activation_job import ActivationJob
from app.models.onboarding import CustomerOnboarding
from app.models.user import User
from app.services.activation_jobs import process_job
from app.services.activation_recovery import activation_lock

URL = os.environ.get("TEST_ACTIVATION_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Set TEST_ACTIVATION_POSTGRES_URL to an isolated PostgreSQL database")


def _hold_worker(url, schema, pipe, uncertain):
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with sessionmaker(bind=engine)() as db, activation_lock(db, 1):
            job = db.get(ActivationJob, 1)
            job.status = "running"
            job.updated_at = datetime.utcnow() - timedelta(minutes=6)
            state = db.get(CustomerOnboarding, 1)
            state.status = "provisioning"
            if uncertain:
                state.uncertain_operation = "screening_agent"
            db.commit()
            pipe.send("locked-after-commit")
            pipe.recv()
    finally:
        engine.dispose()
        pipe.close()


@pytest.fixture
def postgres_db():
    schema = "activation_test_" + uuid4().hex
    admin = create_engine(URL)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.begin() as connection:
            for table in (User.__table__, CustomerOnboarding.__table__, ActivationJob.__table__):
                table.create(connection)
        with sessionmaker(bind=engine)() as db:
            db.add(User(id=1, email="activation@example.com", hashed_password="unused", is_active=True))
            db.flush()
            db.add(CustomerOnboarding(user_id=1, checkout_key="saved", status="draft", order_attempted=True))
            db.add(ActivationJob(user_id=1))
            db.commit()
        yield engine, schema
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.parametrize("uncertain", [False, True])
def test_process_death_releases_lock_and_preserves_creation_safety(postgres_db, uncertain):
    engine, schema = postgres_db
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    worker = context.Process(target=_hold_worker, args=(URL, schema, child, uncertain))
    worker.start()
    child.close()
    try:
        assert parent.poll(30), "Worker failed to acquire PostgreSQL lock"
        assert parent.recv() == "locked-after-commit"
        with sessionmaker(bind=engine)() as db:
            # A different process still owns the advisory lock after DB commits.
            with pytest.raises(HTTPException) as busy:
                with activation_lock(db, 1):
                    pytest.fail("A live worker lock was stolen")
            assert busy.value.status_code == 409
            assert process_job(db, 1) is False
        worker.terminate()
        worker.join(timeout=10)
        assert not worker.is_alive()

        def finish(db, user):
            state = db.get(CustomerOnboarding, user.id)
            assert state.order_attempted
            state.status = "completed"
            db.commit()

        with sessionmaker(bind=engine)() as db, patch(
            "app.services.activation_jobs._provision_customer", side_effect=finish,
        ) as provision:
            assert process_job(db, 1) is True
            job = db.get(ActivationJob, 1)
            state = db.get(CustomerOnboarding, 1)
            if uncertain:
                assert job.status == "paused"
                assert state.uncertain_operation == "screening_agent"
                provision.assert_not_called()
            else:
                assert job.status == "completed"
                provision.assert_called_once()
            assert state.order_attempted
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=10)
        parent.close()


def test_worker_entrypoint_is_ready_and_shuts_down_cleanly(postgres_db, tmp_path):
    engine, schema = postgres_db
    with sessionmaker(bind=engine)() as db:
        db.get(ActivationJob, 1).status = "completed"
        db.commit()
    environment = {
        **os.environ, "DATABASE_URL": URL, "PGOPTIONS": f"-csearch_path={schema}",
        "OPENAI_API_KEY": "test-unused-key", "TELNYX_API_KEY": "test-unused-key",
        "RETELL_API_KEY": "test-unused-key", "STRIPE_SECRET_KEY": "test-unused-key",
    }
    output = tmp_path / "worker.log"
    with output.open("w") as log:
        worker = subprocess.Popen(
            [sys.executable, "-m", "app.activation_worker"],
            cwd=Path(__file__).parents[1], env=environment, stdout=log, stderr=subprocess.STDOUT,
        )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and worker.poll() is None:
            if "Activation worker ready" in output.read_text():
                break
            time.sleep(0.1)
        assert worker.poll() is None, output.read_text()
        assert "Activation worker ready" in output.read_text()
        worker.terminate()
        assert worker.wait(timeout=15) == 0, output.read_text()
        assert "Activation worker stopped" in output.read_text()
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait(timeout=10)


def test_postgres_migration_preserves_existing_setup(postgres_db):
    engine, _ = postgres_db
    path = Path(__file__).parents[1] / "alembic/versions/d143fa65e329_automated_activation.py"
    spec = importlib.util.spec_from_file_location("activation_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        ActivationJob.__table__.drop(connection)
        connection.execute(text("ALTER TABLE customer_onboarding DROP COLUMN service_setup"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert {column["name"] for column in inspect(connection).get_columns("activation_jobs")} == set(
                ActivationJob.__table__.columns.keys(),
            )
            row = connection.execute(text(
                "SELECT checkout_key, order_attempted, service_setup FROM customer_onboarding WHERE user_id = 1"
            )).one()
            assert row.checkout_key == "saved"
            assert row.order_attempted
            assert row.service_setup is None
            migration.downgrade()
            migration.upgrade()
            assert connection.execute(text(
                "SELECT checkout_key FROM customer_onboarding WHERE user_id = 1"
            )).scalar() == "saved"
