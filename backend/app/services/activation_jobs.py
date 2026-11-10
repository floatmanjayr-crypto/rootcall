"""Database-backed activation jobs; provider checkpoints remain authoritative."""
from datetime import datetime, timedelta, timezone
import logging

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError

from app.models.activation_job import ActivationJob
from app.models.onboarding import CustomerOnboarding
from app.models.user import User
from app.services.activation_recovery import ActivationPending, activation_lock
from app.services.customer_onboarding import _provision_customer, validate_activation

log = logging.getLogger(__name__)
ACTIVE_STATUSES = ("queued", "running", "retry")
MAX_ATTEMPTS = 6
STALE_AFTER = timedelta(minutes=5)


def job_summary(job):
    return {
        "status": job.status, "attempts": job.attempts,
        "next_attempt_at": job.available_at.replace(tzinfo=timezone.utc).isoformat()
        if job.status in ("queued", "retry") else None,
        "message": job.last_error,
    } if job else None


def enqueue_activation(db, user):
    existing = db.get(ActivationJob, user.id)
    if existing and existing.status in ACTIVE_STATUSES:
        return {"accepted": True, "job": job_summary(existing)}
    with activation_lock(db, user.id):
        state = db.get(CustomerOnboarding, user.id)
        if not state:
            raise HTTPException(status_code=402, detail="Complete payment before activating.")
        if state.status == "completed":
            return {"success": True, "rootcall_number": state.shield_number, "job": None}
        job = db.get(ActivationJob, user.id)
        if job and job.status in ACTIVE_STATUSES:
            return {"accepted": True, "job": job_summary(job)}
        if job and job.status == "paused":
            raise HTTPException(status_code=409, detail="Support must review the paused activation before resuming.")
        validate_activation(db, user)
        state = db.query(CustomerOnboarding).filter(
            CustomerOnboarding.user_id == user.id,
        ).populate_existing().with_for_update().one()
        if state.status == "provisioning":
            raise HTTPException(status_code=409, detail="Setup needs support review before resuming.")
        if job is None:
            job = ActivationJob(user_id=user.id)
            db.add(job)
        job.status = "queued"
        job.attempts = 0
        job.available_at = job.updated_at = datetime.utcnow()
        job.last_error = None
        state.error_message = None
        state.activation_stage = "Waiting for automatic activation"
        db.commit()
        log.info("Activation queued for user %s", user.id)
        return {"accepted": True, "job": job_summary(job)}


def due_jobs(now):
    return or_(
        and_(ActivationJob.status.in_(("queued", "retry")), ActivationJob.available_at <= now),
        and_(ActivationJob.status == "running", ActivationJob.updated_at <= now - STALE_AFTER),
    )


def process_job(db, user_id):
    try:
        with activation_lock(db, user_id):
            return _process_locked(db, user_id)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        # Another live worker owns this account, even if its heartbeat is old.
        return False


def _process_locked(db, user_id):
    now = datetime.utcnow()
    job = db.query(ActivationJob).filter(
        ActivationJob.user_id == user_id, due_jobs(now),
    ).populate_existing().first()
    if job is None:
        return False
    state = db.query(CustomerOnboarding).filter(
        CustomerOnboarding.user_id == user_id,
    ).populate_existing().first()
    user = db.get(User, user_id)
    if state and state.status == "completed":
        job.status = "completed"
        job.last_error = None
        job.updated_at = now
        db.commit()
        return True
    if not state or not user or not user.is_active:
        job.status = "paused"
        job.last_error = "Account setup is unavailable. Contact support."
        job.updated_at = now
        db.commit()
        return True
    if state.uncertain_operation or job.attempts >= MAX_ATTEMPTS:
        _pause(db, job, state, "Setup needs support review before another attempt. Your provider checkpoints are saved.")
        return True
    # An acquired session lock proves a previous worker is gone. Never clear
    # uncertainty or order flags when recovering its interrupted job.
    if state.status == "provisioning":
        state.status = "error"
    job.status = "running"
    job.attempts += 1
    job.updated_at = now
    db.commit()
    try:
        _provision_customer(db, user)
    except HTTPException as error:
        db.rollback()
        db.refresh(state)
        retryable = isinstance(error, ActivationPending) or error.status_code in (502, 503)
        if retryable and not state.uncertain_operation and job.attempts < MAX_ATTEMPTS:
            job.status = "retry"
            job.last_error = str(error.detail)[:500]
            job.available_at = datetime.utcnow() + timedelta(seconds=min(30 * 2 ** (job.attempts - 1), 600))
            state.status = "error"
            state.error_message = "Setup is waiting for an automatic retry. Your number and provider checkpoints are saved."
            job.updated_at = datetime.utcnow()
            db.commit()
            log.warning("Activation retry scheduled for user %s, attempt %s", user_id, job.attempts)
        else:
            _pause(db, job, state, str(error.detail)[:500])
    except SQLAlchemyError:
        db.rollback()
        log.exception("Activation database failure for user %s; job will be recovered after restart", user_id)
        raise
    except Exception:
        # The worker boundary must expose unexpected failures, never retry an
        # unknown provider operation or report success.
        db.rollback()
        log.exception("Unexpected activation failure for user %s", user_id)
        db.refresh(state)
        _pause(db, job, state, "Setup paused after an unexpected error. Contact support; do not purchase another number.")
    else:
        job.status = "completed"
        job.last_error = None
        job.updated_at = datetime.utcnow()
        db.commit()
        log.info("Activation completed for user %s", user_id)
    return True


def _pause(db, job, state, message):
    message = f"Automatic activation paused. Contact support before retrying. {message}"[:500]
    job.status = "paused"
    job.last_error = message
    job.updated_at = datetime.utcnow()
    state.status = "error"
    state.error_message = message
    db.commit()
    log.warning("Activation paused for user %s after %s attempts; support review required",
                job.user_id, job.attempts)


def run_once(session_factory, stopping=None):
    with session_factory() as db:
        user_ids = [
            row[0] for row in db.query(ActivationJob.user_id).filter(due_jobs(datetime.utcnow()))
            .order_by(ActivationJob.available_at, ActivationJob.user_id).limit(25).all()
        ]
    processed = 0
    for user_id in user_ids:
        if stopping is not None and stopping.is_set():
            break
        with session_factory() as db:
            processed += int(process_job(db, user_id))
    return processed
