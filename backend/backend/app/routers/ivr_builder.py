"""IVR Builder API - Create Interactive Voice Response Flows"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import json
import logging

from app.database import get_db
from app.models.ivr import IVRFlow, IVRNode, IVRAction, IVRNodeType, BusinessHours
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/api/v1/ivr", tags=["IVR Builder"])
log = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class CreateFlowRequest(BaseModel):
    """Create IVR flow"""
    user_id: int
    phone_number: Optional[str] = None
    name: str
    description: Optional[str] = None


class CreateNodeRequest(BaseModel):
    """Create IVR node"""
    flow_id: int
    node_type: str  # greeting, menu, gather_input, transfer, ai_agent, etc.
    name: str
    description: Optional[str] = None
    config: Dict
    position_x: int = 0
    position_y: int = 0
    timeout_seconds: int = 10


class CreateActionRequest(BaseModel):
    """Create IVR action (transition between nodes)"""
    node_id: int
    trigger: str  # "1", "2", "timeout", "no-input", etc.
    next_node_id: Optional[int] = None
    conditions: Optional[Dict] = None


class BusinessHoursRequest(BaseModel):
    """Configure business hours"""
    user_id: int
    name: str
    timezone: str = "America/New_York"
    schedule: Dict
    holidays: Optional[List[str]] = None


class IVRFlowResponse(BaseModel):
    """IVR flow response"""
    id: int
    name: str
    is_active: bool
    is_published: bool
    total_nodes: int
    created_at: datetime


class IVRNodeResponse(BaseModel):
    """IVR node response"""
    id: int
    node_type: str
    name: str
    config: Dict
    position_x: int
    position_y: int


# ============================================================================
# Helper Functions
# ============================================================================

def verify_flow_access(db: Session, user_id: int, flow_id: int) -> IVRFlow:
    """Verify user owns the IVR flow"""
    flow = db.query(IVRFlow).filter(
        IVRFlow.id == flow_id,
        IVRFlow.user_id == user_id
    ).first()
    
    if not flow:
        raise HTTPException(status_code=404, detail="IVR flow not found")
    
    return flow


def validate_node_config(node_type: str, config: Dict) -> bool:
    """Validate node configuration based on type"""
    required_fields = {
        "greeting": ["message"],
        "menu": ["prompt", "options"],
        "gather_input": ["
# Update main.py to include campaign manager and dashboard
sed -i '/from app.routers import enhanced_onboarding/a from app.routers import campaign_manager, dashboard' app/main.py
sed -i '/app.include_router(enhanced_onboarding.router)/a app.include_router(campaign_manager.router)\napp.include_router(dashboard.router)' app/main.py

echo "✅ Campaign manager and dashboard added to main.py"
echo ""
echo "Next: Let's create the IVR builder API and call recording integration"
# Create IVR Builder API
cat > app/routers/ivr_builder.py << 'EOF'
"""IVR Builder API - Create Interactive Voice Response Flows"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import json
import logging

from app.database import get_db
from app.models.ivr import IVRFlow, IVRNode, IVRAction, IVRNodeType, BusinessHours
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/api/v1/ivr", tags=["IVR Builder"])
log = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class CreateFlowRequest(BaseModel):
    """Create IVR flow"""
    user_id: int
    phone_number: Optional[str] = None
    name: str
    description: Optional[str] = None


class CreateNodeRequest(BaseModel):
    """Create IVR node"""
    flow_id: int
    node_type: str  # greeting, menu, gather_input, transfer, ai_agent, etc.
    name: str
    description: Optional[str] = None
    config: Dict
    position_x: int = 0
    position_y: int = 0
    timeout_seconds: int = 10


class CreateActionRequest(BaseModel):
    """Create IVR action (transition between nodes)"""
    node_id: int
    trigger: str  # "1", "2", "timeout", "no-input", etc.
    next_node_id: Optional[int] = None
    conditions: Optional[Dict] = None


class BusinessHoursRequest(BaseModel):
    """Configure business hours"""
    user_id: int
    name: str
    timezone: str = "America/New_York"
    schedule: Dict
    holidays: Optional[List[str]] = None


class IVRFlowResponse(BaseModel):
    """IVR flow response"""
    id: int
    name: str
    is_active: bool
    is_published: bool
    total_nodes: int
    created_at: datetime


