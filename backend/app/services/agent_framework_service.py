"""
Service wrapper for Agent Framework
Integrates the multi-agent system with our VoIP platform
"""
from typing import Dict, Any, Optional, List
from app.agent_framework.core.orchestrator import MasterOrchestrator
from app.agent_framework.core.config import FrameworkConfig, AgentConfig
from app.config import settings


class AgentFrameworkService:
    """Wrapper service for the agent framework"""
    
    _instance: Optional['AgentFrameworkService'] = None
    _orchestrator: Optional[MasterOrchestrator] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._orchestrator is None:
            self._initialize_framework()
    
    def _initialize_framework(self):
        """Initialize the agent framework with configuration"""
        config = FrameworkConfig(
            telnyx_api_key=settings.TELNYX_API_KEY or "dummy_key",
            openai_api_key=settings.OPENAI_API_KEY or "dummy_key",
            voice_agent=AgentConfig(
                model="gpt-4",
                temperature=0.7,
                max_tokens=800
            ),
            messaging_agent=AgentConfig(
                model="gpt-4",
                temperature=0.7,
                max_tokens=500
            ),
            ai_agent=AgentConfig(
                model="gpt-4",
                temperature=0.8,
                max_tokens=1000
            ),
            storage_agent=AgentConfig(
                model="gpt-4",
                temperature=0.5,
                max_tokens=500
            ),
            flow_designer_agent=AgentConfig(
                model="gpt-4",
                temperature=0.7,
                max_tokens=1500
            )
        )
        
        self._orchestrator = MasterOrchestrator(config)
    
    async def generate_call_flow(
        self,
        user_id: int,
        requirements: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete call flow from natural language description
        
        Args:
            user_id: User ID
            requirements: Natural language description of flow requirements
            context: Additional context (phone numbers, etc.)
        
        Returns:
            Dict with flow design, code, and documentation
        """
        result = await self._orchestrator.execute_task(
            user_id=user_id,
            request=f"Design a call flow with these requirements: {requirements}",
            task_type="flow_design",
            context=context
        )
        
        return result
    
    async def create_ai_voice_agent(
        self,
        user_id: int,
        purpose: str,
        tone: str = "professional",
        requirements: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create an AI voice agent configuration
        
        Args:
            user_id: User ID
            purpose: Purpose of the agent
            tone: Tone of voice (professional, friendly, casual, formal)
            requirements: List of specific requirements
        
        Returns:
            Dict with agent design including system prompt, settings, etc.
        """
        result = await self._orchestrator.create_ai_agent(
            user_id=user_id,
            purpose=purpose,
            tone=tone,
            requirements=requirements or []
        )
        
        return result
    
    async def optimize_agent_prompt(
        self,
        user_id: int,
        current_prompt: str,
        performance_data: Dict[str, Any],
        transcripts: List[str]
    ) -> Dict[str, Any]:
        """
        Optimize an existing agent prompt based on performance data
        
        Args:
            user_id: User ID
            current_prompt: Current system prompt
            performance_data: Performance metrics
            transcripts: Sample call transcripts
        
        Returns:
            Dict with analysis and optimized prompt
        """
        result = await self._orchestrator.execute_task(
            user_id=user_id,
            request=f"""Optimize this AI agent prompt based on performance data:
            
Current Prompt: {current_prompt}
Performance: {performance_data}
Sample Transcripts: {transcripts[:3]}

Provide an optimized prompt and explain improvements.""",
            task_type="prompt_optimization",
            context={
                "current_prompt": current_prompt,
                "performance_data": performance_data,
                "transcripts": transcripts
            }
        )
        
        return result
    
    async def design_ivr_system(
        self,
        user_id: int,
        business_goal: str,
        menu_options: List[str],
        phone_number: str
    ) -> Dict[str, Any]:
        """
        Design an IVR (Interactive Voice Response) system
        
        Args:
            user_id: User ID
            business_goal: What the IVR should accomplish
            menu_options: List of menu options
            phone_number: Phone number to assign IVR to
        
        Returns:
            Dict with IVR design, TeXML, and implementation code
        """
        result = await self._orchestrator.execute_task(
            user_id=user_id,
            request=f"""Design an IVR system:
            
Business Goal: {business_goal}
Menu Options: {', '.join(menu_options)}
Phone Number: {phone_number}

Create a complete IVR with TeXML and Python implementation.""",
            task_type="ivr_design",
            context={"phone_number": phone_number}
        )
        
        return result
    
    async def create_messaging_campaign(
        self,
        user_id: int,
        campaign_goal: str,
        audience: str,
        message_template: str
    ) -> Dict[str, Any]:
        """
        Design an automated messaging campaign
        
        Args:
            user_id: User ID
            campaign_goal: Goal of the campaign
            audience: Target audience description
            message_template: Initial message template
        
        Returns:
            Dict with campaign design and implementation
        """
        result = await self._orchestrator.execute_task(
            user_id=user_id,
            request=f"""Design a messaging campaign:
            
Goal: {campaign_goal}
Audience: {audience}
Template: {message_template}

Create a multi-step campaign with triggers and personalization.""",
            task_type="messaging_campaign",
            context={"message_template": message_template}
        )
        
        return result
    
    async def analyze_conversation(
        self,
        user_id: int,
        transcript: str
    ) -> Dict[str, Any]:
        """
        Analyze a call transcript for insights
        
        Args:
            user_id: User ID
            transcript: Call transcript
        
        Returns:
            Dict with sentiment, intent, entities, and summary
        """
        result = await self._orchestrator.execute_task(
            user_id=user_id,
            request=f"""Analyze this conversation transcript:
            
{transcript}

Extract:
1. Primary intent and secondary intents
2. Sentiment (positive/negative/neutral)
3. Key entities (names, dates, amounts, etc.)
4. Action items
5. Summary (2-3 sentences)
6. Customer satisfaction score (1-10)""",
            task_type="conversation_analysis"
        )
        
        return result
    
    def get_framework_status(self) -> Dict[str, Any]:
        """Get status of the agent framework"""
        if self._orchestrator:
            return self._orchestrator.get_agent_status()
        return {"status": "not_initialized"}
    
    async def custom_request(
        self,
        user_id: int,
        request: str,
        task_type: str = "general",
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send a custom request to the agent framework
        
        Args:
            user_id: User ID
            request: Natural language request
            task_type: Type of task
            context: Additional context
        
        Returns:
            Result from the orchestrator
        """
        result = await self._orchestrator.execute_task(
            user_id=user_id,
            request=request,
            task_type=task_type,
            context=context
        )
        
        return result


# Singleton instance
agent_framework_service = AgentFrameworkService()
