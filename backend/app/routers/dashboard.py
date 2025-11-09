"""Real-time Dashboard API for Call Monitoring"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import json
import logging

from app.database import get_db
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.models.bulk_campaign import BulkCampaign, CampaignRecipient
from app.models.user import User
from app.models.subscription import Subscription, UsageLog
from app.config import settings

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])
log = logging.getLogger(__name__)


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    def __init__(self):
        self.active_connections: dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        log.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        log.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass


manager = ConnectionManager()


# ============================================================================
# Pydantic Models
# ============================================================================

class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_calls_today: int
    active_calls: int
    total_minutes_today: int
    total_cost_today: float
    success_rate: float
    avg_call_duration: int


class CallStats(BaseModel):
    """Call statistics"""
    call_id: str
    direction: str
    from_number: str
    to_number: str
    status: str
    duration: Optional[int]
    cost: Optional[float]
    started_at: datetime
    ended_at: Optional[datetime]


class CampaignStats(BaseModel):
    """Campaign statistics"""
    campaign_id: int
    name: str
    status: str
    total_recipients: int
    completed: int
    success_rate: float
    avg_duration: int
    total_cost: float


# ============================================================================
# Helper Functions
# ============================================================================

def get_date_range(period: str) -> tuple[datetime, datetime]:
    """Get start and end date for period"""
    now = datetime.utcnow()
    
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        start = now - timedelta(days=7)
        end = now
    elif period == "month":
        start = now - timedelta(days=30)
        end = now
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    
    return start, end


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/stats/{user_id}", response_model=DashboardStats)
async def get_dashboard_stats(
    user_id: int,
    period: str = "today",
    db: Session = Depends(get_db)
):
    """Get dashboard statistics for user"""
    
    start_date, end_date = get_date_range(period)
    
    # Total calls
    total_calls = db.query(func.count(Call.id)).filter(
        Call.user_id == user_id,
        Call.started_at >= start_date,
        Call.started_at <= end_date
    ).scalar() or 0
    
    # Active calls (currently in progress)
    active_calls = db.query(func.count(Call.id)).filter(
        Call.user_id == user_id,
        Call.status.in_(["initiated", "ringing", "answered", "in-progress"])
    ).scalar() or 0
    
    # Total minutes
    total_seconds = db.query(func.sum(Call.duration)).filter(
        Call.user_id == user_id,
        Call.started_at >= start_date,
        Call.started_at <= end_date,
        Call.duration.isnot(None)
    ).scalar() or 0
    total_minutes = int(total_seconds / 60) if total_seconds else 0
    
    # Total cost
    total_cost = db.query(func.sum(Call.cost)).filter(
        Call.user_id == user_id,
        Call.started_at >= start_date,
        Call.started_at <= end_date,
        Call.cost.isnot(None)
    ).scalar() or 0.0
    
    # Success rate (completed calls / total calls)
    completed_calls = db.query(func.count(Call.id)).filter(
        Call.user_id == user_id,
        Call.started_at >= start_date,
        Call.started_at <= end_date,
        Call.status == "completed"
    ).scalar() or 0
    
    success_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0.0
    
    # Average call duration
    avg_duration = int(total_seconds / total_calls) if total_calls > 0 else 0
    
    return DashboardStats(
        total_calls_today=total_calls,
        active_calls=active_calls,
        total_minutes_today=total_minutes,
        total_cost_today=round(total_cost, 2),
        success_rate=round(success_rate, 1),
        avg_call_duration=avg_duration
    )


@router.get("/calls/{user_id}/recent")
async def get_recent_calls(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get recent calls for user"""
    
    calls = db.query(Call).filter(
        Call.user_id == user_id
    ).order_by(
        Call.started_at.desc()
    ).limit(limit).offset(offset).all()
    
    return {
        "calls": [
            CallStats(
                call_id=call.call_control_id or str(call.id),
                direction=call.direction,
                from_number=call.from_number,
                to_number=call.to_number,
                status=call.status,
                duration=call.duration,
                cost=call.cost,
                started_at=call.started_at,
                ended_at=call.ended_at
            )
            for call in calls
        ]
    }


