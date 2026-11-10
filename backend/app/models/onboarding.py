from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String

from app.database import Base


class CustomerOnboarding(Base):
    __tablename__ = "customer_onboarding"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    forwarding_number = Column(String(16), nullable=True)
    voice_id = Column(String(200), nullable=True)
    shield_number = Column(String(16), unique=True, nullable=True)
    trusted_contacts = Column(JSON, nullable=True)
    tier = Column(String(20), nullable=True)
    checkout_key = Column(String(64), nullable=False)
    checkout_session_id = Column(String(255), unique=True, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    payment_status = Column(String(30), nullable=False, default="pending")
    subscription_status = Column(String(30), nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    billing_checked_at = Column(DateTime, nullable=True)
    payment_issue_since = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="draft")
    activation_stage = Column(String(100), nullable=True)
    activation_updated_at = Column(DateTime, nullable=True)
    uncertain_operation = Column(String(40), nullable=True)
    recovery_reviewed_at = Column(DateTime, nullable=True)
    recovery_reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    recovery_note = Column(String(500), nullable=True)
    service_setup = Column(JSON, nullable=True)
    order_attempted = Column(Boolean, nullable=False, default=False)
    connection_id = Column(String(255), nullable=True)
    llm_id = Column(String(255), nullable=True)
    agent_id = Column(String(255), nullable=True)
    transfer_ready = Column(Boolean, nullable=False, default=False)
    number_imported = Column(Boolean, nullable=False, default=False)
    error_message = Column(String(500), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
