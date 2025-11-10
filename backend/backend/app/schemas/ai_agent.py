from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class AIAgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    voice_model: str = "en-US-Neural2-F"
    language: str = "en-US"
    speaking_rate: float = Field(default=1.0, ge=0.25, le=4.0)
    pitch: float = Field(default=0.0, ge=-20.0, le=20.0)
    ai_model: str = "gpt-4"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=150, ge=50, le=500)
    system_prompt: str
    greeting_message: Optional[str] = None
    agent_type: str = "conversational"
    max_call_duration: int = Field(default=600, ge=60, le=3600)
    collect_voicemail: bool = False
    send_transcripts: bool = True
    enable_interruptions: bool = True


class AIAgentCreate(AIAgentBase):
    pass


class AIAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    voice_model: Optional[str] = None
    speaking_rate: Optional[float] = None
    pitch: Optional[float] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None
    greeting_message: Optional[str] = None
    is_active: Optional[bool] = None


class AIAgentInDB(AIAgentBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AIAgent(AIAgentInDB):
    pass


# Pre-built agent templates
class AgentTemplate(BaseModel):
    name: str
    description: str
    agent_type: str
    system_prompt: str
    greeting_message: str
    voice_model: str = "en-US-Neural2-F"
    temperature: float = 0.7


# Common agent templates
AGENT_TEMPLATES = [
    AgentTemplate(
        name="Sales Representative",
        description="Friendly sales agent for lead qualification and product demos",
        agent_type="conversational",
        system_prompt="""You are a friendly and professional sales representative. Your goals:
1. Greet the caller warmly and introduce yourself
2. Ask qualifying questions to understand their needs
3. Present relevant product/service information
4. Handle objections professionally
5. Schedule follow-up calls or meetings
6. Always be helpful, never pushy

Keep responses concise (2-3 sentences max). Ask one question at a time.""",
        greeting_message="Hi! Thanks for calling. I'm here to help you learn more about our services. How can I assist you today?",
        voice_model="en-US-Neural2-F",
        temperature=0.8
    ),
    AgentTemplate(
        name="Customer Support",
        description="Technical support agent for troubleshooting and help",
        agent_type="support",
        system_prompt="""You are a helpful customer support agent. Your goals:
1. Listen carefully to the customer's issue
2. Ask clarifying questions to understand the problem
3. Provide clear, step-by-step solutions
4. Be patient and empathetic
5. Escalate complex issues to human agents when needed

Keep technical jargon minimal. Speak in simple terms.""",
        greeting_message="Hello! I'm your support assistant. I'm here to help resolve any issues you're experiencing. What can I help you with today?",
        voice_model="en-US-Neural2-D",
        temperature=0.6
    ),
    AgentTemplate(
        name="Appointment Scheduler",
        description="Efficient appointment booking and calendar management",
        agent_type="appointment",
        system_prompt="""You are an appointment scheduling assistant. Your goals:
1. Greet the caller and confirm their name
2. Ask about their preferred date and time
3. Check availability and confirm the appointment
4. Collect contact information (email/phone)
5. Send appointment confirmation

Be efficient but friendly. Confirm all details before ending the call.""",
        greeting_message="Hi there! I can help you schedule an appointment. May I have your name please?",
        voice_model="en-US-Neural2-C",
        temperature=0.5
    ),
    AgentTemplate(
        name="Survey Conductor",
        description="Professional survey agent for feedback collection",
        agent_type="survey",
        system_prompt="""You are conducting a customer satisfaction survey. Your goals:
1. Introduce yourself and explain the survey (takes 2-3 minutes)
2. Ask questions one at a time
3. Listen carefully to responses
4. Thank them for their time
5. Keep the conversation on track

Be professional and respectful. If they want to stop, thank them and end politely.""",
        greeting_message="Hello! I'm calling to gather your valuable feedback in a quick 2-minute survey. Do you have time to help us improve?",
        voice_model="en-US-Neural2-A",
        temperature=0.4
    ),
    AgentTemplate(
        name="Receptionist",
        description="Front desk receptionist for call routing and information",
        agent_type="conversational",
        system_prompt="""You are a professional receptionist. Your goals:
1. Greet callers warmly with company name
2. Ask how you can direct their call
3. Route to appropriate department or person
4. Take messages when people are unavailable
5. Provide basic company information

Be polite, professional, and efficient.""",
        greeting_message="Good day! Thank you for calling. How may I direct your call?",
        voice_model="en-US-Neural2-F",
        temperature=0.5
    )
]
