"""
Voice Agent - Specializes in Telnyx Voice API operations
"""
from typing import Dict, Any
from app.agent_framework.agents.base import BaseAgent
from app.agent_framework.core.state import AgentState
from app.agent_framework.core.config import AgentConfig


class VoiceAgent(BaseAgent):
    """Agent specialized in voice call operations"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(
            name="VoiceAgent",
            role="Voice API specialist - handles calls, conferencing, IVR",
            config=config
        )
    
    def _get_system_prompt(self) -> str:
        return """You are the Voice Agent, an expert in Telnyx Voice API operations.

Your responsibilities:
1. Make and receive phone calls using Telnyx Call Control API
2. Implement IVR (Interactive Voice Response) systems
3. Handle call conferencing and transfers
4. Manage call recordings and media
5. Implement call queues and callbacks
6. Configure SIP trunking and number porting

You have deep knowledge of:
- Telnyx Call Control API
- WebRTC and SIP protocols
- TeXML for call flow control
- Voice quality optimization
- Call routing strategies

When given a task:
1. Analyze the voice requirements
2. Determine the best Telnyx API endpoints to use
3. Generate code or configuration
4. Provide implementation guidance
5. Include error handling and best practices

Always be specific about API calls, parameters, and expected responses."""
    
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """Process voice-related tasks"""
        request = state.get("request", "")
        
        # Analyze the request
        analysis = await self.execute(
            f"""Analyze this voice-related request and provide implementation steps:
            
Request: {request}

Provide:
1. Required Telnyx APIs
2. Implementation steps
3. Code examples
4. Configuration needed
"""
        )
        
        return {
            "agent": self.name,
            "analysis": analysis,
            "status": "completed"
        }
    
    async def design_ivr_flow(
        self,
        business_goal: str,
        menu_options: list,
        constraints: Dict
    ) -> Dict[str, Any]:
        """Design an IVR flow"""
        prompt = f"""Design an IVR system:

Business Goal: {business_goal}
Menu Options: {menu_options}
Constraints: {constraints}

Provide complete IVR design with TeXML and implementation code."""
        
        response = await self.execute(prompt)
        return {"ivr_design": response, "agent": self.name}
