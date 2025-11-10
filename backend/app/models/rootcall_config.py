"""
RootCall Configuration Model
Save as: app/models/rootcall_config.py

Stores RootCall screening configuration per phone number
Replaces hardcoded CLIENT_LINES dictionary
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class RootCallConfig(Base):
    """RootCall screening configuration for a phone number"""
    __tablename__ = "rootcall_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Client information
    client_name = Column(String, nullable=False)
    client_cell = Column(String, nullable=False)  # Where to transfer trusted/verified calls
    
    # Retell AI configuration
    retell_agent_id = Column(String, nullable=False)
    retell_did = Column(String, nullable=False)  # The DID that Retell uses
    
    # Trusted contacts (whitelist) - stored as JSON array
    # Example: ["+17545551234", "+18005551234"]
    trusted_contacts = Column(JSON, default=list)
    
    # SMS alerts configuration
    caregiver_cell = Column(String, nullable=True)  # Optional: receives SMS alerts
    sms_alerts_enabled = Column(Boolean, default=True)
    alert_on_spam = Column(Boolean, default=True)
    alert_on_unknown = Column(Boolean, default=False)
    
    # Screening settings
    auto_block_spam = Column(Boolean, default=True)
    require_caller_name = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    phone_number = relationship("PhoneNumber", backref="rootcall_config")
    user = relationship("User", backref="rootcall_configs")


class TrustedContact(Base):
    """Individual trusted contact (alternative to JSON array)"""
    __tablename__ = "trusted_contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    rootcall_config_id = Column(Integer, ForeignKey("rootcall_configs.id"), nullable=False)
    
    # Contact details
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    relationship_type = Column(String)  # family, friend, doctor, etc.
    notes = Column(String, nullable=True)
    
    # Statistics
    total_calls = Column(Integer, default=0)
    last_call_at = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rootcall_config = relationship("RootCallConfig", backref="trusted_contacts_list")# [PASTE THE CONTENT FROM rootcall_config_model.py HERE]

