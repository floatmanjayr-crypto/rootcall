# -*- coding: utf-8 -*-
"""Stripe Webhook Handler - Auto-provision with personalized AI agent"""
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import stripe
import os
import json
from app.database import get_db
from app.models.user import User
from app.models.phone_number import PhoneNumber
from app.models.ai_agent import AIAgent
from app.models.rootcall_config import RootCallConfig
import requests
import logging

router = APIRouter(prefix="/api/stripe", tags=["Stripe Webhooks"])
log = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
TELNYX_BASE = "https://api.telnyx.com/v2"
RETELL_BASE = "https://api.retellai.com"

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhooks - auto-provision on successful payment"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        if WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except Exception as e:
        log.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Handle successful subscription creation
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Get user from metadata
        user_id = session.get('metadata', {}).get('user_id')
        if not user_id:
            log.error("No user_id in session metadata")
            return {"status": "error", "message": "No user_id"}

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            log.error(f"User {user_id} not found")
            return {"status": "error", "message": "User not found"}

        log.info(f"Ìæâ Payment successful for {user.full_name} ({user.email})")

        # Auto-provision RootCall service with personalized agent
        try:
            result = await auto_provision_rootcall(
                user_id=user.id,
                user_name=user.full_name,
                user_email=user.email,
                db=db
            )

            log.info(f"‚úÖ Auto-provisioning complete for {user.full_name}")
            log.info(f"Ì≥û RootCall Number: {result.get('rootcall_number')}")
            log.info(f"Ì¥ñ AI Agent: {result.get('agent_id')} (knows user as {user.full_name})")

            # TODO: Send welcome email with number

        except Exception as e:
            log.error(f"‚ùå Auto-provisioning failed: {e}")
            # Still return 200 to Stripe, but log the error

    return {"status": "success"}


async def auto_provision_rootcall(user_id: int, user_name: str, user_email: str, db: Session):
    """
    Automatically provision complete RootCall setup after payment
    - Purchases Telnyx number
    - Creates PERSONALIZED Retell AI agent that knows the user's name
    - Configures immediate call protection
    """

    log.info(f"Ì∫Ä Auto-provisioning RootCall for {user_name}...")

    # Step 1: Purchase Telnyx number
    log.info("  [1/6] Purchasing Telnyx number...")
    phone_number = purchase_telnyx_number(area_code="813")  # Default to Tampa
    log.info(f"      ‚úÖ Purchased: {phone_number}")

    # Step 2: Create Retell LLM with PERSONALIZED prompt
    log.info(f"  [2/6] Creating personalized AI agent for {user_name}...")
    llm_id = create_retell_llm(user_name)
    log.info(f"      ‚úÖ LLM Created: {llm_id}")

    # Step 3: Create Retell Agent
    log.info(f"  [3/6] Creating Retell Agent...")
    agent_id = create_retell_agent(user_name, llm_id)
    log.info(f"      ‚úÖ Agent Created: {agent_id}")

    # Step 4: Import number to Retell
    log.info(f"  [4/6] Importing {phone_number} to Retell...")
    import_to_retell(phone_number, agent_id)
    log.info(f"      ‚úÖ Number imported and active")

    # Step 5: Save to database
    log.info("  [5/6] Saving configuration to database...")

    # Create PhoneNumber
    phone = PhoneNumber(
        user_id=user_id,
        phone_number=phone_number,
        friendly_name=f"RootCall - {user_name}",
        country_code="US",
        is_active=True,
        monthly_cost=2.0
    )
    db.add(phone)
    db.flush()

    # Create AIAgent
    agent = AIAgent(
        user_id=user_id,
        name=f"RootCall Agent - {user_name}",
        retell_agent_id=agent_id,
        retell_llm_id=llm_id,
        system_prompt=f"You are protecting {user_name} from phone scams and unwanted calls.",
        greeting_message=f"Hello, you've reached the RootCall protection line for {user_name}. Who is calling, please?",
        is_active=True
    )
    db.add(agent)
    db.flush()

    phone.ai_agent_id = agent.id

    # Create RootCallConfig
    config = RootCallConfig(
        phone_number_id=phone.id,
        user_id=user_id,
        client_name=user_name,
        client_cell="",  # User will add in portal
        retell_agent_id=agent_id,
        retell_did=phone_number,
        trusted_contacts=[],
        sms_alerts_enabled=True,
        alert_on_spam=True,
        auto_block_spam=True,
        is_active=True
    )
    db.add(config)
    db.commit()

    log.info(f"      ‚úÖ Database saved")
    log.info(f"  [6/6] Ìæâ RootCall protection is now ACTIVE for {user_name}!")

    return {
        "success": True,
        "user_name": user_name,
        "rootcall_number": phone_number,
        "agent_id": agent_id,
        "llm_id": llm_id,
        "message": f"Your RootCall protection is active! AI agent knows you as {user_name} and is ready to protect you."
    }


