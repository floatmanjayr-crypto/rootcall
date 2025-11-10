from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.ai_agent import AIAgent
from app.models.phone_number import PhoneNumber
from app.schemas.ai_agent import (
    AIAgent as AIAgentSchema,
    AIAgentCreate,
    AIAgentUpdate,
    AgentTemplate,
    AGENT_TEMPLATES
)
from app.core.deps import get_current_active_user

router = APIRouter()


@router.get("/templates", response_model=List[AgentTemplate])
def get_agent_templates():
    """Get pre-built agent templates"""
    return AGENT_TEMPLATES


@router.post("/", response_model=AIAgentSchema)
def create_agent(
    agent_in: AIAgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new AI agent"""
    agent = AIAgent(
        user_id=current_user.id,
        **agent_in.model_dump()
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/from-template/{template_name}", response_model=AIAgentSchema)
def create_agent_from_template(
    template_name: str,
    custom_name: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create an AI agent from a template"""
    # Find template
    template = None
    for t in AGENT_TEMPLATES:
        if t.name.lower().replace(" ", "_") == template_name.lower():
            template = t
            break
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create agent from template
    agent = AIAgent(
        user_id=current_user.id,
        name=custom_name or template.name,
        description=template.description,
        agent_type=template.agent_type,
        system_prompt=template.system_prompt,
        greeting_message=template.greeting_message,
        voice_model=template.voice_model,
        temperature=template.temperature
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/", response_model=List[AIAgentSchema])
def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List user's AI agents"""
    return db.query(AIAgent).filter(AIAgent.user_id == current_user.id).all()


@router.get("/{agent_id}", response_model=AIAgentSchema)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get AI agent details"""
    agent = db.query(AIAgent).filter(
        AIAgent.id == agent_id,
        AIAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent


@router.put("/{agent_id}", response_model=AIAgentSchema)
def update_agent(
    agent_id: int,
    agent_update: AIAgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update AI agent"""
    agent = db.query(AIAgent).filter(
        AIAgent.id == agent_id,
        AIAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = agent_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)
    
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete AI agent"""
    agent = db.query(AIAgent).filter(
        AIAgent.id == agent_id,
        AIAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Unassign from phone numbers
    db.query(PhoneNumber).filter(PhoneNumber.ai_agent_id == agent_id).update(
        {"ai_agent_id": None}
    )
    
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted successfully"}


@router.post("/{agent_id}/assign-phone/{phone_id}")
def assign_agent_to_phone(
    agent_id: int,
    phone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Assign AI agent to a phone number"""
    agent = db.query(AIAgent).filter(
        AIAgent.id == agent_id,
        AIAgent.user_id == current_user.id
    ).first()
    
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not phone:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    phone.ai_agent_id = agent_id
    db.commit()
    
    return {"message": f"Agent '{agent.name}' assigned to {phone.phone_number}"}


@router.post("/{agent_id}/test")
def test_agent(
    agent_id: int,
    test_message: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Test AI agent with a message"""
    from app.services.ai_agent_service import AIAgentService
    
    agent = db.query(AIAgent).filter(
        AIAgent.id == agent_id,
        AIAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    response = AIAgentService.generate_response(
        user_message=test_message,
        system_prompt=agent.system_prompt,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens
    )
    
    return {
        "agent_name": agent.name,
        "user_message": test_message,
        "agent_response": response
    }
