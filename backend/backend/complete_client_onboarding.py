# -*- coding: utf-8 -*-
import os
import requests
import json
import secrets
import string
import time
from urllib.parse import quote

class VoIPClientOnboarding:
    """
    Complete client onboarding system:
    1. Client purchases subscription
    2. Create user account credentials
    3. Purchase new number OR import existing number
    4. Create SIP trunk with Retell routing
    5. Import to Retell (optional: attach AI agent)
    6. Return all credentials to save in database
    """
    
    def __init__(self):
        self.telnyx_key = os.getenv("TELNYX_API_KEY")
        self.retell_key = os.getenv("RETELL_API_KEY")
        self.telnyx_base = "https://api.telnyx.com/v2"
        self.retell_base = "https://api.retellai.com"
        self.ovp_id = "2812737864519911048"
    
    def onboard_client(self, 
                      client_name,
                      client_email,
                      area_code=None,
                      existing_phone_number_id=None,
                      conversational_ai=False,
                      agent_id=None):
        """
        Complete onboarding workflow
        
        Args:
            client_name: Client's business name
            client_email: Client's email
            area_code: Area code for new number (if purchasing)
            existing_phone_number_id: Telnyx ID of existing number to import
            conversational_ai: True if client wants AI agent
            agent_id: Retell agent ID (required if conversational_ai=True)
        
        Returns:
            dict: All credentials and IDs to save in database
        """
        
        print(f"\n{'='*60}")
        print(f"CLIENT ONBOARDING: {client_name}")
        print(f"{'='*60}")
        
        # Step 1: Generate user credentials
        print("\n[1/6] Generating user credentials...")
        username = f"{client_name.lower().replace(' ', '')}{int(time.time())}"
        password = self._generate_password()
        print(f"   âœ“ Username: {username}")
        print(f"   âœ“ Password: {password}")
        
        # Step 2: Create SIP trunk
        print("\n[2/6] Creating SIP trunk...")
        conn_name = f"{client_name.lower().replace(' ', '-')}-{int(time.time())}"
        
        conn_resp = requests.post(
            f"{self.telnyx_base}/fqdn_connections",
            headers={"Authorization": f"Bearer {self.telnyx_key}", "Content-Type": "application/json"},
            json={
                "connection_name": conn_name,
                "transport_protocol": "TCP",
                "user_name": username,
                "password": password,
                "inbound": {
                    "ani_number_format": "+E.164",
                    "codecs": ["G722", "G729", "OPUS"],
                    "sip_region": "US"
                },
                "outbound": {
                    "fqdn_authentication_method": "credential-authentication",
                    "outbound_voice_profile_id": self.ovp_id
                }
            }
        )
        
        if conn_resp.status_code != 201:
            raise Exception(f"SIP trunk creation failed: {conn_resp.text}")
        
        conn_id = conn_resp.json()["data"]["id"]
        print(f"   âœ“ SIP trunk created: {conn_id}")
        
        # Step 3: Configure Retell routing
        print("\n[3/6] Configuring Retell routing...")
        fqdn_resp = requests.post(
            f"{self.telnyx_base}/fqdns",
            headers={"Authorization": f"Bearer {self.telnyx_key}", "Content-Type": "application/json"},
            json={
                "connection_id": conn_id,
                "fqdn": "sip.retellai.com",
                "dns_record_type": "srv"
            }
        )
        
        if fqdn_resp.status_code != 201:
            raise Exception(f"Retell FQDN configuration failed: {fqdn_resp.text}")
        
        print("   âœ“ Retell routing configured")
        
        # Step 4: Get/Purchase phone number
        if existing_phone_number_id:
            print(f"\n[4/6] Importing existing number...")
            # Get existing number details
            pn_resp = requests.get(
                f"{self.telnyx_base}/phone_numbers/{existing_phone_number_id}",
                headers={"Authorization": f"Bearer {self.telnyx_key}"}
            )
            
            if pn_resp.status_code != 200:
                raise Exception(f"Failed to get phone number: {pn_resp.text}")
            
            phone_number = pn_resp.json()["data"]["phone_number"]
            
            # Assign to connection
            assign_resp = requests.patch(
                f"{self.telnyx_base}/phone_numbers/{existing_phone_number_id}",
                headers={"Authorization": f"Bearer {self.telnyx_key}", "Content-Type": "application/json"},
                json={"connection_id": conn_id}
            )
            
            if assign_resp.status_code != 200:
                raise Exception(f"Failed to assign number: {assign_resp.text}")
            
            print(f"   âœ“ Imported existing number: {phone_number}")
        
        else:
            print(f"\n[4/6] Purchasing new number in area code {area_code}...")
            # Search for available numbers
            search_resp = requests.get(
                f"{self.telnyx_base}/available_phone_numbers",
                headers={"Authorization": f"Bearer {self.telnyx_key}"},
                params={
                    "filter[country_code]": "US",
                    "filter[features]": "sms,mms,voice",
                    "filter[national_destination_code]": area_code,
                    "filter[limit]": 1
                }
            )
            
            if search_resp.status_code != 200 or not search_resp.json()["data"]:
                raise Exception(f"No numbers available in area code {area_code}")
            
            phone_number = search_resp.json()["data"][0]["phone_number"]
            
            # Purchase number
            order_resp = requests.post(
                f"{self.telnyx_base}/number_orders",
                headers={"Authorization": f"Bearer {self.telnyx_key}", "Content-Type": "application/json"},
                json={
                    "phone_numbers": [{"phone_number": phone_number}],
                    "connection_id": conn_id
                }
            )
            
            if order_resp.status_code not in [200, 201]:
                raise Exception(f"Number purchase failed: {order_resp.text}")
            
            print(f"   âœ“ Purchased new number: {phone_number}")
        
        # Step 5: Import to Retell
        print("\n[5/6] Importing to Retell...")
        retell_resp = requests.post(
            f"{self.retell_base}/import-phone-number",
            headers={"Authorization": f"Bearer {self.retell_key}", "Content-Type": "application/json"},
            json={
                "phone_number": phone_number,
                "termination_uri": "sip.telnyx.com",
                "outbound_authentication_username": username,
                "outbound_authentication_password": password
            }
        )
        
        if retell_resp.status_code not in [200, 201]:
            raise Exception(f"Retell import failed: {retell_resp.text}")
        
        print("   âœ“ Number imported to Retell")
        
        # Step 6: Attach AI agent (if requested)
        ai_agent_assigned = False
        if conversational_ai:
            if not agent_id:
                raise Exception("agent_id required when conversational_ai=True")
            
            print(f"\n[6/6] Attaching AI agent...")
            encoded_number = quote(phone_number, safe='')
            agent_resp = requests.patch(
                f"{self.retell_base}/update-phone-number/{encoded_number}",
                headers={"Authorization": f"Bearer {self.retell_key}", "Content-Type": "application/json"},
                json={"inbound_agent_id": agent_id}
            )
            
            if agent_resp.status_code not in [200, 201]:
                raise Exception(f"AI agent assignment failed: {agent_resp.text}")
            
            print(f"   âœ“ AI agent attached: {agent_id}")
            ai_agent_assigned = True
        else:
            print(f"\n[6/6] Skipping AI agent (not purchased)")
        
        # Prepare data for database
        client_data = {
            "client_info": {
                "name": client_name,
                "email": client_email
            },
            "phone_number": phone_number,
            "sip_credentials": {
                "username": username,
                "password": password,
                "connection_id": conn_id,
                "connection_name": conn_name,
                "sip_server": "sip.retellai.com",
                "transport": "TCP"
            },
            "features": {
                "conversational_ai": conversational_ai,
                "ai_agent_id": agent_id if ai_agent_assigned else None
            },
            "provisioned_at": time.time()
        }
        
        print(f"\n{'='*60}")
        print("âœ… ONBOARDING COMPLETE!")
        print(f"{'='*60}")
        print(f"Client: {client_name}")
        print(f"Email: {client_email}")
        print(f"Phone: {phone_number}")
        print(f"AI Agent: {'Yes' if ai_agent_assigned else 'No'}")
        print(f"\ní²¾ Save the returned data to your database")
        
        return client_data
    
    def _generate_password(self):
        """Generate secure random password"""
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(16))


# Example usage scenarios
if __name__ == "__main__":
    onboarding = VoIPClientOnboarding()
    
    # Scenario 1: New client purchases number + AI agent
    print("\n" + "="*60)
    print("SCENARIO 1: Purchase new number with AI agent")
    print("="*60)
    result1 = onboarding.onboard_client(
        client_name="Acme Insurance",
        client_email="admin@acmeinsurance.com",
        area_code="813",
        conversational_ai=True,
        agent_id="agent_238bee69706e1db87d1d0ad131"
    )
    print("\ní³‹ Database record:")
    print(json.dumps(result1, indent=2))
    
    # Scenario 2: Client brings existing number, no AI
    # result2 = onboarding.onboard_client(
    #     client_name="Basic Phone Co",
    #     client_email="admin@basicphone.com",
    #     existing_phone_number_id="2691045353678963984",
    #     conversational_ai=False
    # )
    # print(json.dumps(result2, indent=2))
