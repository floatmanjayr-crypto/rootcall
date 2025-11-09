"""
Flow Designer Agent - Creates and optimizes call/messaging flows
"""
from typing import Dict, Any, List
from app.agent_framework.agents.base import BaseAgent
from app.agent_framework.core.state import AgentState
from app.agent_framework.core.config import AgentConfig


class FlowDesignerAgent(BaseAgent):
    """Agent specialized in designing communication flows"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(
            name="FlowDesignerAgent",
            role="Integration architect - designs complex communication flows",
            config=config
        )
    
    def _get_system_prompt(self) -> str:
        return """You are the Flow Designer Agent, an expert in creating sophisticated communication flows.

Your responsibilities:
1. Design IVR (Interactive Voice Response) systems
2. Create multi-step messaging campaigns
3. Implement call routing logic
4. Design conversational flows for AI agents
5. Optimize flow efficiency and user experience

You have deep knowledge of:
- Call flow design patterns
- State machines and decision trees
- Conversational UX best practices

When designing flows:
1. Start with user goals and use cases
2. Map out all possible paths
3. Handle edge cases and errors
4. Optimize for user experience
5. Generate clean, maintainable code"""
    
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """Process flow design tasks"""
        request = state.get("request", "")
        
        analysis = await self.execute(
            f"""Design a communication flow for this requirement:
            
Request: {request}

Provide:
1. Flow diagram
2. Configuration (JSON)
3. Python implementation
4. Documentation
"""
        )
        
        return {
            "agent": self.name,
            "flow_design": analysis,
            "status": "completed"
        }
    
    async def design_ivr_flow(
        self,
        business_goal: str,
        menu_options: List[str],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Design an IVR flow"""
        prompt = f"""Design an IVR system:

Business Goal: {business_goal}
Menu Options: {menu_options}
Constraints: {constraints}

Provide complete IVR design."""
        
        response = await self.execute(prompt)
        return {"ivr_design": response, "agent": self.name}
