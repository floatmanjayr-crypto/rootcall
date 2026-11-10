# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, Field
from app.database import get_db
from app.config import settings
from app.deployment_checks import service_readiness
from app.core.deps import require_operator
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.rootcall_call_log import RootCallCallLog
from app.models.onboarding import CustomerOnboarding
from app.models.rootcall_config import RootCallConfig
from app.models.activation_job import ActivationJob
from app.services.activation_jobs import job_summary
from app.services.payment_verification import billing_summary
from app.services.activation_recovery import activation_lock, recovery_eligible, reopen_activation

router = APIRouter(tags=["Admin"])


@router.get("/api/admin/attention")
def attention_queue(
    skip: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(require_operator), db: Session = Depends(get_db),
):
    query = db.query(CustomerOnboarding, User).join(User, User.id == CustomerOnboarding.user_id).outerjoin(
        ActivationJob, ActivationJob.user_id == CustomerOnboarding.user_id,
    ).filter(
        or_(
            ActivationJob.status.in_(["queued", "running", "retry", "paused"]),
            CustomerOnboarding.status.in_(["error", "provisioning"]),
            CustomerOnboarding.subscription_status.notin_(["active"]),
            CustomerOnboarding.cancel_at_period_end.is_(True),
            CustomerOnboarding.cancel_at.isnot(None),
        ),
    )
    total = query.count()
    rows = query.order_by(CustomerOnboarding.updated_at, CustomerOnboarding.user_id).offset(skip).limit(limit).all()
    jobs = {job.user_id: job for job in db.query(ActivationJob).filter(
        ActivationJob.user_id.in_([state.user_id for state, _ in rows]),
    ).all()}
    configs = {
        (config.user_id, config.retell_did): config
        for config in db.query(RootCallConfig).filter(
            RootCallConfig.user_id.in_([state.user_id for state, _ in rows]),
        ).all()
    }

    def checkpoints(state):
        config = configs.get((state.user_id, state.shield_number))
        return {
            "order_attempted": state.order_attempted, "connection_id": state.connection_id,
            "llm_id": state.llm_id, "agent_id": state.agent_id,
            "transfer_ready": state.transfer_ready, "number_imported": state.number_imported,
            "trusted_flow_id": config.trusted_flow_id if config else None,
            "trusted_agent_id": config.trusted_agent_id if config else None,
        }

    return {"total": total, "items": [{
        "user_id": state.user_id, "email": user.email, "status": state.status,
        "shield_number": state.shield_number, "activation_stage": state.activation_stage,
        "error_message": state.error_message, "uncertain_operation": state.uncertain_operation,
        "can_review_recovery": recovery_eligible(state),
        "billing": billing_summary(state),
        "checkpoints": checkpoints(state),
        "recovery_reviewed_at": state.recovery_reviewed_at,
        "recovery_reviewed_by": state.recovery_reviewed_by,
        "recovery_note": state.recovery_note,
        "activation_job": job_summary(jobs.get(state.user_id)),
    } for state, user in rows]}


class RecoveryReview(BaseModel):
    provider_reconciled: bool
    note: str = Field(min_length=1, max_length=500)


@router.post("/api/admin/customers/{user_id}/reopen-activation")
def review_activation(
    user_id: int, body: RecoveryReview, current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    with activation_lock(db, user_id):
        state = db.query(CustomerOnboarding).filter(
            CustomerOnboarding.user_id == user_id,
        ).populate_existing().with_for_update().first()
        if not state:
            raise HTTPException(status_code=404, detail="Customer setup was not found.")
        if not db.get(User, user_id).is_active:
            raise HTTPException(status_code=409, detail="The account must be active before reopening setup.")
        reopen_activation(db, state, current_user.id, body.note, body.provider_reconciled)
    return {"success": True, "message": "Activation reopened. Previously confirmed background jobs resume automatically; older setups can be resumed by the customer. No provider changes or purchases were made by this review."}

@router.get("/api/admin/dashboard")
@router.get("/api/admin/dashboard/{admin_id}", include_in_schema=False)
async def admin_dashboard(
    admin_id: Optional[int] = None,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    if admin_id is not None and admin_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    total_users = db.query(User).count()
    total_numbers = db.query(PhoneNumber).filter(PhoneNumber.is_active == True).count()
    total_calls = db.query(RootCallCallLog).count()
    spam_blocked = db.query(RootCallCallLog).filter(RootCallCallLog.action == "spam_blocked").count()
    
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    
    return {
        "readiness": service_readiness(settings, db.get_bind()),
        "stats": {
            "total_users": total_users,
            "total_shield_numbers": total_numbers,
            "total_calls": total_calls,
            "spam_blocked": spam_blocked
        },
        "recent_users": [
            {"id": u.id, "email": u.email, "full_name": u.full_name}
            for u in recent_users
        ]
    }

@router.get("/api/admin/users")
@router.get("/api/admin/users/{admin_id}", include_in_schema=False)
async def get_all_users(
    admin_id: Optional[int] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db),
):
    if admin_id is not None and admin_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    users = db.query(User).order_by(User.id).offset(skip).limit(limit).all()
    
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ],
        "total": db.query(User).count()
    }