class IVRNodeResponse(BaseModel):
    """IVR node response"""
    id: int
    node_type: str
    name: str
    config: Dict
    position_x: int
    position_y: int


# ============================================================================
# Helper Functions
# ============================================================================

def verify_flow_access(db: Session, user_id: int, flow_id: int) -> IVRFlow:
    """Verify user owns the IVR flow"""
    flow = db.query(IVRFlow).filter(
        IVRFlow.id == flow_id,
        IVRFlow.user_id == user_id
    ).first()
    
    if not flow:
        raise HTTPException(status_code=404, detail="IVR flow not found")
    
    return flow


def validate_node_config(node_type: str, config: Dict) -> bool:
    """Validate node configuration based on type"""
    required_fields = {
        "greeting": ["message"],
        "menu": ["prompt", "options"],
        "gather_input": ["prompt", "max_digits"],
        "transfer": ["destination"],
        "ai_agent": ["agent_id"],
        "voicemail": ["prompt"],
        "text_to_speech": ["text"],
        "play_audio": ["audio_url"]
    }
    
    if node_type in required_fields:
        for field in required_fields[node_type]:
            if field not in config:
                return False
    
    return True


def create_default_ivr_flow(db: Session, user_id: int, business_name: str) -> IVRFlow:
    """Create a default IVR flow for new users"""
    
    # Create flow
    flow = IVRFlow(
        user_id=user_id,
        name=f"{business_name} - Main Menu",
        description="Default IVR flow",
        is_active=True
    )
    db.add(flow)
    db.flush()
    
    # Create greeting node
    greeting_node = IVRNode(
        flow_id=flow.id,
        node_type=IVRNodeType.GREETING,
        name="Welcome Greeting",
        config={
            "message": f"Thank you for calling {business_name}.",
            "voice": "en-US-Neural2-F"
        },
        position_x=100,
        position_y=100
    )
    db.add(greeting_node)
    db.flush()
    
    # Create menu node
    menu_node = IVRNode(
        flow_id=flow.id,
        node_type=IVRNodeType.MENU,
        name="Main Menu",
        config={
            "prompt": "Press 1 to speak with an agent. Press 2 to leave a voicemail.",
            "options": {
                "1": "connect_agent",
                "2": "voicemail"
            }
        },
        position_x=100,
        position_y=300
    )
    db.add(menu_node)
    db.flush()
    
    # Create voicemail node
    voicemail_node = IVRNode(
        flow_id=flow.id,
        node_type=IVRNodeType.VOICEMAIL,
        name="Voicemail",
        config={
            "prompt": "Please leave your message after the beep.",
            "max_duration": 120
        },
        position_x=300,
        position_y=500
    )
    db.add(voicemail_node)
    
    # Connect nodes with actions
    greeting_action = IVRAction(
        node_id=greeting_node.id,
        trigger="complete",
        next_node_id=menu_node.id
    )
    db.add(greeting_action)
    
    menu_action_voicemail = IVRAction(
        node_id=menu_node.id,
        trigger="2",
        next_node_id=voicemail_node.id
    )
    db.add(menu_action_voicemail)
    
    flow.entry_node_id = greeting_node.id
    
    db.commit()
    db.refresh(flow)
    
    return flow


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/flows/create", response_model=IVRFlowResponse)
async def create_ivr_flow(
    request: CreateFlowRequest,
    db: Session = Depends(get_db)
):
    """Create a new IVR flow"""
    
    flow = IVRFlow(
        user_id=request.user_id,
        name=request.name,
        description=request.description,
        is_active=False
    )
    
    # Link to phone number if provided
    if request.phone_number:
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.user_id == request.user_id,
            PhoneNumber.phone_number == request.phone_number
        ).first()
        
        if phone:
            flow.phone_number_id = phone.id
    
    db.add(flow)
    db.commit()
    db.refresh(flow)
    
    log.info(f"✅ Created IVR flow: {flow.name}")
    
    return IVRFlowResponse(
        id=flow.id,
        name=flow.name,
        is_active=flow.is_active,
        is_published=flow.is_published,
        total_nodes=0,
        created_at=flow.created_at
    )


