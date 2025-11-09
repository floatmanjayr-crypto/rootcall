# -*- coding: utf-8 -*-
import os
import requests
import json
import secrets
import string
import time
from urllib.parse import quote

class ClientOnboarding:
    def __init__(self):
        self.telnyx_key = os.getenv("TELNYX_API_KEY")
        self.retell_key = os.getenv("RETELL_API_KEY")
        self.telnyx_base = "https://api.telnyx.com/v2"
        self.retell_base = "https://api.retellai.com"
        self.ovp_id = "2812737864519911048"
    
    def provision_new_client(self, client_name, area_code, agent_id=None):
        print(f"\níº€ Starting onboarding for: {client_name}")
        
        print("\n[1/5] Creating SIP trunk...")
        conn_name = f"{client_name.lower().replace(' ', '-')}-{int(time.time())}"
        username = f"{client_name.lower().replace(' ', '')}{int(time.time())}"
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
        
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
            raise Exception(f"Connection failed: {conn_resp.text}")
        
        conn_id = conn_resp.json()["data"]["id"]
        print(f"   âœ“ Connection created: {conn_id}")
        
        print("\n[2/5] Configuring Retell routing...")
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
            raise Exception(f"FQDN failed: {fqdn_resp.text}")
        
        print("   âœ“ Retell FQDN configured")
        
        print(f"\n[3/5] Purchasing phone number in area code {area_code}...")
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
            raise Exception(f"No numbers available in {area_code}")
        
        phone_number = search_resp.json()["data"][0]["phone_number"]
        
        order_resp = requests.post(
            f"{self.telnyx_base}/number_orders",
            headers={"Authorization": f"Bearer {self.telnyx_key}", "Content-Type": "application/json"},
            json={
                "phone_numbers": [{"phone_number": phone_number}],
                "connection_id": conn_id
            }
        )
        
        if order_resp.status_code not in [200, 201]:
            raise Exception(f"Purchase failed: {order_resp.text}")
        
        print(f"   âœ“ Purchased: {phone_number}")
        
        print("\n[4/5] Importing to Retell...")
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
        
        if agent_id:
            print("\n[5/5] Assigning AI agent...")
            encoded_number = quote(phone_number, safe='')
            agent_resp = requests.patch(
                f"{self.retell_base}/update-phone-number/{encoded_number}",
                headers={"Authorization": f"Bearer {self.retell_key}", "Content-Type": "application/json"},
                json={"inbound_agent_id": agent_id}
            )
            
            if agent_resp.status_code not in [200, 201]:
                print(f"   âš  Agent assignment failed: {agent_resp.text}")
                agent_assigned = False
            else:
                print(f"   âœ“ AI agent assigned: {agent_id}")
                agent_assigned = True
        else:
            print("\n[5/5] Skipping AI agent (not requested)")
            agent_assigned = False
        
        result = {
            "client_name": client_name,
            "phone_number": phone_number,
            "connection_id": conn_id,
            "connection_name": conn_name,
            "sip_credentials": {
                "username": username,
                "password": password,
                "fqdn": "sip.retellai.com"
            },
            "ai_enabled": agent_assigned,
            "agent_id": agent_id if agent_assigned else None
        }
        
        print("\n" + "="*60)
        print("âœ… ONBOARDING COMPLETE!")
        print("="*60)
        print(f"Phone: {phone_number}")
        print(f"Connection: {conn_name}")
        if agent_assigned:
            print(f"AI Agent: {agent_id}")
        print("\nCall the number to test your AI agent!")
        
        return result

if __name__ == "__main__":
    onboarding = ClientOnboarding()
    
    result = onboarding.provision_new_client(
        client_name="Demo Client",
        area_code="813",
        agent_id="agent_238bee69706e1db87d1d0ad131"
    )
    
    print("\ní³‹ Save this to your database:")
    print(json.dumps(result, indent=2))
