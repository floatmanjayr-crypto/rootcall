"""Enhanced Client Onboarding with Feature Selection"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.models.subscription import Subscription, UserFeature, SubscriptionTier, FeatureType
from app.services.retell_service import retell_service
from app.services.telnyx_service import TelnyxService
from app.config import settings

router = APIRouter(prefix="/api/v1/enhanced-onboarding", tags=["Enhanced Onboarding"])
log = logging.getLogger(__name__)

telnyx_service = TelnyxService()


# ============================================================================
# Pydantic Models
# ============================================================================

class FeatureSelection(BaseModel):
    """Feature to enable for the client"""
    feature_type: str  # ai_agent, outbound_calls, bulk_campaigns, etc.
    enabled: bool = True
    monthly_limit: Optional[int] = None


class OnboardingRequest(BaseModel):
    """Complete onboarding request"""
    # User details
    email: EmailStr
    password: str
    full_name: str
    business_name: str
    
    # Subscription tier
    tier: str = "basic"  # free, basic, pro, enterprise
    trial_days: int = 14
    
    # Features to enable
    features: List[FeatureSelection]
    
    # Phone number (optional - can purchase later)
    purchase_phone_number: bool = False
    area_code: Optional[str] = None
    
    # AI Agent configuration (if ai_agent feature enabled)
    ai_system_prompt: Optional[str] = None
    ai_greeting: Optional[str] = None
    ai_voice: str = "11labs-Adrian"
    
    # IVR configuration (if ivr_system feature enabled)
    enable_ivr: bool = False


class OnboardingResponse(BaseModel):
    """Onboarding completion response"""
    user_id: int
    email: str
    subscription_tier: str
    features_enabled: List[str]
    phone_number: Optional[str]
    ai_agent_id: Optional[str]
    ivr_flow_id: Optional[int]
    trial_ends_at: Optional[datetime]
    next_steps: List[str]


# ============================================================================
# Helper Functions
# ============================================================================

async def create_user_account(
    db: Session,
    email: str,
    password: str,
    full_name: str
) -> User:
    """Create new user account"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Check if email already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=email,
        username=email.split('@')[0],
        hashed_password=pwd_context.hash(password),
        full_name=full_name,
        is_active=True,
        balance=0.0
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    log.info(f"✅ Created user: {email}")
    return user


async def create_subscription(
    db: Session,
    user_id: int,
    tier: str,
    trial_days: int
) -> Subscription:
    """Create subscription for user"""
    
    # Subscription tier pricing
    tier_config = {
        "free": {
            "monthly_price": 0.0,
            "monthly_minutes": 0,
            "max_numbers": 1,
            "max_campaigns": 0,
            "concurrent_calls": 1
        },
        "basic": {
            "monthly_price": 49.0,
            "monthly_minutes": 500,
            "max_numbers": 2,
            "max_campaigns": 10,
            "concurrent_calls": 5
        },
        "pro": {
            "monthly_price": 149.0,
            "monthly_minutes": 2000,
            "max_numbers": 5,
            "max_campaigns": 50,
            "concurrent_calls": 20
        },
        "enterprise": {
            "monthly_price": 499.0,
            "monthly_minutes": 10000,
            "max_numbers": 20,
            "max_campaigns": 999,
            "concurrent_calls": 100
        }
    }
    
    config = tier_config.get(tier, tier_config["basic"])
    
    subscription = Subscription(
        user_id=user_id,
        tier=SubscriptionTier(tier),
        monthly_price=config["monthly_price"],
        monthly_minutes_included=config["monthly_minutes"],
        max_phone_numbers=config["max_numbers"],
        max_campaigns_per_month=config["max_campaigns"],
        max_concurrent_calls=config["concurrent_calls"],
        billing_cycle_start=datetime.utcnow(),
        billing_cycle_end=datetime.utcnow() + timedelta(days=30),
        trial_ends_at=datetime.utcnow() + timedelta(days=trial_days) if trial_days > 0 else None,
        is_active=True
    )
    
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    log.info(f"✅ Created {tier} subscription for user {user_id}")
    return subscription


