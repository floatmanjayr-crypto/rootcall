"""
Updated Client Config Service - Database-driven
Replace: app/services/client_config.py
Reads RootCall configuration from database instead of hardcoded CLIENT_LINES
"""
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.rootcall_config import RootCallConfig
from app.models.phone_number import PhoneNumber
import logging

log = logging.getLogger("rootcall")

# Legacy hardcoded config for backward compatibility (optional)
CLIENT_LINES: Dict[str, Dict] = {
    "+18135478218": {
        "client_cell": "+17543314009",
        "client_name": "Primary Senior Client",
        "retell_agent_id": "agent_cde1ba4c8efa2aba5665a77b91",
        "retell_did": "+18135478218",
        "trusted_contacts": [],
        "caregiver_cell": ""
    }
}

def get_client_config(telnyx_number: str, db: Session = None) -> Optional[Dict]:
    """
    Get RootCall configuration for a phone number
    First checks database, falls back to hardcoded CLIENT_LINES for backward compatibility
    
    Args:
        telnyx_number: The phone number to look up (e.g., "+18135478218")
        db: Optional database session (creates one if not provided)
    
    Returns:
        Dict with configuration or None if not found
    """
    # Normalize phone number
    normalized = telnyx_number.strip()
    if not normalized.startswith("+"):
        normalized = f"+{normalized}"
    
    # Try database first
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True
    
    try:
        # Find phone number in database
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == normalized
        ).first()
        
        if phone:
            # Query RootCallConfig directly - FIXED
            config = db.query(RootCallConfig).filter(
                RootCallConfig.phone_number_id == phone.id
            ).first()
            
            if config:
                # Convert database model to dict format expected by screening logic
                result = {
                    "client_cell": config.client_cell,
                    "client_name": config.client_name,
                    "retell_agent_id": config.retell_agent_id,
                    "retell_did": config.retell_did,
                    "trusted_contacts": config.trusted_contacts or [],
                    "caregiver_cell": config.caregiver_cell or "",
                    "sms_alerts_enabled": config.sms_alerts_enabled,
                    "alert_on_spam": config.alert_on_spam,
                    "alert_on_unknown": config.alert_on_unknown,
                    "auto_block_spam": config.auto_block_spam,
                }
                log.info(f"[DB CONFIG] Loaded config for {normalized}: {config.client_name}")
                return result
            else:
                log.warning(f"[DB CONFIG] No RootCall config found for phone {phone.id}")
                
    except Exception as e:
        log.error(f"[DB CONFIG] Error loading config for {normalized}: {e}")
    finally:
        if should_close_db:
            db.close()
    
    # Fallback to hardcoded config for backward compatibility
    if normalized in CLIENT_LINES:
        log.info(f"[HARDCODED CONFIG] Using fallback config for {normalized}")
        return CLIENT_LINES[normalized]
    
    log.warning(f"[CONFIG] No configuration found for {normalized}")
    return None

def get_trusted_contacts(telnyx_number: str, db: Session = None) -> list:
    """Get list of trusted phone numbers for a given Telnyx number"""
    config = get_client_config(telnyx_number, db)
    if config:
        return config.get("trusted_contacts", [])
    return []

def is_trusted_contact(telnyx_number: str, caller_number: str, db: Session = None) -> bool:
    """Check if a caller is on the trusted contact list"""
    trusted = get_trusted_contacts(telnyx_number, db)
    
    # Normalize caller number
    caller_normalized = caller_number.strip()
    if not caller_normalized.startswith("+"):
        caller_normalized = f"+{caller_normalized}"
    
    return caller_normalized in trusted

def add_trusted_contact(telnyx_number: str, contact_number: str, db: Session) -> bool:
    """Add a number to the trusted contacts list"""
    try:
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == telnyx_number
        ).first()
        
        if not phone:
            return False
            
        config = db.query(RootCallConfig).filter(
            RootCallConfig.phone_number_id == phone.id
        ).first()
        
        if not config:
            return False
        
        # Normalize contact number
        contact_normalized = contact_number.strip()
        if not contact_normalized.startswith("+"):
            contact_normalized = f"+{contact_normalized}"
        
        # Add to list if not already there
        if config.trusted_contacts is None:
            config.trusted_contacts = []
            
        if contact_normalized not in config.trusted_contacts:
            config.trusted_contacts.append(contact_normalized)
            db.commit()
            log.info(f"[CONFIG] Added trusted contact {contact_normalized} for {telnyx_number}")
            return True
            
        return False
        
    except Exception as e:
        log.error(f"[CONFIG] Error adding trusted contact: {e}")
        db.rollback()
        return False

def remove_trusted_contact(telnyx_number: str, contact_number: str, db: Session) -> bool:
    """Remove a number from the trusted contacts list"""
    try:
        phone = db.query(PhoneNumber).filter(
            PhoneNumber.phone_number == telnyx_number
        ).first()
        
        if not phone:
            return False
            
        config = db.query(RootCallConfig).filter(
            RootCallConfig.phone_number_id == phone.id
        ).first()
        
        if not config:
            return False
        
        # Normalize contact number
        contact_normalized = contact_number.strip()
        if not contact_normalized.startswith("+"):
            contact_normalized = f"+{contact_normalized}"
        
        # Remove from list
        if config.trusted_contacts and contact_normalized in config.trusted_contacts:
            config.trusted_contacts.remove(contact_normalized)
            db.commit()
            log.info(f"[CONFIG] Removed trusted contact {contact_normalized} for {telnyx_number}")
            return True
            
        return False
        
    except Exception as e:
        log.error(f"[CONFIG] Error removing trusted contact: {e}")
        db.rollback()
        return False
