"""Guard activation retries and require review for uncertain resource creation."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging
from threading import Lock
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import text

log = logging.getLogger(__name__)
_sqlite_locks = WeakKeyDictionary()
_registry_lock = Lock()


class ActivationPending(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail)


@contextmanager
def activation_lock(db, user_id: int):
    engine = db.get_bind()
    if engine.dialect.name == "postgresql":
        # A separate session-level lock survives provisioning checkpoint commits.
        with engine.connect() as connection:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(73021, :user_id)"), {"user_id": user_id},
            ).scalar()
            if not acquired:
                raise HTTPException(status_code=409, detail="Activation is still running. No recovery changes were made.")
            try:
                yield
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(73021, :user_id)"), {"user_id": user_id},
                )
    elif engine.dialect.name == "sqlite":
        # SQLite is for single-process local development; production uses PostgreSQL.
        with _registry_lock:
            locks = _sqlite_locks.setdefault(engine, {})
            lock = locks.setdefault(user_id, Lock())
        if not lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Activation is still running. No recovery changes were made.")
        try:
            yield
        finally:
            lock.release()
    else:
        log.error("Unsupported database for guarded activation recovery")
        raise HTTPException(status_code=503, detail="Activation recovery requires a supported database.")


@contextmanager
def resource_creation(db, onboarding, operation: str):
    if onboarding is None:
        yield
        return
    onboarding.uncertain_operation = operation
    onboarding.activation_updated_at = datetime.utcnow()
    db.commit()
    yield
    onboarding.uncertain_operation = None
    onboarding.activation_updated_at = datetime.utcnow()
    db.commit()


def recovery_eligible(onboarding) -> bool:
    if onboarding.status == "error":
        return True
    return bool(
        onboarding.status == "provisioning" and onboarding.activation_updated_at
        and onboarding.activation_updated_at <= datetime.utcnow() - timedelta(minutes=30)
    )


def reopen_activation(db, onboarding, administrator_id: int, note: str, reconciled: bool):
    if not recovery_eligible(onboarding):
        raise HTTPException(status_code=409, detail="Only paused or stale activations can be reopened.")
    if not reconciled:
        raise HTTPException(status_code=422, detail="Confirm provider reconciliation before reopening activation.")
    if not note.strip() or len(note.strip()) > 500:
        raise HTTPException(status_code=422, detail="Enter a provider reconciliation note of 1 to 500 characters.")
    # Never clear purchased-number or provider-ID checkpoints.
    onboarding.status = "error"
    onboarding.uncertain_operation = None
    onboarding.error_message = "Support reviewed your setup. Resume activation using your saved details; do not purchase another number."
    onboarding.recovery_reviewed_at = datetime.utcnow()
    onboarding.recovery_reviewed_by = administrator_id
    onboarding.recovery_note = note.strip()
    from app.models.activation_job import ActivationJob
    job = db.get(ActivationJob, onboarding.user_id)
    if job:
        job.status = "queued"
        job.attempts = 0
        job.available_at = job.updated_at = datetime.utcnow()
        job.last_error = None
        onboarding.error_message = None
        onboarding.activation_stage = "Support reviewed setup; waiting for automatic activation"
    db.commit()
    log.warning("Activation reopened after provider review by administrator %s for user %s",
                administrator_id, onboarding.user_id)
