"""One read-only activity view for customer history, totals, and exports."""
from datetime import timezone

from sqlalchemy import case, func, or_, select, union_all
from sqlalchemy.orm import Session

from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.rootcall_call_log import RootCallCallLog


def activity_query(db: Session, user_id: int):
    log = RootCallCallLog
    owned_numbers = select(PhoneNumber.id).where(PhoneNumber.user_id == user_id)
    same_call = (
        (Call.user_id == user_id)
        & (Call.phone_number_id == log.phone_number_id)
        & (log.call_control_id != "")
        & or_(
            log.call_control_id == Call.call_control_id,
            log.call_control_id == Call.telnyx_call_id,
            log.call_control_id == Call.retell_call_id,
        )
    )
    legacy_action = select(log.action).where(same_call).order_by(
        log.timestamp.desc(), log.id.desc()
    ).limit(1).correlate(Call).scalar_subquery()
    legacy_name = select(log.caller_name).where(same_call).order_by(
        log.timestamp.desc(), log.id.desc()
    ).limit(1).correlate(Call).scalar_subquery()
    action = case(
        (Call.is_spam.is_(True), "spam_blocked"),
        (Call.screening_action.in_(["trusted_transfer", "trusted_forwarded"]), "trusted_forwarded"),
        (Call.screening_action == "trusted_bypass", "trusted_bypass"),
        (Call.screening_action.in_(["retell_transfer", "screened"]), "screened"),
        else_=func.coalesce(
            Call.screening_action, legacy_action,
            case(
                (Call.direction == "outbound", "outbound"),
                (Call.retell_call_id.isnot(None), "screened"),
                else_="received",
            ),
        ),
    )
    calls = select(
        Call.started_at.label("timestamp"),
        Call.from_number.label("from_number"),
        func.coalesce(Call.caller_name, legacy_name, "Unknown").label("caller_name"),
        action.label("action"),
        Call.status.label("status"),
        (Call.id * 2).label("sort_id"),
    ).where(Call.user_id == user_id, Call.phone_number_id.in_(owned_numbers))
    legacy = select(
        log.timestamp, log.from_number, func.coalesce(log.caller_name, "Unknown"),
        log.action, log.status, log.id * 2 + 1,
    ).where(
        log.phone_number_id.in_(owned_numbers),
        ~select(Call.id).where(same_call).correlate(log).exists(),
    )
    activity = union_all(calls, legacy).subquery()
    return db.query(
        activity.c.timestamp, activity.c.from_number, activity.c.caller_name,
        activity.c.action, activity.c.status,
    ).order_by(activity.c.timestamp.desc(), activity.c.sort_id.desc())


def activity_stats(db: Session, user_id: int):
    activity = activity_query(db, user_id).order_by(None).subquery()
    counts = dict(db.query(
        activity.c.action, func.count(),
    ).group_by(activity.c.action).all())
    return {
        "spam_blocked": counts.get("spam_blocked", 0),
        "calls_screened": counts.get("screened", 0),
        "trusted_forwarded": counts.get("trusted_forwarded", 0),
        "trusted_calls": counts.get("trusted_forwarded", 0) + counts.get("trusted_bypass", 0),
        "total_calls": sum(counts.values()),
    }


def serialize_activity(row):
    timestamp = row.timestamp
    if timestamp is not None and timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return {
        "timestamp": timestamp.isoformat() if timestamp else None,
        "from_number": row.from_number,
        "caller_name": row.caller_name,
        "action": row.action,
        "status": row.status,
    }
