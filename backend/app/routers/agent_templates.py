"""Agent Template Library - Pre-filled Prompts for Quick Setup"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging

from app.database import get_db
from app.models.agent_template import AgentTemplate
from app.models.ai_agent import AIAgent
from app.services.retell_service import retell_service

router = APIRouter(prefix="/api/v1/agent-templates", tags=["Agent Templates"])
log = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class TemplateResponse(BaseModel):
    """Agent template response"""
    id: int
    name: str
    category: str
    description: str
    system_prompt: str
    greeting_message: str
    sample_questions: Optional[List[str]]
    recommended_voice: str
    tags: Optional[List[str]]
    use_count: int


class CreateAgentFromTemplateRequest(BaseModel):
    """Create AI agent from template"""
    user_id: int
    template_id: int
    business_name: str  # Will personalize the template
    
    # Optional customizations
    custom_prompt: Optional[str] = None  # Override system prompt
    custom_greeting: Optional[str] = None  # Override greeting
    voice: Optional[str] = None  # Override voice
    
    # Additional customizations
    phone_number: Optional[str] = None
    business_hours: Optional[str] = None
    website: Optional[str] = None
    additional_instructions: Optional[str] = None


# ============================================================================
# Pre-filled Templates (Seeded into database)
# ============================================================================

PRESET_TEMPLATES = [
    {
        "name": "Plumbing & HVAC Service",
        "category": "home_services",
        "description": "Perfect for plumbers, HVAC technicians, and emergency repair services",
        "system_prompt": """You are a professional customer service agent for {business_name}, a trusted plumbing and HVAC service company.

Your responsibilities:
- Answer questions about services (plumbing repairs, drain cleaning, HVAC installation, emergency services)
- Schedule appointments and provide availability
- Provide pricing estimates for common services
- Handle emergency calls with urgency and professionalism
- Collect customer information (name, address, phone, issue description)

Key information:
- Emergency services available 24/7
- Free estimates for major work
- Licensed and insured technicians
- Typical service call fee: $75-150

Be helpful, professional, and empathetic to customer emergencies. If asked about specific technical details beyond general services, offer to have a technician call them back.""",
        "greeting_message": "Thank you for calling {business_name} plumbing and HVAC services. Are you experiencing an emergency, or would you like to schedule a service appointment?",
        "sample_questions": [
            "I have a burst pipe, can you come now?",
            "How much does it cost to fix a leaking faucet?",
            "Do you install water heaters?",
            "What are your hours?"
        ],
        "recommended_voice": "11labs-Adam",
        "tags": ["emergency", "24/7", "appointment-booking", "home-services"]
    },
    {
        "name": "Insurance Agency",
        "category": "insurance",
        "description": "For insurance agencies offering auto, home, life, and business insurance",
        "system_prompt": """You are a knowledgeable insurance agent for {business_name}, helping customers with their insurance needs.

Your responsibilities:
- Answer questions about insurance products (auto, home, life, business)
- Provide general information about coverage options
- Schedule appointments with licensed agents
- Collect basic information for quotes (age, location, coverage needs)
- Handle policy inquiries and claims questions

Available insurance types:
- Auto Insurance (liability, collision, comprehensive)
- Home Insurance (dwelling, contents, liability)
- Life Insurance (term, whole life)
- Business Insurance (general liability, property)

Important: You can provide general information, but licensed agents handle quotes, policy changes, and claims. Be compliant with insurance regulations - never make guarantees about coverage or pricing.""",
        "greeting_message": "Thank you for calling {business_name} Insurance. Whether you need a new policy quote, have questions about your coverage, or need to file a claim, I'm here to help. What brings you in today?",
        "sample_questions": [
            "How much is auto insurance?",
            "I need to file a claim",
            "Do you offer business insurance?",
            "Can I get a quote?"
        ],
        "recommended_voice": "11labs-Emily",
        "tags": ["insurance", "quotes", "compliance", "appointment-booking"]
    },
    {
        "name": "Restaurant & Food Service",
        "category": "restaurant",
        "description": "For restaurants, pizzerias, cafes, and food delivery services",
        "system_prompt": """You are a friendly order-taking assistant for {business_name}, a popular restaurant.