async def enable_features(
    db: Session,
    subscription_id: int,
    features: List[FeatureSelection]
) -> List[UserFeature]:
    """Enable features for subscription"""
    
    # Feature pricing
    feature_pricing = {
        "ai_agent": {"monthly": 20.0, "per_use": 0.0},
        "outbound_calls": {"monthly": 15.0, "per_use": 0.02},
        "inbound_calls": {"monthly": 10.0, "per_use": 0.01},
        "bulk_campaigns": {"monthly": 30.0, "per_use": 0.0},
        "call_recording": {"monthly": 10.0, "per_use": 0.005},
        "transcription": {"monthly": 15.0, "per_use": 0.01},
        "ivr_system": {"monthly": 25.0, "per_use": 0.0},
        "sms": {"monthly": 5.0, "per_use": 0.01},
        "analytics": {"monthly": 10.0, "per_use": 0.0},
        "api_access": {"monthly": 20.0, "per_use": 0.0}
    }
    
    enabled_features = []
    
    for feature in features:
        if not feature.enabled:
            continue
        
        pricing = feature_pricing.get(feature.feature_type, {"monthly": 0.0, "per_use": 0.0})
        
        user_feature = UserFeature(
            subscription_id=subscription_id,
            feature_type=FeatureType(feature.feature_type),
            is_enabled=True,
            monthly_limit=feature.monthly_limit,
            monthly_cost=pricing["monthly"],
            per_use_cost=pricing["per_use"]
        )
        
        db.add(user_feature)
        enabled_features.append(user_feature)
    
    db.commit()
    
    log.info(f"✅ Enabled {len(enabled_features)} features")
    return enabled_features


async def setup_ai_agent(
    db: Session,
    user_id: int,
    business_name: str,
    system_prompt: str,
    greeting: str,
    voice: str
) -> tuple[AIAgent, str]:
    """Create and configure AI agent"""
    
    # Create Retell LLM
    llm_id = retell_service.create_llm(
        general_prompt=system_prompt,
        begin_message=greeting
    )
    
    # Create Retell Agent
    agent_id = retell_service.create_agent(
        name=f"{business_name} AI",
        llm_id=llm_id,
        voice_id=voice,
        publish=True
    )
    
    # Save to database
    ai_agent = AIAgent(
        user_id=user_id,
        name=f"{business_name} AI",
        retell_agent_id=agent_id,
        retell_llm_id=llm_id,
        system_prompt=system_prompt,
        greeting_message=greeting,
        voice_model=voice,
        is_active=True
    )
    
    db.add(ai_agent)
    db.commit()
    db.refresh(ai_agent)
    
    log.info(f"✅ Created AI agent: {agent_id}")
    return ai_agent, agent_id


