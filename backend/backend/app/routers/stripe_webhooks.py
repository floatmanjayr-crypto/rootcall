# -*- coding: utf-8 -*-
"""Stripe Webhook Handler - Auto-provision after payment"""
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
        
        log.info(f"Payment successful for user {user.email}")
        
        # Auto-provision RootCall service
        try:
            result = await auto_provision_rootcall(
                user_id=user.id,
                user_name=user.full_name,
                user_email=user.email,
                db=db
            )
            
            log.info(f"Auto-provisioning complete for {user.email}")
            log.info("RootCall Number: %s", result.get("rootcall_number"))
            
            # TODO: Send welcome email with number
            
        except Exception as e:
            log.error(f"Auto-provisioning failed: {e}")
            # Still return 200 to Stripe, but log the error
    
    return {"status": "success"}


async def auto_provision_rootcall(user_id: int, user_name: str, user_email: str, db: Session):
    """Automatically provision complete RootCall setup after payment"""
    
    log.info(f" Auto-provisioning RootCall for {user_name}...")
    
    # Step 1: Purchase Telnyx number
    log.info("  [1/6] Purchasing Telnyx number...")
    phone_number = purchase_telnyx_number(area_code="813")  # Default to Tampa
    log.info(f"      Purchased: {phone_number}")
    
    # Step 2: Create Retell LLM
    log.info("  [2/6] Creating Retell LLM...")
    llm_id = create_retell_llm(user_name)
    log.info(f"      LLM: {llm_id}")
    
    # Step 3: Create Retell Agent
    log.info("  [3/6] Creating Retell Agent...")
    agent_id = create_retell_agent(user_name, llm_id)
    log.info(f"      Agent: {agent_id}")
    
    # Step 4: Import number to Retell
    log.info("  [4/6] Importing to Retell...")
    import_to_retell(phone_number, agent_id)
    log.info(f"      Imported")
    
    # Step 5: Save to database
    log.info("  [5/6] Saving to database...")
    
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
    
    log.info(f"      Database saved")
    
    return {
        "success": True,
        "user_name": user_name,
        "rootcall_number": phone_number,
        "agent_id": agent_id,
        "llm_id": llm_id
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
        raise Exception(f"No numbers available")
    
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
    """Create Retell LLM"""
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""You are RootCall, protecting {client_name} from phone scams.

Ask who's calling and why. Detect scam indicators:
- IRS/police threats
- Tech support scams
- Prize/lottery scams
- Request for personal info

If SCAM: Politely end call
If LEGITIMATE: Say "One moment" and transfer

Be brief and protective."""
    
    response = requests.post(
        f"{RETELL_BASE}/create-retell-llm",
        headers=headers,
        json={
            "general_prompt": prompt,
            "model": "gpt-4o-mini"
        }
    )
    
    if response.status_code not in [200, 201]:
        raise Exception(f"LLM creation failed: {response.text}")
    
    return response.json()["llm_id"]


def create_retell_agent(client_name, llm_id):
    """Create Retell Agent"""
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{RETELL_BASE}/create-agent",
        headers=headers,
        json={
            "agent_name": f"RootCall - {client_name}",
            "llm_id": llm_id,
            "voice_id": "11labs-Adrian",
            "responsiveness": 1
        }
    )
    
    if response.status_code not in [200, 201]:
        raise Exception(f"Agent creation failed: {response.text}")
    
    return response.json()["agent_id"]


def import_to_retell(phone_number, agent_id):
    """Import number to Retell"""
    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    requests.post(
        f"{RETELL_BASE}/import-phone-number",
        headers=headers,
        json={
            "phone_number": phone_number,
            "agent_id": agent_id
        }
    )
