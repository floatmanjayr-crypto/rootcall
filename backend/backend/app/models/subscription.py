"""Subscription and Feature Management Models"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from app.database import Base


class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class FeatureType(str, Enum):
    AI_AGENT = "ai_agent"
    OUTBOUND_CALLS = "outbound_calls"
    INBOUND_CALLS = "inbound_calls"
    BULK_CAMPAIGNS = "bulk_campaigns"
    CALL_RECORDING = "call_recording"
    TRANSCRIPTION = "transcription"
    IVR_SYSTEM = "ivr_system"
    SMS = "sms"
    ANALYTICS = "analytics"
    API_ACCESS = "api_access"


class Subscription(Base):
    """User subscription plan"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Plan details
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE)
    monthly_price = Column(Float, default=0.0)
    
    # Usage limits
    monthly_minutes_included = Column(Integer, default=0)
    monthly_minutes_used = Column(Integer, default=0)
    additional_minute_rate = Column(Float, default=0.02)
    
    max_phone_numbers = Column(Integer, default=1)
    max_campaigns_per_month = Column(Integer, default=0)
    max_concurrent_calls = Column(Integer, default=1)
    
    # Billing
    stripe_subscription_id = Column(String, nullable=True)
    billing_cycle_start = Column(DateTime, default=datetime.utcnow)
    billing_cycle_end = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    trial_ends_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    canceled_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    features = relationship("UserFeature", back_populates="subscription", cascade="all, delete-orphan")


class UserFeature(Base):
    """Individual features enabled for a user"""
    __tablename__ = "user_features"
    
    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    
    # Feature details
    feature_type = Column(SQLEnum(FeatureType), nullable=False)
    is_enabled = Column(Boolean, default=True)
    
    # Feature-specific limits
    monthly_limit = Column(Integer, nullable=True)  # e.g., 1000 minutes, 500 calls
    current_usage = Column(Integer, default=0)
    
    # Pricing (if feature has separate pricing)
    monthly_cost = Column(Float, default=0.0)
    per_use_cost = Column(Float, nullable=True)  # Cost per minute/call/SMS
    
    # Configuration
    config = Column(JSON, nullable=True)  # Feature-specific settings
    
    # Timestamps
    enabled_at = Column(DateTime, default=datetime.utcnow)
    disabled_at = Column(DateTime, nullable=True)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="features")


class UsageLog(Base):
    """Track feature usage for billing"""
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Usage details
    feature_type = Column(SQLEnum(FeatureType), nullable=False)
    resource_id = Column(String, nullable=True)  # call_id, campaign_id, etc.
    
    # Quantity
    quantity = Column(Float, nullable=False)  # minutes, calls, SMS count
    unit = Column(String, nullable=False)  # "minutes", "calls", "messages"
    
    # Cost
    unit_cost = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    
    # Metadata - RENAMED from 'metadata' to 'meta_data' to avoid SQLAlchemy conflict
    meta_data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="usage_logs")
