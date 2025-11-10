"""Campaign Management with CSV Upload"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import csv
import io
import logging

from app.database import get_db
from app.models.bulk_campaign import BulkCampaign, CampaignRecipient, CampaignStatus, CampaignType
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.models.subscription import Subscription, FeatureType
from app.services.retell_service import retell_service
from app.config import settings

router = APIRouter(prefix="/api/v1/campaigns", tags=["Campaign Management"])
log = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class CreateCampaignRequest(BaseModel):
    """Create new campaign"""
    user_id: int
    phone_number: str
    name: str
    description: Optional[str] = None
    campaign_type: str = "voice"  # voice, sms, both
    
    # AI Agent
    agent_id: Optional[str] = None
    
    # Voice settings
    max_call_duration: int = 300
    enable_voicemail_detection: bool = True
    leave_voicemail: bool = True
    voicemail_message: Optional[str] = None
    
    # Rate limiting
    calls_per_minute: int = 10
    concurrent_calls: int = 5
    
    # Retry settings
    max_retry_attempts: int = 2
    retry_delay_minutes: int = 30


class CampaignResponse(BaseModel):
    """Campaign response"""
    id: int
    name: str
    status: str
    total_recipients: int
    completed_count: int
    success_count: int
    failed_count: int
    created_at: datetime


class StartCampaignRequest(BaseModel):
    """Start campaign execution"""
    campaign_id: int
    user_id: int


# ============================================================================
# Helper Functions
# ============================================================================

def verify_campaign_access(db: Session, user_id: int, campaign_id: int) -> BulkCampaign:
    """Verify user owns the campaign"""
    campaign = db.query(BulkCampaign).filter(
        BulkCampaign.id == campaign_id,
        BulkCampaign.user_id == user_id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign


def check_feature_enabled(db: Session, user_id: int, feature: str) -> bool:
    """Check if user has feature enabled"""
    from app.models.subscription import UserFeature
    
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id
    ).first()
    
    if not subscription:
        return False
    
    user_feature = db.query(UserFeature).filter(
        UserFeature.subscription_id == subscription.id,
        UserFeature.feature_type == feature,
        UserFeature.is_enabled == True
    ).first()
    
    return user_feature is not None


def parse_csv_recipients(csv_content: str) -> List[dict]:
    """Parse CSV file and extract recipient data"""
    recipients = []
    
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)
    
    for row in reader:
        # Required field: phone_number
        if 'phone_number' not in row or not row['phone_number']:
            continue
        
        recipient = {
            'phone_number': row['phone_number'].strip(),
            'name': row.get('name', '').strip() or None,
            'email': row.get('email', '').strip() or None,
            'custom_data': {}
        }
        
        # Add any additional columns as custom_data
        for key, value in row.items():
            if key not in ['phone_number', 'name', 'email'] and value:
                recipient['custom_data'][key] = value
        
        recipients.append(recipient)
    
    return recipients


async def execute_campaign(campaign_id: int, db: Session):
    """Execute campaign in background"""
    campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
    
    if not campaign:
        return
    
    # Update status
    campaign.status = CampaignStatus.RUNNING
    campaign.started_at = datetime.utcnow()
    db.commit()
    
    # Get recipients
    recipients = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == campaign_id,
        CampaignRecipient.status == "pending"
    ).all()
    
    log.info(f"íº€ Executing campaign {campaign.name} with {len(recipients)} recipients")
    
    for recipient in recipients:
        try:
            # Make call via Retell
            call_response = retell_service.create_phone_call(
                from_number=campaign.phone_number.phone_number,
                to_number=recipient.phone_number,
                override_agent_id=campaign.ai_agent.retell_agent_id
            )
            
            # Update recipient status
            recipient.status = "in_progress"
            recipient.attempts += 1
            recipient.last_attempt_at = datetime.utcnow()
            recipient.call_status = call_response.get("call_status")
            
            campaign.completed_count += 1
            
            db.commit()
            
            # Rate limiting delay
            import time
            time.sleep(60 / campaign.calls_per_minute)
            
        except Exception as e:
            log.error(f"Failed to call {recipient.phone_number}: {str(e)}")
            recipient.status = "failed"
            recipient.error_message = str(e)
            campaign.failed_count += 1
            db.commit()
    
    # Campaign complete
    campaign.status = CampaignStatus.COMPLETED
    campaign.completed_at = datetime.utcnow()
    db.commit()
    
    log.info(f"âœ… Campaign {campaign.name} completed")


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/create", response_model=CampaignResponse)
async def create_campaign(
    request: CreateCampaignRequest,
    db: Session = Depends(get_db)
):
    """Create a new campaign"""
    
    # Check if user has bulk_campaigns feature
    if not check_feature_enabled(db, request.user_id, "bulk_campaigns"):
        raise HTTPException(
            status_code=403,
            detail="Bulk campaigns feature not enabled. Please upgrade your plan."
        )
    
    # Verify phone number
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == request.user_id,
        PhoneNumber.phone_number == request.phone_number
    ).first()
    
    if not phone:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    # Get AI agent
    agent = None
    if request.agent_id:
        agent = db.query(AIAgent).filter(
            AIAgent.retell_agent_id == request.agent_id
        ).first()
    
    # Create campaign
    campaign = BulkCampaign(
        user_id=request.user_id,
        phone_number_id=phone.id,
        ai_agent_id=agent.id if agent else None,
        name=request.name,
        description=request.description,
        campaign_type=CampaignType(request.campaign_type),
        max_call_duration=request.max_call_duration,
        enable_voicemail_detection=request.enable_voicemail_detection,
        leave_voicemail=request.leave_voicemail,
        voicemail_message=request.voicemail_message,
        calls_per_minute=request.calls_per_minute,
        concurrent_calls=request.concurrent_calls,
        max_retry_attempts=request.max_retry_attempts,
        retry_delay_minutes=request.retry_delay_minutes,
        status=CampaignStatus.DRAFT
    )
    
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    
    log.info(f"âœ… Created campaign: {campaign.name}")
    
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status.value,
        total_recipients=0,
        completed_count=0,
        success_count=0,
        failed_count=0,
        created_at=campaign.created_at
    )


@router.post("/{campaign_id}/upload-csv")
async def upload_recipients_csv(
    campaign_id: int,
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload CSV file with recipients"""
    
    # Verify campaign access
    campaign = verify_campaign_access(db, user_id, campaign_id)
    
    # Read and parse CSV
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        recipients_data = parse_csv_recipients(csv_content)
        
        if not recipients_data:
            raise HTTPException(status_code=400, detail="No valid recipients found in CSV")
        
        # Add recipients to campaign
        for data in recipients_data:
            recipient = CampaignRecipient(
                campaign_id=campaign_id,
                phone_number=data['phone_number'],
                name=data.get('name'),
                email=data.get('email'),
                custom_data=data.get('custom_data'),
                status="pending"
            )
            db.add(recipient)
        
        # Update campaign total
        campaign.total_recipients = len(recipients_data)
        db.commit()
        
        log.info(f"âœ… Uploaded {len(recipients_data)} recipients to campaign {campaign.name}")
        
        return {
            "campaign_id": campaign_id,
            "recipients_uploaded": len(recipients_data),
            "status": "success"
        }
        
    except Exception as e:
        log.error(f"Failed to upload CSV: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")


