from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)
    starts_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    timezone = Column(String, default="America/New_York")
    status = Column(String, default="pending")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