@router.post("/nodes/create", response_model=IVRNodeResponse)
async def create_ivr_node(
    request: CreateNodeRequest,
    db: Session = Depends(get_db)
):
    """Create a new IVR node"""
    
    # Validate config
    if not validate_node_config(request.node_type, request.config):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration for node type {request.node_type}"
        )
    
    node = IVRNode(
        flow_id=request.flow_id,
        node_type=IVRNodeType(request.node_type),
        name=request.name,
        description=request.description,
        config=request.config,
        position_x=request.position_x,
        position_y=request.position_y,
        timeout_seconds=request.timeout_seconds
    )
    
    db.add(node)
    db.commit()
    db.refresh(node)
    
    log.info(f"✅ Created IVR node: {node.name} (type: {node.node_type.value})")
    
    return IVRNodeResponse(
        id=node.id,
        node_type=node.node_type.value,
        name=node.name,
        config=node.config,
        position_x=node.position_x,
        position_y=node.position_y
    )


@router.post("/actions/create")
async def create_ivr_action(
    request: CreateActionRequest,
    db: Session = Depends(get_db)
):
    """Create action/transition between nodes"""
    
    action = IVRAction(
        node_id=request.node_id,
        trigger=request.trigger,
        next_node_id=request.next_node_id,
        conditions=request.conditions
    )
    
    db.add(action)
    db.commit()
    db.refresh(action)
    
    return {
        "id": action.id,
        "node_id": action.node_id,
        "trigger": action.trigger,
        "next_node_id": action.next_node_id
    }


@router.get("/flows/{flow_id}")
async def get_ivr_flow(
    flow_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get IVR flow with all nodes and actions"""
    
    flow = verify_flow_access(db, user_id, flow_id)
    
    # Get all nodes
    nodes = db.query(IVRNode).filter(IVRNode.flow_id == flow_id).all()
    
    # Get all actions
    node_ids = [node.id for node in nodes]
    actions = db.query(IVRAction).filter(IVRAction.node_id.in_(node_ids)).all()
    
    return {
        "flow": {
            "id": flow.id,
            "name": flow.name,
            "description": flow.description,
            "is_active": flow.is_active,
            "is_published": flow.is_published,
            "entry_node_id": flow.entry_node_id
        },
        "nodes": [
            {
                "id": node.id,
                "node_type": node.node_type.value,
                "name": node.name,
                "config": node.config,
                "position_x": node.position_x,
                "position_y": node.position_y
            }
            for node in nodes
        ],
        "actions": [
            {
                "id": action.id,
                "node_id": action.node_id,
                "trigger": action.trigger,
                "next_node_id": action.next_node_id
            }
            for action in actions
        ]
    }


@router.post("/flows/{flow_id}/publish")
async def publish_ivr_flow(
    flow_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Publish IVR flow (make it live)"""
    
    flow = verify_flow_access(db, user_id, flow_id)
    
    if not flow.entry_node_id:
        raise HTTPException(status_code=400, detail="Flow must have an entry node before publishing")
    
    flow.is_published = True
    flow.is_active = True
    flow.published_at = datetime.utcnow()
    
    db.commit()
    
    log.info(f"✅ Published IVR flow: {flow.name}")
    
    return {
        "flow_id": flow.id,
        "status": "published",
        "message": f"IVR flow '{flow.name}' is now live"
    }


@router.post("/business-hours/create")
async def create_business_hours(
    request: BusinessHoursRequest,
    db: Session = Depends(get_db)
):
    """Configure business hours"""
    
    business_hours = BusinessHours(
        user_id=request.user_id,
        name=request.name,
        timezone=request.timezone,
        schedule=request.schedule,
        holidays=request.holidays,
        is_active=True
    )
    
    db.add(business_hours)
    db.commit()
    db.refresh(business_hours)
    
    return {
        "id": business_hours.id,
        "name": business_hours.name,
        "timezone": business_hours.timezone,
        "is_active": business_hours.is_active
    }


@router.get("/templates")
async def get_ivr_templates():
    """Get pre-built IVR templates"""
    
    return {
        "templates": [
            {
                "id": "basic_menu",
                "name": "Basic Menu",
                "description": "Simple menu with options for agent or voicemail",
                "nodes": 3
            },
            {
                "id": "business_hours",
                "name": "Business Hours Routing",
                "description": "Route calls based on business hours",
                "nodes": 5
            },
            {
                "id": "department_routing",
                "name": "Department Routing",
                "description": "Route to different departments",
                "nodes": 6
            },
            {
                "id": "ai_first",
                "name": "AI-First with Escalation",
                "description": "AI handles call, escalates to human if needed",
                "nodes": 4
            }
        ]
    }