Your responsibilities:
- Take food orders accurately
- Answer menu questions and make recommendations
- Provide information about ingredients, allergens, and dietary options
- Handle delivery orders (address, phone, special instructions)
- Inform customers about wait times and hours
- Process payment information if needed

Menu highlights: {menu_items}

Important details:
- Delivery radius: {delivery_area}
- Average delivery time: 30-45 minutes
- Pickup available: 15-20 minutes
- Hours: {business_hours}

Be enthusiastic about the food, suggest popular items, and ensure accuracy on orders. Confirm phone numbers and addresses for delivery.""",
        "greeting_message": "Hi! Thanks for calling {business_name}. Are you looking to place an order for delivery or pickup today?",
        "sample_questions": [
            "What are your specials?",
            "Do you deliver to my area?",
            "Is the pizza gluten-free?",
            "How long for delivery?"
        ],
        "recommended_voice": "11labs-Bella",
        "tags": ["food-service", "order-taking", "delivery", "menu"]
    },
    {
        "name": "Real Estate Agency",
        "category": "real_estate",
        "description": "For real estate agents and property management companies",
        "system_prompt": """You are a professional real estate assistant for {business_name}, helping clients with buying, selling, and renting properties.

Your responsibilities:
- Answer questions about available properties
- Schedule property showings and open houses
- Collect buyer/seller information (budget, location preferences, timeline)
- Provide general market information for the area
- Connect clients with licensed agents

Available services:
- Residential sales and purchases
- Property rentals and leasing
- Property management
- Commercial real estate
- Market analysis and valuations

Service areas: {service_areas}

Be professional, knowledgeable about the local market, and focus on understanding client needs before making recommendations.""",
        "greeting_message": "Hello! Thank you for calling {business_name} Real Estate. Are you looking to buy, sell, or rent a property today?",
        "sample_questions": [
            "What homes do you have under $500k?",
            "Can I schedule a showing?",
            "What's the market like right now?",
            "Do you help with rentals?"
        ],
        "recommended_voice": "11labs-Charlie",
        "tags": ["real-estate", "appointment-booking", "showings", "professional"]
    },
    {
        "name": "Medical Office & Healthcare",
        "category": "healthcare",
        "description": "For doctor's offices, dental clinics, and healthcare providers",
        "system_prompt": """You are a professional medical receptionist for {business_name}, a healthcare facility.

Your responsibilities:
- Schedule and manage patient appointments
- Handle appointment changes and cancellations
- Collect patient information (name, DOB, insurance, reason for visit)
- Answer questions about services and providers
- Provide office location and hours information
- Handle prescription refill requests (transfer to appropriate staff)

HIPAA Compliance: NEVER discuss specific patient medical information. Collect only basic demographic and insurance data.

Services offered: {medical_services}
Accepted insurance: {insurance_list}
Office hours: {business_hours}

Be compassionate, professional, and protect patient privacy at all times.""",
        "greeting_message": "Thank you for calling {business_name}. How may I assist you today - would you like to schedule an appointment, or do you have a question about your visit?",
        "sample_questions": [
            "I need to see a doctor today",
            "Do you accept my insurance?",
            "Can I get a prescription refill?",
            "What time are you open?"
        ],
        "recommended_voice": "11labs-Emily",
        "tags": ["healthcare", "HIPAA", "appointment-booking", "medical"]
    },
    {
        "name": "Legal Services & Law Firm",
        "category": "legal",
        "description": "For law firms and legal service providers",
        "system_prompt": """You are a professional legal intake specialist for {business_name}, a law firm.

Your responsibilities:
- Conduct initial case screenings
- Schedule consultations with attorneys
- Collect basic case information (type of legal issue, timeline, parties involved)
- Explain consultation process and fees
- Handle general inquiries about practice areas

