import json
import logging
from datetime import datetime

import httpx
import websockets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_active_user
from app.database import get_db
from app.models.call import Call
from app.models.user import User

router = APIRouter(prefix="/api/rootcall/live-calls", tags=["Live Calls"])
log = logging.getLogger(__name__)
LIVE_STATUSES = ("in-progress", "takeover-pending", "human-connected")


class TakeoverRequest(BaseModel):
    participant_id: str = Field(min_length=1, max_length=256)


def owned_call(db, user, call_id):
    call = db.query(Call).filter(Call.id == call_id, Call.user_id == user.id).first()
    if not call or not call.retell_call_id:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.ended_at or call.status not in LIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Call is no longer active")
    return call


async def provider_action(call_id, action, payload=None):
    if not settings.RETELL_API_KEY:
        raise HTTPException(status_code=503, detail="Retell is not configured")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://api.retellai.com/v2/{action}/{call_id}",
                headers={"Authorization": f"Bearer {settings.RETELL_API_KEY}"},
                json=payload or {},
            )
            response.raise_for_status()
            return response.json() if response.content else {}
    except (httpx.HTTPError, ValueError):
        log.warning("Live call provider action failed: %s", action)
        raise HTTPException(status_code=502, detail="Call control failed. Check the call before retrying.")


@router.get("")
def list_live_calls(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    calls = db.query(Call).filter(
        Call.user_id == current_user.id, Call.retell_call_id.isnot(None),
        Call.ended_at.is_(None), Call.status.in_(LIVE_STATUSES),
    ).order_by(Call.started_at.desc()).limit(50).all()
    return [{
        "id": call.id, "retell_call_id": call.retell_call_id,
        "from_number": call.from_number, "to_number": call.to_number,
        "status": call.status, "started_at": call.started_at.isoformat(),
        "transcript": call.transcription or "",
    } for call in calls]


@router.post("/{call_id}/listen")
async def listen(
    call_id: int, current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    call = owned_call(db, current_user, call_id)
    return await provider_action(call.retell_call_id, "listen-live-call")


@router.post("/{call_id}/takeover")
async def takeover(
    call_id: int, body: TakeoverRequest,
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db),
):
    call = owned_call(db, current_user, call_id)
    provider_id = call.retell_call_id
    claimed = db.query(Call).filter(
        Call.id == call_id, Call.user_id == current_user.id,
        Call.status == "in-progress", Call.ended_at.is_(None),
    ).update({Call.status: "takeover-pending"}, synchronize_session=False)
    db.commit()
    if not claimed:
        raise HTTPException(status_code=409, detail="Takeover is already in progress or completed")
    try:
        result = await provider_action(provider_id, "take-over-live-call", body.model_dump())
        if result.get("success") is not True:
            raise HTTPException(status_code=502, detail="Takeover was not confirmed")
    except HTTPException:
        db.query(Call).filter(Call.id == call_id, Call.status == "takeover-pending").update(
            {Call.status: "in-progress"}, synchronize_session=False
        )
        db.commit()
        raise
    db.query(Call).filter(Call.id == call_id, Call.status == "takeover-pending").update(
        {Call.status: "human-connected"}, synchronize_session=False
    )
    db.commit()
    return result


@router.post("/{call_id}/end")
async def end_call(
    call_id: int, current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    call = owned_call(db, current_user, call_id)
    if call.status == "human-connected":
        raise HTTPException(status_code=409, detail="End this call from the browser that took over")
    await provider_action(call.retell_call_id, "stop-call")
    call.status = "completed"
    call.ended_at = datetime.utcnow()
    db.commit()
    return {"status": "end-requested"}


@router.post("/{call_id}/release")
def release_session(
    call_id: int, current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    call = owned_call(db, current_user, call_id)
    if call.status != "human-connected":
        raise HTTPException(status_code=409, detail="No human session to release")
    call.status = "completed"
    call.ended_at = datetime.utcnow()
    db.commit()
    return {"status": "session-released"}


@router.get("/{call_id}/transcript")
def transcript(
    call_id: int, current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    call = owned_call(db, current_user, call_id)
    provider_id = call.retell_call_id
    if not settings.RETELL_API_KEY:
        raise HTTPException(status_code=503, detail="Retell is not configured")
    db.close()

    async def events():
        try:
            async with websockets.connect(
                f"wss://api.retellai.com/v2/monitor-call/{provider_id}",
                additional_headers={"Authorization": f"Bearer {settings.RETELL_API_KEY}"},
                open_timeout=10, max_size=2 ** 20,
            ) as upstream:
                async for message in upstream:
                    payload = json.loads(message)
                    yield f"data: {json.dumps(payload)}\n\n"
        except Exception:
            log.warning("Live transcript stream disconnected")
            yield 'data: {"type":"stream_error"}\n\n'

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-store", "X-Accel-Buffering": "no",
    })