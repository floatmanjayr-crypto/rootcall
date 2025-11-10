"""Interactive Voice Response (IVR) System Models"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from app.database import Base


class IVRNodeType(str, Enum):
    GREETING = "greeting"
    MENU = "menu"
    GATHER_INPUT = "gather_input"
    TRANSFER = "transfer"
    VOICEMAIL = "voicemail"
    AI_AGENT = "ai_agent"
    HANGUP = "hangup"
    PLAY_AUDIO = "play_audio"
    TEXT_TO_SPEECH = "text_to_speech"
    BUSINESS_HOURS = "business_hours"
    CALLBACK = "callback"


class IVRFlow(Base):
    """Main IVR flow configuration"""
    __tablename__ = "ivr_flows"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), nullable=True)
    
    name = Column(String, nullable=False)
    description = Column(Text)
    entry_node_id = Column(Integer, nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)
    
    total_calls_handled = Column(Integer, default=0)
    avg_call_duration = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", backref="ivr_flows")
    phone_number = relationship("PhoneNumber", backref="ivr_flow")
    nodes = relationship("IVRNode", back_populates="flow", cascade="all, delete-orphan", foreign_keys="IVRNode.flow_id")


class IVRNode(Base):
    """Individual node in IVR flow"""
    __tablename__ = "ivr_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("ivr_flows.id"), nullable=False)
    
    node_type = Column(SQLEnum(IVRNodeType), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    
    config = Column(JSON, nullable=False)
    
    timeout_seconds = Column(Integer, default=10)
    timeout_node_id = Column(Integer, ForeignKey("ivr_nodes.id"), nullable=True)
    error_node_id = Column(Integer, ForeignKey("ivr_nodes.id"), nullable=True)
    
    times_visited = Column(Integer, default=0)
    avg_time_spent = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Fixed with foreign_keys parameter
    flow = relationship("IVRFlow", back_populates="nodes", foreign_keys=[flow_id])
    actions = relationship("IVRAction", back_populates="node", cascade="all, delete-orphan", foreign_keys="IVRAction.node_id")


class IVRAction(Base):
    """Actions/transitions between IVR nodes"""
    __tablename__ = "ivr_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("ivr_nodes.id"), nullable=False)
    
    trigger = Column(String, nullable=False)
    next_node_id = Column(Integer, ForeignKey("ivr_nodes.id"), nullable=True)
    
    conditions = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - Fixed with foreign_keys parameter
    node = relationship("IVRNode", back_populates="actions", foreign_keys=[node_id])


class IVRCallLog(Base):
    """Track caller journey through IVR"""
    __tablename__ = "ivr_call_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    flow_id = Column(Integer, ForeignKey("ivr_flows.id"), nullable=False)
    
    nodes_visited = Column(JSON, nullable=False)
    inputs_collected = Column(JSON, nullable=True)
    
    final_action = Column(String, nullable=True)
    transferred_to = Column(String, nullable=True)
    
    total_duration = Column(Integer, default=0)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # Relationships
    call = relationship("Call", backref="ivr_log")
    flow = relationship("IVRFlow", backref="call_logs")


class BusinessHours(Base):
    """Business hours configuration for IVR routing"""
    __tablename__ = "business_hours"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String, nullable=False)
    timezone = Column(String, default="America/New_York")
    
    schedule = Column(JSON, nullable=False)
    holidays = Column(JSON, nullable=True)
    
    open_hours_flow_id = Column(Integer, ForeignKey("ivr_flows.id"), nullable=True)
    closed_hours_flow_id = Column(Integer, ForeignKey("ivr_flows.id"), nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="business_hours")