def purchase_telnyx_number(area_code="813"):
    """Purchase a Telnyx number"""
    headers = {"Authorization": f"Bearer {TELNYX_API_KEY}"}

    # Search
    response = requests.get(
        f"{TELNYX_BASE}/available_phone_numbers",
        headers=headers,
        params={
            "filter[country_code]": "US",
            "filter[features]": "sms,voice",
            "filter[national_destination_code]": area_code,
            "filter[limit]": 1
        }
    )

    if response.status_code != 200 or not response.json().get("data"):
        raise Exception(f"No numbers available in area code {area_code}")

    phone = response.json()["data"][0]
    phone_number = phone["phone_number"]
    phone_id = phone["id"]

    # Purchase
    purchase_response = requests.post(
        f"{TELNYX_BASE}/phone_numbers/{phone_id}/actions/purchase",
        headers=headers
    )

    if purchase_response.status_code not in [200, 201]:
        raise Exception(f"Purchase failed: {purchase_response.text}")

    return phone_number


def create_retell_llm(client_name):
    """Create Retell LLM with PERSONALIZED prompt"""
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }

    # PERSONALIZED PROMPT - Agent knows the user's name
    prompt = f"""You are RootCall AI, the personal call screening assistant for {client_name}.

YOUR MISSION:
Protect {client_name} from phone scams, robocalls, and unwanted solicitations while allowing legitimate calls through.

GREETING:
"Hello, you've reached {client_name}'s RootCall protection line. May I ask who's calling and the reason for your call?"

SCREENING PROCESS:
1. Ask the caller to identify themselves and state their purpose
2. Listen carefully for scam indicators
3. Make a decision: TRANSFER or BLOCK

RED FLAGS (Auto-block these):
- IRS/tax threats ("You owe taxes, pay now or go to jail")
- Tech support scams ("Your computer has a virus")
- Prize/lottery scams ("You've won! Just pay fees first")
- Grandparent scams ("It's me, I need money urgently")
- Threats or intimidation
- Requests for personal information (SSN, credit card, passwords)
- Robocalls or pre-recorded messages
- Unknown solicitations

GREEN FLAGS (Transfer to {client_name}):
- Family members and friends by name
- Expected business calls
- Medical professionals
- Delivery notifications
- Appointments or reservations

RESPONSES:

For SCAMS:
"I'm sorry, this appears to be a fraudulent call. {client_name} does not wish to receive these calls. Please remove this number from your list. Goodbye."
Then END the call.

For LEGITIMATE calls:
"Thank you. One moment please while I connect you to {client_name}."
Then TRANSFER the call.

For UNSURE calls:
"Thank you for calling. {client_name} isn't available right now. May I take a message?"
Get name and callback number, then END the call.

TONE:
- Professional and polite
- Firm with scammers
- Helpful with legitimate callers
- Brief and efficient (30 seconds max per call)

Remember: You are {client_name}'s first line of defense. Be protective but courteous."""

    response = requests.post(
        f"{RETELL_BASE}/create-retell-llm",
        headers=headers,
        json={
            "general_prompt": prompt,
            "model": "gpt-4o-mini",
            "begin_message": f"Hello, you've reached {client_name}'s RootCall protection line. May I ask who's calling?"
        }
    )

    if response.status_code not in [200, 201]:
        raise Exception(f"LLM creation failed: {response.text}")

    return response.json()["llm_id"]


def create_retell_agent(client_name, llm_id):
    """Create Retell Agent with client's name"""
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{RETELL_BASE}/create-agent",
        headers=headers,
        json={
            "agent_name": f"RootCall Protection - {client_name}",
            "llm_id": llm_id,
            "voice_id": "11labs-Adrian",  # Professional, clear voice
            "responsiveness": 1,  # Fast response
            "enable_backchannel": True,  # Natural conversation
            "ambient_sound": "off",
            "language": "en-US"
        }
    )

    if response.status_code not in [200, 201]:
        raise Exception(f"Agent creation failed: {response.text}")

    return response.json()["agent_id"]


def import_to_retell(phone_number, agent_id):
    """Import number to Retell and activate immediately"""
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{RETELL_BASE}/import-phone-number",
        headers=headers,
        json={
            "phone_number": phone_number,
            "agent_id": agent_id
        }
    )

    if response.status_code not in [200, 201]:
        # Log but don't fail - number is still purchased
        log.warning(f"Retell import warning: {response.text}")
    
    return response.json() if response.status_code in [200, 201] else None
