from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class PhoneNumber(Base):
    __tablename__ = "phone_numbers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Phone details
    phone_number = Column(String, unique=True, index=True, nullable=False)
    friendly_name = Column(String)
    country_code = Column(String, default="US")
    
    # Telnyx details
    telnyx_phone_number_id = Column(String, unique=True)
    telnyx_connection_id = Column(String)
    
    # AI Agent assignment
    ai_agent_id = Column(Integer, ForeignKey("ai_agents.id"), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    monthly_cost = Column(Float, default=1.0)
    
    # Timestamps
    purchased_at = Column(DateTime, default=datetime.utcnow)
    released_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="phone_numbers")
    ai_agent = relationship("AIAgent", back_populates="phone_numbers")
    calls = relationship("Call", back_populates="phone_number")
