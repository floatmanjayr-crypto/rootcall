"""
State management for multi-agent system
"""
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
import operator


class AgentState(TypedDict):
    """Shared state across all agents"""
    # User request
    user_id: int
    request: str
    request_type: str  # "voice_call", "sms_campaign", "flow_design", etc.
    
    # Agent tracking
    current_agent: str
    agent_history: List[str]
    
    # Task execution
    task_id: str
    status: str  # "pending", "in_progress", "completed", "failed"
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    
    # Conversation context
    messages: Annotated[List[Dict], operator.add]
    intermediate_steps: Annotated[List[Dict], operator.add]
    
    # Telnyx resources
    phone_numbers: List[str]
    call_control_ids: List[str]
    messaging_profile_ids: List[str]
    
    # AI context
    ai_agent_id: Optional[int]
    system_prompt: Optional[str]
    conversation_history: List[Dict]
    
    # Metadata
    created_at: datetime
    updated_at: datetime


class VoiceTaskState(TypedDict):
    """State specific to voice tasks"""
    call_control_id: str
    from_number: str
    to_number: str
    call_status: str
    recording_enabled: bool
    transcription_enabled: bool
    ai_enabled: bool


class MessagingTaskState(TypedDict):
    """State specific to messaging tasks"""
    messaging_profile_id: str
    campaign_id: Optional[str]
    recipients: List[str]
    message_template: str
    delivery_status: Dict[str, str]


class FlowDesignTaskState(TypedDict):
    """State specific to flow design tasks"""
    flow_requirements: str
    generated_flow: Optional[Dict]
    flow_code: Optional[str]
    validation_result: Optional[Dict]
