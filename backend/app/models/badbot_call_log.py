"""
BadBot Call Logs Model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class BadBotCallLog(Base):
    __tablename__ = "badbot_call_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"))
    from_number = Column(String(20), nullable=False)
    caller_name = Column(String(255))
    action = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    call_control_id = Column(String(255))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