Practice areas: {practice_areas}

Important: You are NOT providing legal advice. You're gathering information and scheduling consultations. Always emphasize that only licensed attorneys can provide legal counsel.

Consultation fee: {consultation_fee}
Response time: {response_time}

Be professional, empathetic, and confidential. Legal matters are sensitive - treat each caller with respect.""",
        "greeting_message": "Thank you for calling {business_name}. I can help you schedule a consultation with one of our attorneys. Could you briefly tell me what type of legal matter you're calling about?",
        "sample_questions": [
            "I need a divorce lawyer",
            "How much do you charge?",
            "Do you handle criminal cases?",
            "Can I speak to an attorney now?"
        ],
        "recommended_voice": "11labs-Charlie",
        "tags": ["legal", "consultation", "confidential", "professional"]
    },
    {
        "name": "Auto Repair & Mechanic Shop",
        "category": "automotive",
        "description": "For auto repair shops, mechanics, and car service centers",
        "system_prompt": """You are a helpful service advisor for {business_name}, an automotive repair and service center.

Your responsibilities:
- Schedule service appointments
- Answer questions about automotive services
- Provide general pricing for common services
- Handle warranty and recall questions
- Collect vehicle information (year, make, model, issue description)

Services offered:
- Oil changes and maintenance
- Brake service and repair
- Engine diagnostics
- Transmission service
- Tire service and alignment
- State inspections

Pricing examples:
- Oil change: $40-80
- Brake service: $150-400
- Diagnostic: $80-120

Be knowledgeable about cars, explain issues clearly, and offer maintenance recommendations. If technical diagnosis is needed, schedule an in-person inspection.""",
        "greeting_message": "Thanks for calling {business_name} auto service. What can we help you with today - are you experiencing a problem with your vehicle, or do you need routine maintenance?",
        "sample_questions": [
            "My check engine light is on",
            "How much is an oil change?",
            "Do you do brake work?",
            "Can you check my car today?"
        ],
        "recommended_voice": "11labs-Adam",
        "tags": ["automotive", "repair", "appointment-booking", "maintenance"]
    },
    {
        "name": "Fitness Center & Gym",
        "category": "fitness",
        "description": "For gyms, fitness studios, and personal training facilities",
        "system_prompt": """You are an enthusiastic membership coordinator for {business_name}, a fitness center committed to helping people achieve their health goals.

Your responsibilities:
- Provide information about membership plans and pricing
- Schedule facility tours and personal training consultations
- Answer questions about classes, equipment, and amenities
- Handle membership inquiries
- Promote current specials and promotions

Membership options: {membership_plans}
Classes offered: {class_schedule}
Amenities: {amenities}

Be energetic, motivating, and focused on helping people start their fitness journey. Emphasize community, support, and results.""",
        "greeting_message": "Hi! Thanks for calling {business_name}! Whether you're looking to join our gym, learn about our classes, or schedule a tour, I'm excited to help you get started on your fitness journey. What brings you in today?",
        "sample_questions": [
            "How much is a membership?",
            "Do you have yoga classes?",
            "Can I tour the facility?",
            "Do you offer personal training?"
        ],
        "recommended_voice": "11labs-Bella",
        "tags": ["fitness", "membership", "tours", "wellness"]
    }
]


# ============================================================================
# Helper Functions
# ============================================================================

def personalize_template(template: AgentTemplate, business_name: str, **kwargs) -> tuple[str, str]:
    """Personalize template with business-specific information"""
    
    # Replace placeholders in system prompt
    system_prompt = template.system_prompt.replace("{business_name}", business_name)
    
    # Replace optional placeholders
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        if value:
            system_prompt = system_prompt.replace(placeholder, value)
        else:
            # Remove placeholder if no value provided
            system_prompt = system_prompt.replace(placeholder, "[Not provided]")
    
    # Personalize greeting
    greeting = template.greeting_message.replace("{business_name}", business_name)
    
    return system_prompt, greeting


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/list", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all available agent templates"""
    
    query = db.query(AgentTemplate).filter(AgentTemplate.is_active == True)
    
    if category:
        query = query.filter(AgentTemplate.category == category)
    
    templates = query.order_by(AgentTemplate.use_count.desc()).all()
    
    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            category=t.category,
            description=t.description,
            system_prompt=t.system_prompt,
            greeting_message=t.greeting_message,
            sample_questions=t.sample_questions,
            recommended_voice=t.recommended_voice,
            tags=t.tags,
            use_count=t.use_count
        )
        for t in templates
    ]


