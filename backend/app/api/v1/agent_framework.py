"""
Agent Framework API Endpoints
Exposes the multi-agent system capabilities
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.ai_agent import AIAgent
from app.models.call import Call
from app.core.deps import get_current_active_user
from app.services.agent_framework_service import agent_framework_service

router = APIRouter()


# Request Models
class FlowGenerationRequest(BaseModel):
    requirements: str = Field(..., description="Natural language description of the flow")
    phone_number: Optional[str] = Field(None, description="Phone number to assign flow to")


class AIAgentCreationRequest(BaseModel):
    purpose: str = Field(..., description="Purpose of the AI agent")
    tone: str = Field(default="professional", description="Tone: professional, friendly, casual, formal")
    requirements: List[str] = Field(default=[], description="Specific requirements")


class PromptOptimizationRequest(BaseModel):
    agent_id: int = Field(..., description="ID of the agent to optimize")
    include_last_n_calls: int = Field(default=50, ge=10, le=200)


class IVRDesignRequest(BaseModel):
    business_goal: str = Field(..., description="What should the IVR accomplish")
    menu_options: List[str] = Field(..., description="Menu options")
    phone_number: str = Field(..., description="Phone number for IVR")


class MessagingCampaignRequest(BaseModel):
    campaign_goal: str = Field(..., description="Goal of the campaign")
    audience: str = Field(..., description="Target audience description")
    message_template: str = Field(..., description="Initial message template")


class ConversationAnalysisRequest(BaseModel):
    call_id: Optional[int] = Field(None, description="Call ID to analyze")
    transcript: Optional[str] = Field(None, description="Direct transcript text")


class CustomTaskRequest(BaseModel):
    request: str = Field(..., description="Natural language task description")
    task_type: str = Field(default="general")
    context: Optional[Dict] = Field(default=None)


# Endpoints
@router.get("/status")
async def get_framework_status(
    current_user: User = Depends(get_current_active_user)
):
    """Get status of the agent framework"""
    status = agent_framework_service.get_framework_status()
    return {
        "framework": status,
        "user_id": current_user.id
    }


@router.post("/generate-flow")
async def generate_call_flow(
    request: FlowGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a complete call flow from natural language description
    
    Example: "Create a customer support flow that qualifies issues, 
             provides solutions, and escalates complex problems"
    """
    try:
        result = await agent_framework_service.generate_call_flow(
            user_id=current_user.id,
            requirements=request.requirements,
            context={"phone_number": request.phone_number} if request.phone_number else None
        )
        
        return {
            "success": result.get("success"),
            "task_id": result.get("task_id"),
            "flow": result.get("result"),
            "agent_used": result.get("agent_used")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flow generation failed: {str(e)}")


@router.post("/create-ai-agent")
async def create_ai_agent_design(
    request: AIAgentCreationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create an AI voice agent configuration using the framework
    
    This generates a complete agent design including system prompt,
    conversation flow, and recommended settings
    """
    try:
        result = await agent_framework_service.create_ai_voice_agent(
            user_id=current_user.id,
            purpose=request.purpose,
            tone=request.tone,
            requirements=request.requirements
        )
        
        return {
            "success": True,
            "agent_design": result,
            "message": "AI agent design created. You can now save this as a new agent."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent creation failed: {str(e)}")


@router.post("/optimize-prompt")
async def optimize_agent_prompt(
    request: PromptOptimizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Analyze agent performance and optimize the system prompt
    """
    # Get agent
    agent = db.query(AIAgent).filter(
        AIAgent.id == request.agent_id,
        AIAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get recent calls with transcripts
    recent_calls = db.query(Call).filter(
        Call.ai_agent_id == agent.id,
        Call.transcription.isnot(None)
    ).order_by(Call.started_at.desc()).limit(request.include_last_n_calls).all()
    
    if len(recent_calls) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 10 calls with transcriptions. Found {len(recent_calls)}"
        )
    
    # Calculate performance metrics
    performance_data = {
        "total_calls": len(recent_calls),
        "avg_duration": sum(c.duration for c in recent_calls) / len(recent_calls),
        "completion_rate": sum(1 for c in recent_calls if c.status == "completed") / len(recent_calls),
        "avg_cost": sum(c.cost for c in recent_calls) / len(recent_calls)
    }
    
    transcripts = [c.transcription for c in recent_calls if c.transcription]
    
    try:
        result = await agent_framework_service.optimize_agent_prompt(
            user_id=current_user.id,
            current_prompt=agent.system_prompt,
            performance_data=performance_data,
            transcripts=transcripts
        )
        
        return {
            "success": result.get("success"),
            "agent_name": agent.name,
            "current_prompt": agent.system_prompt,
            "performance_metrics": performance_data,
            "optimization": result.get("result"),
            "calls_analyzed": len(recent_calls)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/design-ivr")
async def design_ivr_system(
    request: IVRDesignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Design an IVR (Interactive Voice Response) system
    """
    try:
        result = await agent_framework_service.design_ivr_system(
            user_id=current_user.id,
            business_goal=request.business_goal,
            menu_options=request.menu_options,
            phone_number=request.phone_number
        )
        
        return {
            "success": result.get("success"),
            "ivr_design": result.get("result"),
            "phone_number": request.phone_number
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"IVR design failed: {str(e)}")


@router.post("/create-campaign")
async def create_messaging_campaign(
    request: MessagingCampaignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Design an automated messaging campaign
    """
    try:
        result = await agent_framework_service.create_messaging_campaign(
            user_id=current_user.id,
            campaign_goal=request.campaign_goal,
            audience=request.audience,
            message_template=request.message_template
        )
        
        return {
            "success": result.get("success"),
            "campaign_design": result.get("result")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Campaign creation failed: {str(e)}")


@router.post("/analyze-conversation")
async def analyze_conversation(
    request: ConversationAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Analyze a call transcript for insights
    """
    transcript = request.transcript
    
    # If call_id provided, get transcript from database
    if request.call_id and not transcript:
        call = db.query(Call).filter(
            Call.id == request.call_id,
            Call.user_id == current_user.id
        ).first()
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if not call.transcription:
            raise HTTPException(status_code=400, detail="Call has no transcription")
        
        transcript = call.transcription
    
    if not transcript:
        raise HTTPException(status_code=400, detail="No transcript provided")
    
    try:
        result = await agent_framework_service.analyze_conversation(
            user_id=current_user.id,
            transcript=transcript
        )
        
        return {
            "success": result.get("success"),
            "analysis": result.get("result")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/custom-task")
async def execute_custom_task(
    request: CustomTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Execute a custom task with the agent framework
    
    Send any natural language request to the framework
    """
    try:
        result = await agent_framework_service.custom_request(
            user_id=current_user.id,
            request=request.request,
            task_type=request.task_type,
            context=request.context
        )
        
        return {
            "success": result.get("success"),
            "result": result.get("result"),
            "agent_used": result.get("agent_used")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")