async def purchase_and_configure_number(
    db: Session,
    user_id: int,
    ai_agent_id: int,
    retell_agent_id: str,
    area_code: str
) -> PhoneNumber:
    """Purchase phone number and configure it"""
    
    # Search for available numbers
    available_numbers = telnyx_service.search_phone_numbers(
        country_code="US",
        limit=5,
        features=["voice", "sms"]
    )
    
    if not available_numbers:
        raise HTTPException(status_code=404, detail="No phone numbers available")
    
    # Purchase first available number
    number_data = available_numbers[0]
    purchased = telnyx_service.purchase_phone_number(number_data["phone_number"])
    
    phone_number = purchased["phone_number"]
    
    # Import to Retell for outbound calling
    # Note: You'll need SIP credentials from Telnyx
    # For now, just save to database
    
    phone = PhoneNumber(
        user_id=user_id,
        phone_number=phone_number,
        ai_agent_id=ai_agent_id,
        telnyx_phone_number_id=purchased.get("id"),
        is_active=True,
        monthly_cost=1.0
    )
    
    db.add(phone)
    db.commit()
    db.refresh(phone)
    
    log.info(f"✅ Purchased and configured: {phone_number}")
    return phone


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/complete", response_model=OnboardingResponse)
async def complete_onboarding(
    request: OnboardingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Complete end-to-end client onboarding with feature selection
    
    This creates:
    - User account
    - Subscription with selected tier
    - Enabled features
    - AI agent (if feature enabled)
    - Phone number (if requested)
    - IVR flow (if enabled)
    """
    
    try:
        log.info(f"��� Starting onboarding for {request.email}")
        
        # Step 1: Create user account
        user = await create_user_account(
            db=db,
            email=request.email,
            password=request.password,
            full_name=request.full_name
        )
        
        # Step 2: Create subscription
        subscription = await create_subscription(
            db=db,
            user_id=user.id,
            tier=request.tier,
            trial_days=request.trial_days
        )
        
        # Step 3: Enable features
        features = await enable_features(
            db=db,
            subscription_id=subscription.id,
            features=request.features
        )
        
        feature_types = [f.feature_type.value for f in features]
        
        # Step 4: Setup AI agent if feature enabled
        ai_agent_id = None
        retell_agent_id = None
        if "ai_agent" in feature_types and request.ai_system_prompt:
            ai_agent, retell_agent_id = await setup_ai_agent(
                db=db,
                user_id=user.id,
                business_name=request.business_name,
                system_prompt=request.ai_system_prompt,
                greeting=request.ai_greeting or f"Hi! Welcome to {request.business_name}. How can I help you?",
                voice=request.ai_voice
            )
            ai_agent_id = retell_agent_id
        
        # Step 5: Purchase phone number if requested
        phone_number = None
        if request.purchase_phone_number and request.area_code:
            phone = await purchase_and_configure_number(
                db=db,
                user_id=user.id,
                ai_agent_id=ai_agent.id if ai_agent_id else None,
                retell_agent_id=retell_agent_id,
                area_code=request.area_code
            )
            phone_number = phone.phone_number
        
        # Step 6: Setup IVR (if enabled)
        ivr_flow_id = None
        if request.enable_ivr and "ivr_system" in feature_types:
            # TODO: Create default IVR flow
            pass
        
        # Build next steps
        next_steps = []
        if not phone_number:
            next_steps.append("Purchase a phone number from the dashboard")
        if not ai_agent_id:
            next_steps.append("Configure your AI agent settings")
        if "bulk_campaigns" in feature_types:
            next_steps.append("Create your first calling campaign")
        next_steps.append("Explore the dashboard and features")
        
        log.info(f"✅ Onboarding complete for {request.email}")
        
        return OnboardingResponse(
            user_id=user.id,
            email=user.email,
            subscription_tier=subscription.tier.value,
            features_enabled=feature_types,
            phone_number=phone_number,
            ai_agent_id=ai_agent_id,
            ivr_flow_id=ivr_flow_id,
            trial_ends_at=subscription.trial_ends_at,
            next_steps=next_steps
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"❌ Onboarding failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pricing")
async def get_pricing():
    """Get pricing tiers and features"""
    return {
        "tiers": {
            "free": {
                "name": "Free",
                "price": 0,
                "minutes": 0,
                "phone_numbers": 1,
                "features": ["inbound_calls"]
            },
            "basic": {
                "name": "Basic",
                "price": 49,
                "minutes": 500,
                "phone_numbers": 2,
                "features": ["ai_agent", "inbound_calls", "outbound_calls", "call_recording"]
            },
            "pro": {
                "name": "Pro",
                "price": 149,
                "minutes": 2000,
                "phone_numbers": 5,
                "features": ["ai_agent", "inbound_calls", "outbound_calls", "bulk_campaigns", "call_recording", "transcription", "ivr_system", "analytics"]
            },
            "enterprise": {
                "name": "Enterprise",
                "price": 499,
                "minutes": 10000,
                "phone_numbers": 20,
                "features": ["all"]
            }
        },
        "add_ons": {
            "ai_agent": {"name": "AI Agent", "monthly": 20},
            "bulk_campaigns": {"name": "Bulk Campaigns", "monthly": 30},
            "ivr_system": {"name": "IVR System", "monthly": 25},
            "transcription": {"name": "Call Transcription", "monthly": 15},
            "api_access": {"name": "API Access", "monthly": 20}
        }
    }
