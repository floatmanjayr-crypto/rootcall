from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Call(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), nullable=False)
    ai_agent_id = Column(Integer, ForeignKey("ai_agents.id"), nullable=True)
    
    # Call details
    call_control_id = Column(String, unique=True, index=True)
    telnyx_call_id = Column(String, unique=True)
    direction = Column(String)  # inbound, outbound
    from_number = Column(String)
    to_number = Column(String)
    
    # Status
    status = Column(String)  # initiated, ringing, answered, completed, failed
    duration = Column(Integer, default=0)  # in seconds
    
    # Cost
    cost = Column(Float, default=0.0)
    
    # AI features
    transcription = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment = Column(String, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="calls")
    phone_number = relationship("PhoneNumber", back_populates="calls")
    ai_agent = relationship("AIAgent", back_populates="agent_calls")
    recordings = relationship("Recording", back_populates="call")

# === RootCall screening fields - ADD THESE ===
    
    # Screening results
    is_trusted = Column(Boolean, default=False)  # Was caller on whitelist?
    is_spam = Column(Boolean, default=False)  # Was call blocked as spam?
    screening_action = Column(String, nullable=True)  # trusted_transfer, spam_blocked, retell_transfer, unknown_forward
    
    # Caller identification
    caller_name = Column(String, nullable=True)  # CNAM or contact name
    spam_score = Column(Integer, nullable=True)  # 0-100 spam likelihood
    
    # RootCall AI interaction (if went to Retell)
    retell_call_id = Column(String, nullable=True)  # Retell's call ID
    rootcall_transcript = Column(Text, nullable=True)  # What RootCall said/heard
    scam_detected = Column(Boolean, default=False)  # Did RootCall detect scam?
    scam_type = Column(String, nullable=True)  # irs, bank, tech_support, etc.
