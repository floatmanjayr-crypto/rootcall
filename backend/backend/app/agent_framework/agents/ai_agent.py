"""
AI Agent - Specializes in AI inference and conversation management
"""
from typing import Dict, Any, List
from app.agent_framework.agents.base import BaseAgent
from app.agent_framework.core.state import AgentState
from app.agent_framework.core.config import AgentConfig


class AIAgent(BaseAgent):
    """Agent specialized in AI and NLP operations"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(
            name="AIAgent",
            role="AI Inference specialist - handles transcription, NLP, conversation AI",
            config=config
        )
    
    def _get_system_prompt(self) -> str:
        return """You are the AI Agent, an expert in artificial intelligence and natural language processing.

Your responsibilities:
1. Design conversational AI agents with optimal prompts
2. Implement speech-to-text and text-to-speech pipelines
3. Analyze conversation sentiment and intent
4. Optimize AI agent performance based on metrics
5. Create context-aware conversation flows

You have deep knowledge of:
- OpenAI GPT models and prompt engineering
- Whisper for transcription
- Conversation design patterns
- Intent classification and entity extraction

When designing AI agents:
1. Create clear, effective system prompts
2. Define conversation goals and guardrails
3. Handle edge cases and failures gracefully
4. Optimize for response time and quality
5. Include evaluation metrics"""
    
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """Process AI-related tasks"""
        request = state.get("request", "")
        
        analysis = await self.execute(
            f"""Analyze this AI-related request and provide implementation:
            
Request: {request}

Provide:
1. Recommended AI models
2. System prompt design
3. Implementation steps
4. Evaluation metrics
"""
        )
        
        return {
            "agent": self.name,
            "analysis": analysis,
            "status": "completed"
        }
    
    async def design_conversation_agent(
        self,
        purpose: str,
        tone: str,
        requirements: List[str]
    ) -> Dict[str, Any]:
        """Design a conversational AI agent"""
        prompt = f"""Design a conversational AI agent:

Purpose: {purpose}
Tone: {tone}
Requirements: {requirements}

Provide complete agent design with system prompt and examples."""
        
        response = await self.execute(prompt)
        return {"agent_design": response, "designer": self.name}
