from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class ActivationJob(Base):
    __tablename__ = "activation_jobs"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_error = Column(String(500), nullable=True)
