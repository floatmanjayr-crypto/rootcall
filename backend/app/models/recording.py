from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Recording(Base):
    __tablename__ = "recordings"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Recording details
    recording_id = Column(String, unique=True, index=True)
    file_url = Column(String)
    file_path = Column(String)
    duration = Column(Integer)  # in seconds
    file_size = Column(Integer)  # in bytes
    
    # Storage
    storage_type = Column(String, default="s3")  # s3, local, gcs
    s3_bucket = Column(String, nullable=True)
    s3_key = Column(String, nullable=True)
    
    # Processing
    is_transcribed = Column(Boolean, default=False)
    transcription_status = Column(String, default="pending")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", back_populates="recordings")
    user = relationship("User", back_populates="recordings")
