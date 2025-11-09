from sqlalchemy import Column, Integer, String, UniqueConstraint
from app.database import Base

class ClientMapping(Base):
    __tablename__ = "client_mappings"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, nullable=False, unique=True, index=True)
    voice_connection_id = Column(String, nullable=False)
    messaging_profile_id = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint("client_id", name="uq_client_id"),)
