from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class AIAgent(Base):
    __tablename__ = "ai_agents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Agent details
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Retell.ai Integration
    retell_agent_id = Column(String, unique=True, nullable=True, index=True)  # NEW
    retell_llm_id = Column(String, nullable=True)  # NEW
    
    # Voice settings
    voice_model = Column(String, default="en-US-Neural2-F")  # Google TTS voice
    language = Column(String, default="en-US")
    speaking_rate = Column(Float, default=1.0)
    pitch = Column(Float, default=0.0)
    
    # AI settings
    ai_model = Column(String, default="gpt-4")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=150)
    
    # System prompt and personality
    system_prompt = Column(Text, nullable=False)
    greeting_message = Column(Text)
    
    # Agent behavior
    agent_type = Column(String, default="conversational")  # conversational, appointment, survey, support
    transfer_on_keywords = Column(Text)  # JSON list of keywords to transfer to human
    max_call_duration = Column(Integer, default=600)  # seconds
    
    # Advanced features
    collect_voicemail = Column(Boolean, default=False)
    send_transcripts = Column(Boolean, default=True)
    enable_interruptions = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="ai_agents")
    phone_numbers = relationship("PhoneNumber", back_populates="ai_agent")
    agent_calls = relationship("Call", back_populates="ai_agent")
