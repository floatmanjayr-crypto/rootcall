"""
Master Orchestrator - Routes tasks to appropriate specialist agents
"""
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from app.agent_framework.core.state import AgentState
from app.agent_framework.core.config import FrameworkConfig, AgentConfig
from app.agent_framework.agents.voice_agent import VoiceAgent
from app.agent_framework.agents.ai_agent import AIAgent
from app.agent_framework.agents.flow_designer_agent import FlowDesignerAgent


class MasterOrchestrator:
    """
    Master orchestrator that coordinates all specialist agents
    Uses LangGraph for complex multi-agent workflows
    """
    
    def __init__(self, config: FrameworkConfig):
        self.config = config
        
        # Initialize specialist agents
        self.voice_agent = VoiceAgent(config.voice_agent)
        self.ai_agent = AIAgent(config.ai_agent)
        self.flow_designer = FlowDesignerAgent(config.flow_designer_agent)
        
        # Agent routing map
        self.agent_map = {
            "voice": self.voice_agent,
            "ai": self.ai_agent,
            "flow_designer": self.flow_designer
        }
    
    async def route_request(self, request: str) -> str:
        """Determine which agent should handle the request"""
        routing_prompt = f"""Analyze this request and determine which specialist should handle it:

Request: "{request}"

Specialists available:
- voice: Handles phone calls, IVR, call routing, conferencing
- ai: Handles conversational AI, transcription, NLP, agent design
- flow_designer: Designs communication flows, campaigns, integration architecture

Respond with ONLY the specialist name (voice, ai, or flow_designer)."""
        
        # Use a simple LLM call to route
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4", temperature=0.3)
        response = await llm.ainvoke([("human", routing_prompt)])
        
        agent_name = response.content.strip().lower()
        
        # Validate and return
        if agent_name in self.agent_map:
            return agent_name
        return "flow_designer"  # Default
    
    async def execute_task(
        self,
        user_id: int,
        request: str,
        task_type: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Execute a task with the appropriate agent"""
        
        # Create initial state
        state: AgentState = {
            "user_id": user_id,
            "request": request,
            "request_type": task_type or "general",
            "current_agent": "",
            "agent_history": [],
            "task_id": str(uuid.uuid4()),
            "status": "pending",
            "result": None,
            "error": None,
            "messages": [],
            "intermediate_steps": [],
            "phone_numbers": context.get("phone_numbers", []) if context else [],
            "call_control_ids": [],
            "messaging_profile_ids": [],
            "ai_agent_id": context.get("ai_agent_id") if context else None,
            "system_prompt": context.get("system_prompt") if context else None,
            "conversation_history": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        try:
            # Route to appropriate agent
            agent_name = await self.route_request(request)
            state["current_agent"] = agent_name
            state["agent_history"].append(agent_name)
            
            # Get the agent
            agent = self.agent_map[agent_name]
            
            # Execute task
            state["status"] = "in_progress"
            result = await agent.process(state)
            
            # Update state
            state["status"] = "completed"
            state["result"] = result
            state["updated_at"] = datetime.utcnow()
            
            return {
                "success": True,
                "task_id": state["task_id"],
                "agent_used": agent_name,
                "result": result,
                "status": "completed"
            }
            
        except Exception as e:
            state["status"] = "failed"
            state["error"] = str(e)
            state["updated_at"] = datetime.utcnow()
            
            return {
                "success": False,
                "task_id": state["task_id"],
                "error": str(e),
                "status": "failed"
            }
    
    async def design_voice_flow(
        self,
        user_id: int,
        requirements: str
    ) -> Dict[str, Any]:
        """Specialized method to design a voice flow"""
        result = await self.flow_designer.design_ivr_flow(
            business_goal=requirements,
            menu_options=[],
            constraints={}
        )
        return result
    
    async def create_ai_agent(
        self,
        user_id: int,
        purpose: str,
        tone: str,
        requirements: list
    ) -> Dict[str, Any]:
        """Specialized method to create an AI agent"""
        result = await self.ai_agent.design_conversation_agent(
            purpose=purpose,
            tone=tone,
            requirements=requirements
        )
        return result
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            "orchestrator": "active",
            "agents": {
                "voice": {"name": self.voice_agent.name, "status": "ready"},
                "ai": {"name": self.ai_agent.name, "status": "ready"},
                "flow_designer": {"name": self.flow_designer.name, "status": "ready"}
            }
        }
