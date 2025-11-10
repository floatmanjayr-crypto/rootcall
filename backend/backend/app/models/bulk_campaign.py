from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from app.database import Base


class CampaignType(str, Enum):
    VOICE = "voice"
    SMS = "sms"
    BOTH = "both"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RecipientStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BulkCampaign(Base):
    __tablename__ = "bulk_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), nullable=False)
    ai_agent_id = Column(Integer, ForeignKey("ai_agents.id"), nullable=True)

    # Campaign details
    name = Column(String, nullable=False)
    description = Column(Text)
    campaign_type = Column(SQLEnum(CampaignType), nullable=False)
    
    # Voice settings
    voice_message = Column(Text, nullable=True)
    voice_audio_url = Column(String, nullable=True)
    max_call_duration = Column(Integer, default=300)
    enable_voicemail_detection = Column(Boolean, default=True)
    leave_voicemail = Column(Boolean, default=True)
    voicemail_message = Column(Text, nullable=True)
    
    # SMS settings
    sms_message = Column(Text, nullable=True)
    enable_sms_personalization = Column(Boolean, default=True)
    
    # Scheduling
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    timezone = Column(String, default="America/New_York")
    
    # Rate limiting
    calls_per_minute = Column(Integer, default=10)
    calls_per_hour = Column(Integer, default=100)
    concurrent_calls = Column(Integer, default=5)
    
    # Retry logic
    max_retry_attempts = Column(Integer, default=2)
    retry_delay_minutes = Column(Integer, default=30)
    retry_on_no_answer = Column(Boolean, default=True)
    retry_on_busy = Column(Boolean, default=True)
    
    # Status and stats
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    total_recipients = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    
    # Cost tracking
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float, default=0.0)
    
    # Advanced settings
    require_confirmation = Column(Boolean, default=False)
    record_calls = Column(Boolean, default=True)
    transcribe_calls = Column(Boolean, default=False)
    collect_dtmf = Column(Boolean, default=False)
    dtmf_options = Column(JSON, nullable=True)
    
    # Compliance
    respect_dnc = Column(Boolean, default=True)
    quiet_hours_start = Column(String, default="21:00")
    quiet_hours_end = Column(String, default="08:00")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="bulk_campaigns")
    phone_number = relationship("PhoneNumber", backref="bulk_campaigns")
    ai_agent = relationship("AIAgent", backref="bulk_campaigns")
    recipients = relationship("CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan")


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("bulk_campaigns.id"), nullable=False)
    
    # Recipient info
    phone_number = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    custom_data = Column(JSON, nullable=True)
    
    # Status tracking
    status = Column(SQLEnum(RecipientStatus), default=RecipientStatus.PENDING)
    attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    
    # Call results
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=True)
    call_duration = Column(Integer, nullable=True)
    call_status = Column(String, nullable=True)
    voicemail_detected = Column(Boolean, default=False)
    dtmf_response = Column(String, nullable=True)
    
    # SMS results
    message_id = Column(String, nullable=True)
    message_status = Column(String, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    
    # Cost
    cost = Column(Float, default=0.0)
    
    # Notes and errors
    notes = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    campaign = relationship("BulkCampaign", back_populates="recipients")
    call = relationship("Call", backref="campaign_recipient")


class CampaignTemplate(Base):
    __tablename__ = "campaign_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String, nullable=False)
    description = Column(Text)
    campaign_type = Column(SQLEnum(CampaignType), nullable=False)
    
    # Template content
    voice_message = Column(Text, nullable=True)
    sms_message = Column(Text, nullable=True)
    
    # Default settings
    settings = Column(JSON, nullable=True)
    
    # Usage tracking
    times_used = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="campaign_templates")
