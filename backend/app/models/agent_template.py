"""Pre-filled Agent Templates for Quick Setup"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class AgentTemplate(Base):
    """Pre-built AI agent templates"""
    __tablename__ = "agent_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Template details
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # plumbing, insurance, restaurant, etc.
    description = Column(Text)
    
    # Pre-filled content
    system_prompt = Column(Text, nullable=False)
    greeting_message = Column(Text, nullable=False)
    sample_questions = Column(JSON, nullable=True)  # Example questions customers might ask
    
    # Voice settings
    recommended_voice = Column(String, default="11labs-Adrian")
    language = Column(String, default="en-US")
    
    # Template metadata
    use_count = Column(Integer, default=0)  # Track popularity
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)  # Premium templates
    
    # Tags for filtering
    tags = Column(JSON, nullable=True)  # ["emergency", "24/7", "appointment-booking"]
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
