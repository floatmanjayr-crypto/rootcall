import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import telnyx
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.config import settings
from app.models.bulk_campaign import (
    BulkCampaign, CampaignRecipient, CampaignStatus, 
    RecipientStatus, CampaignType
)
from app.models.call import Call
from app.models.phone_number import PhoneNumber
from app.services.telnyx_service import TelnyxService

telnyx.api_key = settings.TELNYX_API_KEY


class BulkCampaignService:
    """Service for managing bulk calling and messaging campaigns"""
    
    @staticmethod
    def create_campaign(
        db: Session,
        user_id: int,
        campaign_data: Dict[str, Any]
    ) -> BulkCampaign:
        """Create a new bulk campaign"""
        # Remove user_id from campaign_data if it exists to avoid duplicate
        campaign_data = campaign_data.copy()
        campaign_data.pop('user_id', None)
        
        campaign = BulkCampaign(
            user_id=user_id,
            **campaign_data
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign
    
    @staticmethod
    def add_recipients(
        db: Session,
        campaign_id: int,
        recipients: List[Dict[str, Any]]
    ) -> List[CampaignRecipient]:
        """Add recipients to a campaign"""
        campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
        if not campaign:
            raise ValueError("Campaign not found")
        
        recipient_objects = []
        for recipient_data in recipients:
            recipient = CampaignRecipient(
                campaign_id=campaign_id,
                **recipient_data
            )
            recipient_objects.append(recipient)
            db.add(recipient)
        
        campaign.total_recipients = len(recipient_objects)
        db.commit()
        
        for r in recipient_objects:
            db.refresh(r)
        
        return recipient_objects
    
    @staticmethod
    async def start_campaign(
        db: Session,
        campaign_id: int
    ) -> Dict[str, Any]:
        """Start executing a bulk campaign"""
        campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign.status != CampaignStatus.DRAFT and campaign.status != CampaignStatus.SCHEDULED:
            raise ValueError(f"Campaign is already {campaign.status}")
        
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = datetime.utcnow()
        db.commit()
        
        # Start processing in background
        asyncio.create_task(
            BulkCampaignService._process_campaign(db, campaign_id)
        )
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "status": "running",
            "total_recipients": campaign.total_recipients
        }
    
    @staticmethod
    async def _process_campaign(db: Session, campaign_id: int):
        """Process campaign recipients (runs in background)"""
        campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
        if not campaign:
            return
        
        phone_number = db.query(PhoneNumber).filter(
            PhoneNumber.id == campaign.phone_number_id
        ).first()
        
        if not phone_number:
            campaign.status = CampaignStatus.FAILED
            db.commit()
            return
        
        recipients = db.query(CampaignRecipient).filter(
            and_(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == RecipientStatus.PENDING
            )
        ).all()
        
        calls_this_minute = 0
        calls_this_hour = 0
        minute_start = datetime.utcnow()
        hour_start = datetime.utcnow()
        
        active_tasks = set()
        
        for recipient in recipients:
            db.refresh(campaign)
            if campaign.status == CampaignStatus.PAUSED:
                break
            
            now = datetime.utcnow()
            
            if (now - minute_start).total_seconds() >= 60:
                calls_this_minute = 0
                minute_start = now
            
            if (now - hour_start).total_seconds() >= 3600:
                calls_this_hour = 0
                hour_start = now
            
            if calls_this_minute >= campaign.calls_per_minute:
                await asyncio.sleep(60 - (now - minute_start).total_seconds())
                calls_this_minute = 0
                minute_start = datetime.utcnow()
            
            if calls_this_hour >= campaign.calls_per_hour:
                sleep_time = 3600 - (now - hour_start).total_seconds()
                await asyncio.sleep(sleep_time)
                calls_this_hour = 0
                hour_start = datetime.utcnow()
            
            while len(active_tasks) >= campaign.concurrent_calls:
                done, active_tasks = await asyncio.wait(
                    active_tasks, 
                    return_when=asyncio.FIRST_COMPLETED
                )
            
            if campaign.campaign_type == CampaignType.VOICE or campaign.campaign_type == CampaignType.BOTH:
                task = asyncio.create_task(
                    BulkCampaignService._make_call(
                        db, campaign, recipient, phone_number.phone_number
                    )
                )
                active_tasks.add(task)
                calls_this_minute += 1
                calls_this_hour += 1
            
            if campaign.campaign_type == CampaignType.SMS or campaign.campaign_type == CampaignType.BOTH:
                await BulkCampaignService._send_sms(
                    db, campaign, recipient, phone_number.phone_number
                )
        
        if active_tasks:
            await asyncio.wait(active_tasks)
        
        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = datetime.utcnow()
        
        campaign.completed_count = db.query(CampaignRecipient).filter(
            and_(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == RecipientStatus.COMPLETED
            )
        ).count()
        
        campaign.failed_count = db.query(CampaignRecipient).filter(
            and_(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == RecipientStatus.FAILED
            )
        ).count()
        
        db.commit()
    
    @staticmethod
    async def _make_call(
        db: Session,
        campaign: BulkCampaign,
        recipient: CampaignRecipient,
        from_number: str
    ):
        """Make an individual call"""
        try:
            recipient.status = RecipientStatus.IN_PROGRESS
            recipient.attempts += 1
            recipient.last_attempt_at = datetime.utcnow()
            db.commit()
            
            voice_message = campaign.voice_message
            if campaign.enable_sms_personalization and recipient.name:
                voice_message = voice_message.replace("{{name}}", recipient.name)
            
            call_result = TelnyxService.make_call(
                to_number=recipient.phone_number,
                from_number=from_number,
                webhook_url=settings.TELNYX_VOICE_WEBHOOK_URL
            )
            
            if call_result:
                call = Call(
                    user_id=campaign.user_id,
                    phone_number_id=campaign.phone_number_id,
                    ai_agent_id=campaign.ai_agent_id,
                    call_control_id=call_result.get("call_control_id"),
                    telnyx_call_id=call_result.get("call_session_id"),
                    direction="outbound",
                    from_number=from_number,
                    to_number=recipient.phone_number,
                    status="initiated"
                )
                db.add(call)
                db.commit()
                
                recipient.call_id = call.id
                recipient.status = RecipientStatus.COMPLETED
                recipient.completed_at = datetime.utcnow()
                
                if voice_message:
                    await asyncio.sleep(2)
                    TelnyxService.speak_text(
                        call_result.get("call_control_id"),
                        voice_message
                    )
                
                campaign.success_count += 1
            else:
                recipient.status = RecipientStatus.FAILED
                recipient.error_message = "Failed to initiate call"
                campaign.failed_count += 1
            
            db.commit()
            
        except Exception as e:
            print(f"Error making call to {recipient.phone_number}: {e}")
            recipient.status = RecipientStatus.FAILED
            recipient.error_message = str(e)
            campaign.failed_count += 1
            db.commit()
    
    @staticmethod
    async def _send_sms(
        db: Session,
        campaign: BulkCampaign,
        recipient: CampaignRecipient,
        from_number: str
    ):
        """Send an individual SMS"""
        try:
            recipient.status = RecipientStatus.IN_PROGRESS
            recipient.attempts += 1
            recipient.last_attempt_at = datetime.utcnow()
            db.commit()
            
            sms_message = campaign.sms_message
            if campaign.enable_sms_personalization:
                if recipient.name:
                    sms_message = sms_message.replace("{{name}}", recipient.name)
                if recipient.custom_data:
                    for key, value in recipient.custom_data.items():
                        sms_message = sms_message.replace(f"{{{{{key}}}}}", str(value))
            
            result = TelnyxService.send_sms(
                to_number=recipient.phone_number,
                from_number=from_number,
                text=sms_message,
                webhook_url=settings.TELNYX_MSG_WEBHOOK_URL
            )
            
            if result:
                recipient.message_id = result.get("id")
                recipient.message_status = "sent"
                recipient.status = RecipientStatus.COMPLETED
                recipient.completed_at = datetime.utcnow()
                campaign.success_count += 1
            else:
                recipient.status = RecipientStatus.FAILED
                recipient.error_message = "Failed to send SMS"
                campaign.failed_count += 1
            
            db.commit()
            
        except Exception as e:
            print(f"Error sending SMS to {recipient.phone_number}: {e}")
            recipient.status = RecipientStatus.FAILED
            recipient.error_message = str(e)
            campaign.failed_count += 1
            db.commit()
    
    @staticmethod
    def pause_campaign(db: Session, campaign_id: int) -> Dict[str, Any]:
        """Pause a running campaign"""
        campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign.status != CampaignStatus.RUNNING:
            raise ValueError("Campaign is not running")
        
        campaign.status = CampaignStatus.PAUSED
        db.commit()
        
        return {"success": True, "status": "paused"}
    
    @staticmethod
    def resume_campaign(db: Session, campaign_id: int) -> Dict[str, Any]:
        """Resume a paused campaign"""
        campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign.status != CampaignStatus.PAUSED:
            raise ValueError("Campaign is not paused")
        
        campaign.status = CampaignStatus.RUNNING
        db.commit()
        
        asyncio.create_task(
            BulkCampaignService._process_campaign(db, campaign_id)
        )
        
        return {"success": True, "status": "running"}
    
    @staticmethod
    def get_campaign_stats(db: Session, campaign_id: int) -> Dict[str, Any]:
        """Get campaign statistics"""
        campaign = db.query(BulkCampaign).filter(BulkCampaign.id == campaign_id).first()
        if not campaign:
            raise ValueError("Campaign not found")
        
        pending = db.query(CampaignRecipient).filter(
            and_(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == RecipientStatus.PENDING
            )
        ).count()
        
        in_progress = db.query(CampaignRecipient).filter(
            and_(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.status == RecipientStatus.IN_PROGRESS
            )
        ).count()
        
        return {
            "campaign_id": campaign_id,
            "name": campaign.name,
            "status": campaign.status,
            "total_recipients": campaign.total_recipients,
            "pending": pending,
            "in_progress": in_progress,
            "completed": campaign.completed_count,
            "failed": campaign.failed_count,
            "success": campaign.success_count,
            "success_rate": (campaign.success_count / campaign.total_recipients * 100) if campaign.total_recipients > 0 else 0,
            "estimated_cost": campaign.estimated_cost,
            "actual_cost": campaign.actual_cost,
            "started_at": campaign.started_at,
            "completed_at": campaign.completed_at
        }