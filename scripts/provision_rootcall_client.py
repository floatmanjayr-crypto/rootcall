# -*- coding: utf-8 -*-
"""
RootCall Multi-Client Provisioning System
Option 2: Separate Retell Agent Per Client

Complete flow:
1. Purchase Telnyx number
2. Create dedicated Retell LLM for client
3. Create dedicated Retell Agent for client
4. Import number to Retell with client's agent
5. Configure SIP trunk
6. Create RootCallConfig in database
"""
import os
import sys
import json
import requests
import subprocess
from typing import Dict, Optional

# Configuration
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
BACKEND_WEBHOOK_URL = os.getenv("BACKEND_WEBHOOK_URL", "https://your-domain.com/telnyx/rootcall/webhook")

TELNYX_BASE = "https://api.telnyx.com/v2"
RETELL_BASE = "https://api.retellai.com"


class RootCallProvisioner:
    """Provision complete RootCall setup for a new client"""
    
    def __init__(self, client_name: str, client_cell: str, area_code: str = "813"):
        self.client_name = client_name
        self.client_cell = client_cell
        self.area_code = area_code
        
        self.telnyx_number = None
        self.telnyx_connection_id = None
        self.retell_llm_id = None
        self.retell_agent_id = None
        
        print(f"\n{'='*60}")
        print(f"RootCall Provisioning for: {client_name}")
        print(f"Client Cell: {client_cell}")
        print(f"Area Code: {area_code}")
        print(f"{'='*60}\n")
    
    def provision_telnyx_number(self) -> str:
        """Step 1: Purchase Telnyx phone number"""
        print("Ì¥π Step 1: Purchasing Telnyx number...")
        
        # Search for available numbers
        search_url = f"{TELNYX_BASE}/available_phone_numbers"
        params = {
            "filter[country_code]": "US",
            "filter[features]": "sms,voice",
            "filter[limit]": 1
        }
        
        if self.area_code:
            params["filter[national_destination_code]"] = self.area_code
        
        headers = {"Authorization": f"Bearer {TELNYX_API_KEY}"}
        
        response = requests.get(search_url, headers=headers, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Failed to search numbers: {response.text}")
        
        available = response.json().get("data", [])
        
        if not available:
            raise Exception(f"No numbers available in area code {self.area_code}")
        
        phone_number = available[0]["phone_number"]
        phone_number_id = available[0]["id"]
        
        print(f"   Found available: {phone_number}")
        
        # Purchase the number
        purchase_url = f"{TELNYX_BASE}/phone_numbers/{phone_number_id}/actions/purchase"
        
        response = requests.post(purchase_url, headers=headers, json={})
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to purchase: {response.text}")
        
        self.telnyx_number = phone_number
        
        print(f"   ‚úÖ Purchased: {phone_number}")
        return phone_number
    
    def create_sip_trunk(self) -> str:
        """Step 2: Create or use existing SIP trunk"""
        print("\nÌ¥π Step 2: Configuring SIP trunk...")
        
        # Check if trunk exists
        headers = {"Authorization": f"Bearer {TELNYX_API_KEY}"}
        
        response = requests.get(
            f"{TELNYX_BASE}/texml_applications",
            headers=headers
        )
        
        if response.status_code == 200:
            apps = response.json().get("data", [])
            
            # Look for existing RootCall trunk
            for app in apps:
                if "RootCall" in app.get("friendly_name", ""):
                    connection_id = app["id"]
                    print(f"   ‚úÖ Using existing trunk: {connection_id}")
                    self.telnyx_connection_id = connection_id
                    return connection_id
        
        # Create new trunk
        print("   Creating new SIP trunk...")
        
        trunk_data = {
            "friendly_name": "RootCall SIP Trunk",
            "active": True,
            "webhook_event_url": BACKEND_WEBHOOK_URL,
            "webhook_event_failover_url": "",
            "webhook_timeout_secs": 25,
            "first_command_timeout": True,
            "first_command_timeout_secs": 10
        }
        
        response = requests.post(
            f"{TELNYX_BASE}/texml_applications",
            headers=headers,
            json=trunk_data
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create trunk: {response.text}")
        
        connection_id = response.json()["data"]["id"]
        self.telnyx_connection_id = connection_id
        
        print(f"   ‚úÖ Created trunk: {connection_id}")
        return connection_id
    
    def assign_number_to_trunk(self):
        """Step 3: Assign purchased number to SIP trunk"""
        print("\nÌ¥π Step 3: Assigning number to trunk...")
        
        headers = {"Authorization": f"Bearer {TELNYX_API_KEY}"}
        
        # Find phone number ID
        response = requests.get(
            f"{TELNYX_BASE}/phone_numbers",
            headers=headers,
            params={"filter[phone_number]": self.telnyx_number}
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to find number: {response.text}")
        
        phones = response.json().get("data", [])
        if not phones:
            raise Exception(f"Number {self.telnyx_number} not found")
        
        phone_id = phones[0]["id"]
        
        # Update connection
        update_url = f"{TELNYX_BASE}/phone_numbers/{phone_id}"
        
        response = requests.patch(
            update_url,
            headers=headers,
            json={
                "connection_id": self.telnyx_connection_id
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to assign: {response.text}")
        
        print(f"   ‚úÖ Assigned {self.telnyx_number} to trunk")
    
    def create_retell_llm(self) -> str:
        """Step 4: Create dedicated Retell LLM for client"""
        print("\nÌ¥π Step 4: Creating Retell LLM...")
        
        # Personalized RootCall prompt for this client
        prompt = f"""You are RootCall, an AI assistant protecting {self.client_name}'s phone line from scams and fraud.

Your job:
1. Answer the phone professionally
2. Ask who is calling and their reason
3. Determine if the call is:
   - Legitimate business/personal
   - Potential scam (IRS, tech support, bank fraud, etc.)
   - Sales/marketing

If SCAM detected:
- Do NOT transfer
- Politely end the call
- Say "I'm sorry, this line doesn't accept unsolicited calls"

If LEGITIMATE:
- Be polite and helpful
- Say "One moment please, I'll connect you"
- Transfer to {self.client_name}

Red flags (SCAM):
- IRS calling about arrest warrant
- Tech support for computer virus
- Bank asking for account details
- Prize/lottery winnings
- Medicare/Social Security threats
- Gift card payments

Be conversational but brief. Protect {self.client_name} from fraud!"""
        
        headers = {
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        llm_data = {
            "general_prompt": prompt,
            "general_tools": [],
            "states": [],
            "starting_state": "default",
            "model": "gpt-4o-mini"
        }
        
        response = requests.post(
            f"{RETELL_BASE}/create-retell-llm",
            headers=headers,
            json=llm_data
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create LLM: {response.text}")
        
        result = response.json()
        self.retell_llm_id = result.get("llm_id")
        
        print(f"   ‚úÖ Created LLM: {self.retell_llm_id}")
        return self.retell_llm_id
    
    def create_retell_agent(self) -> str:
        """Step 5: Create dedicated Retell Agent"""
        print("\nÌ¥π Step 5: Creating Retell Agent...")
        
        headers = {
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        agent_data = {
            "agent_name": f"RootCall - {self.client_name}",
            "llm_id": self.retell_llm_id,
            "voice_id": "11labs-Adrian",  # Professional male voice
            "voice_temperature": 1,
            "voice_speed": 1,
            "responsiveness": 1,
            "interruption_sensitivity": 1,
            "enable_backchannel": True,
            "backchannel_frequency": 0.8,
            "reminder_trigger_ms": 10000,
            "reminder_max_count": 2,
            "ambient_sound": "office",
            "language": "en-US",
            "webhook_url": f"{BACKEND_WEBHOOK_URL.replace('/telnyx/', '/retell/')}/call-result",
            "boosted_keywords": ["scam", "fraud", "IRS", "arrest", "social security"]
        }
        
        response = requests.post(
            f"{RETELL_BASE}/create-agent",
            headers=headers,
            json=agent_data
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create agent: {response.text}")
        
        result = response.json()
        self.retell_agent_id = result.get("agent_id")
        
        print(f"   ‚úÖ Created Agent: {self.retell_agent_id}")
        return self.retell_agent_id
    
    def import_number_to_retell(self):
        """Step 6: Import Telnyx number to Retell"""
        print("\nÌ¥π Step 6: Importing number to Retell...")
        
        headers = {
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        import_data = {
            "phone_number": self.telnyx_number,
            "agent_id": self.retell_agent_id,
            "inbound_webhook_url": f"{BACKEND_WEBHOOK_URL.replace('/telnyx/', '/retell/')}/inbound"
        }
        
        response = requests.post(
            f"{RETELL_BASE}/import-phone-number",
            headers=headers,
            json=import_data
        )
        
        if response.status_code not in [200, 201]:
            print(f"   ‚ö†Ô∏è  Import warning: {response.text}")
            print(f"   Note: May need to import manually or number already imported")
        else:
            print(f"   ‚úÖ Imported to Retell")
    
    def create_database_config(self, user_id: int = 1):
        """Step 7: Create RootCallConfig in database"""
        print("\nÌ¥π Step 7: Creating database config...")
        
        sys.path.append(".")
        from app.database import SessionLocal
        from app.models.phone_number import PhoneNumber
        from app.models.rootcall_config import RootCallConfig
        from app.models.ai_agent import AIAgent
        
        db = SessionLocal()
        
        try:
            # Create PhoneNumber record
            phone = PhoneNumber(
                user_id=user_id,
                phone_number=self.telnyx_number,
                friendly_name=f"RootCall - {self.client_name}",
                country_code="US",
                telnyx_connection_id=self.telnyx_connection_id,
                is_active=True,
                monthly_cost=2.0
            )
            db.add(phone)
            db.flush()
            
            print(f"   ‚úÖ Created PhoneNumber: {phone.id}")
            
            # Create AIAgent record
            agent = AIAgent(
                user_id=user_id,
                name=f"RootCall Agent - {self.client_name}",
                description=f"AI call screening for {self.client_name}",
                retell_agent_id=self.retell_agent_id,
                retell_llm_id=self.retell_llm_id,
                system_prompt=f"RootCall AI for {self.client_name}",
                is_active=True
            )
            db.add(agent)
            db.flush()
            
            phone.ai_agent_id = agent.id
            
            print(f"   ‚úÖ Created AIAgent: {agent.id}")
            
            # Create RootCallConfig
            config = RootCallConfig(
                phone_number_id=phone.id,
                user_id=user_id,
                client_name=self.client_name,
                client_cell=self.client_cell,
                retell_agent_id=self.retell_agent_id,
                retell_did=self.telnyx_number,
                trusted_contacts=[],
                caregiver_cell="",
                sms_alerts_enabled=True,
                alert_on_spam=True,
                alert_on_unknown=False,
                auto_block_spam=True,
                is_active=True
            )
            db.add(config)
            db.commit()
            
            print(f"   ‚úÖ Created RootCallConfig: {config.id}")
            
        except Exception as e:
            db.rollback()
            raise Exception(f"Database error: {e}")
        finally:
            db.close()
    
    def provision_complete(self) -> Dict:
        """Run complete provisioning flow"""
        try:
            # Execute all steps
            self.provision_telnyx_number()
            self.create_sip_trunk()
            self.assign_number_to_trunk()
            self.create_retell_llm()
            self.create_retell_agent()
            self.import_number_to_retell()
            self.create_database_config()
            
            print(f"\n{'='*60}")
            print("‚úÖ PROVISIONING COMPLETE!")
            print(f"{'='*60}")
            
            result = {
                "success": True,
                "client_name": self.client_name,
                "rootcall_number": self.telnyx_number,
                "client_cell": self.client_cell,
                "retell_agent_id": self.retell_agent_id,
                "retell_llm_id": self.retell_llm_id,
                "telnyx_connection_id": self.telnyx_connection_id
            }
            
            print("\nÌ≥ã Summary:")
            print(f"   RootCall Number: {self.telnyx_number}")
            print(f"   Client Cell: {self.client_cell}")
            print(f"   Retell Agent: {self.retell_agent_id}")
            print(f"   Retell LLM: {self.retell_llm_id}")
            
            print("\nÌ≥û Next Steps:")
            print(f"   1. Client forwards {self.client_cell} to {self.telnyx_number}")
            print(f"   2. Add trusted contacts via portal")
            print(f"   3. Test by calling {self.telnyx_number}")
            
            # Save to file
            with open(f"rootcall_provision_{self.telnyx_number.replace('+', '')}.json", "w") as f:
                json.dump(result, f, indent=2)
            
            print(f"\nÌ≤æ Config saved to: rootcall_provision_{self.telnyx_number.replace('+', '')}.json")
            
            return result
            
        except Exception as e:
            print(f"\n‚ùå PROVISIONING FAILED: {e}")
            raise


def main():
    """CLI for provisioning"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Provision RootCall for new client")
    parser.add_argument("--name", required=True, help="Client name")
    parser.add_argument("--cell", required=True, help="Client cell phone (+1234567890)")
    parser.add_argument("--area-code", default="813", help="Preferred area code")
    parser.add_argument("--user-id", type=int, default=1, help="Database user ID")
    
    args = parser.parse_args()
    
    provisioner = RootCallProvisioner(
        client_name=args.name,
        client_cell=args.cell,
        area_code=args.area_code
    )
    
    provisioner.provision_complete()


if __name__ == "__main__":
    # Check environment variables
    if not TELNYX_API_KEY:
        print("‚ùå Error: TELNYX_API_KEY not set")
        sys.exit(1)
    
    if not RETELL_API_KEY:
        print("‚ùå Error: RETELL_API_KEY not set")
        sys.exit(1)
    
    main()
