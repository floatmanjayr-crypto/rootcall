from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import csv
import io

from app.database import get_db
from app.models.bulk_campaign import (
    BulkCampaign, CampaignRecipient, CampaignTemplate,
    CampaignType, CampaignStatus
)
from app.services.bulk_service import BulkCampaignService

router = APIRouter(prefix="/api/v1/bulk", tags=["Bulk Campaigns"])


# Pydantic Schemas
class CreateCampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    campaign_type: CampaignType
    phone_number_id: int
    ai_agent_id: Optional[int] = None
    
    # Voice settings
    voice_message: Optional[str] = None
    voice_audio_url: Optional[str] = None
    max_call_duration: int = 300
    enable_voicemail_detection: bool = True
    leave_voicemail: bool = True
    voicemail_message: Optional[str] = None
    
    # SMS settings
    sms_message: Optional[str] = None
    enable_sms_personalization: bool = True
    
    # Scheduling
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    timezone: str = "America/New_York"
    
    # Rate limiting
    calls_per_minute: int = Field(default=10, ge=1, le=60)
    calls_per_hour: int = Field(default=100, ge=1, le=1000)
    concurrent_calls: int = Field(default=5, ge=1, le=20)
    
    # Retry logic
    max_retry_attempts: int = Field(default=2, ge=0, le=5)
    retry_delay_minutes: int = Field(default=30, ge=5, le=1440)
    retry_on_no_answer: bool = True
    retry_on_busy: bool = True
    
    # Advanced
    require_confirmation: bool = False
    record_calls: bool = True
    transcribe_calls: bool = False
    collect_dtmf: bool = False
    dtmf_options: Optional[Dict[str, str]] = None
    
    # Compliance
    respect_dnc: bool = True
    quiet_hours_start: str = "21:00"
    quiet_hours_end: str = "08:00"


class AddRecipientRequest(BaseModel):
    phone_number: str
    name: Optional[str] = None
    email: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = None


class AddRecipientsRequest(BaseModel):
    recipients: List[AddRecipientRequest]


class CampaignResponse(BaseModel):
    id: int
    name: str
    status: str
    campaign_type: str
    total_recipients: int
    completed_count: int
    failed_count: int
    success_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Endpoints

@router.post("/campaigns", response_model=CampaignResponse)
def create_campaign(
    request: CreateCampaignRequest,
    user_id: int = 1,  # TODO: Get from auth
    db: Session = Depends(get_db)
):
    """Create a new bulk campaign"""
    try:
        campaign_data = request.dict()
        campaign_data["user_id"] = user_id
        
        campaign = BulkCampaignService.create_campaign(db, user_id, campaign_data)
        
        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status.value,
            campaign_type=campaign.campaign_type.value,
            total_recipients=campaign.total_recipients,
            completed_count=campaign.completed_count,
            failed_count=campaign.failed_count,
            success_count=campaign.success_count,
            created_at=campaign.created_at,
            started_at=campaign.started_at,
            completed_at=campaign.completed_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaigns/{campaign_id}/recipients")
def add_recipients(
    campaign_id: int,
    request: AddRecipientsRequest,
    db: Session = Depends(get_db)
):
    """Add recipients to a campaign"""
    try:
        recipients_data = [r.dict() for r in request.recipients]
        recipients = BulkCampaignService.add_recipients(db, campaign_id, recipients_data)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "recipients_added": len(recipients)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaigns/{campaign_id}/recipients/upload")
