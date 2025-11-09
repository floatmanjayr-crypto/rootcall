import os
import requests
import json

class VoIPOnboarding:
    def __init__(self, telnyx_api_key: str, retell_api_key: str):
        self.telnyx_key = telnyx_api_key
        self.retell_key = retell_api_key
        self.telnyx_base = "https://api.telnyx.com/v2"
        self.retell_base = "https://api.retellai.com"
    
    def onboard_existing_number(self, phone_number_id: str, agent_id: str):
        pn_response = requests.get(
            f"{self.telnyx_base}/phone_numbers/{phone_number_id}",
            headers={"Authorization": f"Bearer {self.telnyx_key}"}
        )
        phone_number = pn_response.json()["data"]["phone_number"]
        
        conn_response = requests.get(
            f"{self.telnyx_base}/fqdn_connections/2812968115544000352",
            headers={"Authorization": f"Bearer {self.telnyx_key}"}
        )
        conn_data = conn_response.json()["data"]
        username = conn_data["user_name"]
        password = conn_data["password"]
        
        payload = {
            "phone_number": phone_number,
            "termination_uri": "sip:sip.telnyx.com",
            "outbound_authentication_username": username,
            "outbound_authentication_password": password,
            "inbound_agent_id": agent_id
        }
        
        response = requests.post(
            f"{self.retell_base}/import-phone-number",
            headers={
                "Authorization": f"Bearer {self.retell_key}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        return {"phone_number": phone_number, "agent_id": agent_id, "success": response.status_code in [200, 201]}

if __name__ == "__main__":
    onboarding = VoIPOnboarding(
        telnyx_api_key=os.getenv("TELNYX_API_KEY"),
        retell_api_key=os.getenv("RETELL_API_KEY")
    )
    
    result = onboarding.onboard_existing_number(
        phone_number_id="2691045353678963984",
        agent_id="agent_238bee69706e1db87d1d0ad131"
    )
    
    print(json.dumps(result, indent=2))
