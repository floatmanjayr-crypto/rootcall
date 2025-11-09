"""
Agent Framework Configuration
"""
from typing import Dict, Any
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for individual agents"""
    model: str = Field(default="gpt-4", description="LLM model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=500, ge=1, le=4000)
    timeout: int = Field(default=30, description="Timeout in seconds")


class FrameworkConfig(BaseModel):
    """Global framework configuration"""
    # API Keys
    telnyx_api_key: str
    openai_api_key: str
    
    # Agent Configs
    voice_agent: AgentConfig = Field(default_factory=AgentConfig)
    messaging_agent: AgentConfig = Field(default_factory=AgentConfig)
    ai_agent: AgentConfig = Field(default_factory=AgentConfig)
    storage_agent: AgentConfig = Field(default_factory=AgentConfig)
    flow_designer_agent: AgentConfig = Field(default_factory=AgentConfig)
    
    # Knowledge Base
    enable_rag: bool = Field(default=True)
    vector_db_path: str = Field(default="./vector_store")
    
    # LangGraph
    max_iterations: int = Field(default=10)
    enable_memory: bool = Field(default=True)
    
    class Config:
        arbitrary_types_allowed = True


# Default constants
AGENT_ROLES = {
    "orchestrator": "Master coordinator that routes tasks to specialist agents",
    "voice": "Handles Telnyx Voice API operations (calls, conferencing, IVR)",
    "messaging": "Manages SMS/MMS campaigns and messaging workflows",
    "ai": "Processes AI inference, transcription, and NLP tasks",
    "storage": "Manages cloud storage, recordings, and media files",
    "flow_designer": "Designs and generates call flow architectures"
}

TELNYX_CAPABILITIES = [
    "voice_calls",
    "call_control",
    "sms_messaging",
    "mms_messaging",
    "number_lookup",
    "verify_api",
    "texml",
    "fax",
    "wireless",
    "messaging_profiles",
    "call_recording",
    "transcription"
]