@router.get("/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Get all template categories"""
    
    categories = db.query(AgentTemplate.category).distinct().all()
    
    return {
        "categories": [cat[0] for cat in categories]
    }


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: int, db: Session = Depends(get_db)):
    """Get specific template details"""
    
    template = db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return TemplateResponse(
        id=template.id,
        name=template.name,
        category=template.category,
        description=template.description,
        system_prompt=template.system_prompt,
        greeting_message=template.greeting_message,
        sample_questions=template.sample_questions,
        recommended_voice=template.recommended_voice,
        tags=template.tags,
        use_count=template.use_count
    )


@router.post("/create-agent")
async def create_agent_from_template(
    request: CreateAgentFromTemplateRequest,
    db: Session = Depends(get_db)
):
    """Create AI agent from template with customizations"""
    
    # Get template
    template = db.query(AgentTemplate).filter(AgentTemplate.id == request.template_id).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Personalize template
    system_prompt, greeting = personalize_template(
        template,
        request.business_name,
        business_hours=request.business_hours,
        website=request.website
    )
    
    # Apply custom overrides
    if request.custom_prompt:
        system_prompt = request.custom_prompt
    if request.custom_greeting:
        greeting = request.custom_greeting
    
    # Add additional instructions if provided
    if request.additional_instructions:
        system_prompt += f"\n\nAdditional instructions:\n{request.additional_instructions}"
    
    voice = request.voice or template.recommended_voice
    
    # Create Retell LLM
    llm_id = retell_service.create_llm(
        general_prompt=system_prompt,
        begin_message=greeting
    )
    
    # Create Retell Agent
    agent_id = retell_service.create_agent(
        name=f"{request.business_name} AI",
        llm_id=llm_id,
        voice_id=voice,
        publish=True
    )
    
    # Save to database
    ai_agent = AIAgent(
        user_id=request.user_id,
        name=f"{request.business_name} - {template.name}",
        retell_agent_id=agent_id,
        retell_llm_id=llm_id,
        system_prompt=system_prompt,
        greeting_message=greeting,
        voice_model=voice,
        is_active=True
    )
    
    db.add(ai_agent)
    
    # Update template use count
    template.use_count += 1
    
    db.commit()
    db.refresh(ai_agent)
    
    log.info(f"✅ Created agent from template '{template.name}' for {request.business_name}")
    
    return {
        "agent_id": agent_id,
        "llm_id": llm_id,
        "ai_agent_db_id": ai_agent.id,
        "template_used": template.name,
        "business_name": request.business_name,
        "system_prompt": system_prompt,
        "greeting": greeting,
        "message": f"AI agent created successfully from {template.name} template"
    }


@router.post("/seed-templates")
async def seed_default_templates(db: Session = Depends(get_db)):
    """Seed database with preset templates (admin only)"""
    
    created_count = 0
    
    for template_data in PRESET_TEMPLATES:
        # Check if template already exists
        existing = db.query(AgentTemplate).filter(
            AgentTemplate.name == template_data["name"]
        ).first()
        
        if not existing:
            template = AgentTemplate(**template_data)
            db.add(template)
            created_count += 1
    
    db.commit()
    
    return {
        "message": f"Seeded {created_count} new templates",
        "total_templates": db.query(AgentTemplate).count()
    }