@router.post("/{campaign_id}/start")
async def start_campaign(
    campaign_id: int,
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start campaign execution"""
    
    campaign = verify_campaign_access(db, user_id, campaign_id)
    
    if campaign.status != CampaignStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Campaign must be in DRAFT status. Current: {campaign.status.value}"
        )
    
    if campaign.total_recipients == 0:
        raise HTTPException(status_code=400, detail="No recipients in campaign")
    
    # Schedule campaign execution
    background_tasks.add_task(execute_campaign, campaign_id, db)
    
    return {
        "campaign_id": campaign_id,
        "status": "scheduled",
        "total_recipients": campaign.total_recipients,
        "message": "Campaign execution started"
    }


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get campaign details"""
    campaign = verify_campaign_access(db, user_id, campaign_id)
    
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status.value,
        total_recipients=campaign.total_recipients,
        completed_count=campaign.completed_count,
        success_count=campaign.success_count,
        failed_count=campaign.failed_count,
        created_at=campaign.created_at
    )


@router.get("/user/{user_id}/campaigns")
async def list_user_campaigns(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List all campaigns for a user"""
    campaigns = db.query(BulkCampaign).filter(
        BulkCampaign.user_id == user_id
    ).order_by(
        BulkCampaign.created_at.desc()
    ).limit(limit).offset(offset).all()
    
    return {
        "campaigns": [
            CampaignResponse(
                id=c.id,
                name=c.name,
                status=c.status.value,
                total_recipients=c.total_recipients,
                completed_count=c.completed_count,
                success_count=c.success_count,
                failed_count=c.failed_count,
                created_at=c.created_at
            )
            for c in campaigns
        ]
    }