@router.get("/calls/{user_id}/active")
async def get_active_calls(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get currently active calls"""
    
    active_calls = db.query(Call).filter(
        Call.user_id == user_id,
        Call.status.in_(["initiated", "ringing", "answered", "in-progress"])
    ).all()
    
    return {
        "active_calls": [
            {
                "call_id": call.call_control_id or str(call.id),
                "direction": call.direction,
                "from_number": call.from_number,
                "to_number": call.to_number,
                "status": call.status,
                "started_at": call.started_at,
                "duration_seconds": (datetime.utcnow() - call.started_at).total_seconds() if call.started_at else 0
            }
            for call in active_calls
        ]
    }


@router.get("/campaigns/{user_id}/stats")
async def get_campaign_stats(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get campaign statistics"""
    
    campaigns = db.query(BulkCampaign).filter(
        BulkCampaign.user_id == user_id
    ).order_by(
        BulkCampaign.created_at.desc()
    ).limit(10).all()
    
    campaign_stats = []
    
    for campaign in campaigns:
        # Calculate success rate
        success_count = db.query(func.count(CampaignRecipient.id)).filter(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status == "completed"
        ).scalar() or 0
        
        success_rate = (success_count / campaign.total_recipients * 100) if campaign.total_recipients > 0 else 0.0
        
        # Calculate average duration
        avg_duration = db.query(func.avg(CampaignRecipient.call_duration)).filter(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.call_duration.isnot(None)
        ).scalar() or 0
        
        # Calculate total cost
        total_cost = db.query(func.sum(CampaignRecipient.cost)).filter(
            CampaignRecipient.campaign_id == campaign.id
        ).scalar() or 0.0
        
        campaign_stats.append(
            CampaignStats(
                campaign_id=campaign.id,
                name=campaign.name,
                status=campaign.status.value,
                total_recipients=campaign.total_recipients,
                completed=campaign.completed_count,
                success_rate=round(success_rate, 1),
                avg_duration=int(avg_duration) if avg_duration else 0,
                total_cost=round(total_cost, 2)
            )
        )
    
    return {"campaigns": campaign_stats}


@router.get("/usage/{user_id}")
async def get_usage_breakdown(
    user_id: int,
    period: str = "month",
    db: Session = Depends(get_db)
):
    """Get usage breakdown by feature"""
    
    start_date, end_date = get_date_range(period)
    
    # Query usage logs
    usage_logs = db.query(
        UsageLog.feature_type,
        func.sum(UsageLog.quantity).label('total_quantity'),
        func.sum(UsageLog.total_cost).label('total_cost')
    ).filter(
        UsageLog.user_id == user_id,
        UsageLog.created_at >= start_date,
        UsageLog.created_at <= end_date
    ).group_by(UsageLog.feature_type).all()
    
    return {
        "period": period,
        "usage": [
            {
                "feature": log.feature_type.value,
                "quantity": log.total_quantity,
                "cost": round(log.total_cost, 2)
            }
            for log in usage_logs
        ]
    }


@router.get("/subscription/{user_id}")
async def get_subscription_info(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get subscription information and limits"""
    
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id
    ).first()
    
    if not subscription:
        return {
            "tier": "none",
            "message": "No active subscription"
        }
    
    # Calculate usage percentage
    minutes_used_pct = (subscription.monthly_minutes_used / subscription.monthly_minutes_included * 100) if subscription.monthly_minutes_included > 0 else 0
    
    return {
        "tier": subscription.tier.value,
        "monthly_price": subscription.monthly_price,
        "minutes_included": subscription.monthly_minutes_included,
        "minutes_used": subscription.monthly_minutes_used,
        "minutes_remaining": max(0, subscription.monthly_minutes_included - subscription.monthly_minutes_used),
        "minutes_used_percentage": round(minutes_used_pct, 1),
        "trial_ends_at": subscription.trial_ends_at,
        "is_active": subscription.is_active,
        "billing_cycle_end": subscription.billing_cycle_end
    }


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time updates"""
    
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            # Echo back (or handle commands)
            await websocket.send_json({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


# Helper function to broadcast call updates (call from webhooks)
async def broadcast_call_update(user_id: int, call_data: dict):
    """Broadcast call update to user's dashboard"""
    await manager.send_personal_message({
        "type": "call_update",
        "data": call_data,
        "timestamp": datetime.utcnow().isoformat()
    }, user_id)