async def upload_recipients_csv(
    campaign_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload recipients via CSV file"""
    try:
        content = await file.read()
        csv_file = io.StringIO(content.decode('utf-8'))
        csv_reader = csv.DictReader(csv_file)
        
        recipients_data = []
        for row in csv_reader:
            recipient = {
                "phone_number": row.get("phone_number", "").strip(),
                "name": row.get("name", "").strip() or None,
                "email": row.get("email", "").strip() or None,
            }
            
            custom_data = {}
            for key, value in row.items():
                if key not in ["phone_number", "name", "email"] and value:
                    custom_data[key] = value.strip()
            
            if custom_data:
                recipient["custom_data"] = custom_data
            
            if recipient["phone_number"]:
                recipients_data.append(recipient)
        
        if not recipients_data:
            raise HTTPException(status_code=400, detail="No valid recipients found in CSV")
        
        recipients = BulkCampaignService.add_recipients(db, campaign_id, recipients_data)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "recipients_added": len(recipients)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """Start executing a campaign"""
    try:
        result = await BulkCampaignService.start_campaign(db, campaign_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaigns/{campaign_id}/pause")
def pause_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """Pause a running campaign"""
    try:
        result = BulkCampaignService.pause_campaign(db, campaign_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaigns/{campaign_id}/resume")
def resume_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """Resume a paused campaign"""
    try:
        result = BulkCampaignService.resume_campaign(db, campaign_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campaigns/{campaign_id}/stats")
def get_campaign_stats(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed campaign statistics"""
    try:
        stats = BulkCampaignService.get_campaign_stats(db, campaign_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """Get campaign details"""
    campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "campaign_type": campaign.campaign_type.value,
        "status": campaign.status.value,
        "phone_number_id": campaign.phone_number_id,
        "ai_agent_id": campaign.ai_agent_id,
        "voice_message": campaign.voice_message,
        "sms_message": campaign.sms_message,
        "total_recipients": campaign.total_recipients,
        "completed_count": campaign.completed_count,
        "failed_count": campaign.failed_count,
        "success_count": campaign.success_count,
        "calls_per_minute": campaign.calls_per_minute,
        "calls_per_hour": campaign.calls_per_hour,
        "concurrent_calls": campaign.concurrent_calls,
        "estimated_cost": campaign.estimated_cost,
        "actual_cost": campaign.actual_cost,
        "created_at": campaign.created_at,
        "started_at": campaign.started_at,
        "completed_at": campaign.completed_at
    }


@router.get("/campaigns")
def list_campaigns(
    user_id: int = 1,
    status: Optional[CampaignStatus] = None,
    campaign_type: Optional[CampaignType] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List all campaigns for a user"""
    query = db.query(BulkCampaign).filter(BulkCampaign.user_id == user_id)
    
    if status:
        query = query.filter(BulkCampaign.status == status)
    
    if campaign_type:
        query = query.filter(BulkCampaign.campaign_type == campaign_type)
    
    campaigns = query.order_by(BulkCampaign.created_at.desc()).limit(limit).offset(offset).all()
    
    return {
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "campaign_type": c.campaign_type.value,
                "status": c.status.value,
                "total_recipients": c.total_recipients,
                "completed_count": c.completed_count,
                "success_count": c.success_count,
                "created_at": c.created_at,
                "started_at": c.started_at
            }
            for c in campaigns
        ],
        "total": query.count()
    }


@router.get("/campaigns/{campaign_id}/recipients")
def get_campaign_recipients(
    campaign_id: int,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get recipients for a campaign"""
    query = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id)
    
    if status:
        query = query.filter(CampaignRecipient.status == status)
    
    recipients = query.limit(limit).offset(offset).all()
    
    return {
        "recipients": [
            {
                "id": r.id,
                "phone_number": r.phone_number,
                "name": r.name,
                "status": r.status.value,
                "attempts": r.attempts,
                "call_status": r.call_status,
                "message_status": r.message_status,
                "cost": r.cost,
                "error_message": r.error_message,
                "last_attempt_at": r.last_attempt_at,
                "completed_at": r.completed_at
            }
            for r in recipients
        ],
        "total": query.count()
    }


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """Delete a campaign"""
    campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status == CampaignStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete running campaign")
    
    db.delete(campaign)
    db.commit()
    
    return {"success": True, "message": "Campaign deleted"}
