# app/services/telnyx_service.py
from __future__ import annotations
import os
import logging
from typing import List, Dict, Any, Optional, Tuple

import requests
from telnyx import Telnyx
from app.config import settings

log = logging.getLogger(__name__)

TLX_API_KEY = settings.TELNYX_API_KEY
TLX_BASE = os.getenv("TELNYX_BASE", "https://api.telnyx.com/v2")
client = Telnyx(api_key=TLX_API_KEY)


class TelnyxService:
    """Telnyx provisioning with Elastic SIP Trunk for Retell"""

    def __init__(self, api_key: Optional[str] = None, base_url: str = TLX_BASE):
        self.api_key = api_key or TLX_API_KEY
        if not self.api_key:
            raise RuntimeError("Missing TELNYX_API_KEY")
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Dict[str, Any] | None = None, ok=(200,)) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}{path}", headers=self.headers, params=params, timeout=30)
        if r.status_code not in ok:
            log.error("GET %s failed [%s]: %s", path, r.status_code, r.text)
            raise RuntimeError(r.text)
        return r.json()

    def _post(self, path: str, json: Dict[str, Any], ok=(200, 201)) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}{path}", headers=self.headers, json=json, timeout=30)
        if r.status_code not in ok:
            log.error("POST %s failed [%s]: %s", path, r.status_code, r.text)
            raise RuntimeError(r.text)
        return r.json()

    def _patch(self, path: str, json: Dict[str, Any], ok=(200,)) -> Dict[str, Any]:
        r = requests.patch(f"{self.base_url}{path}", headers=self.headers, json=json, timeout=30)
        if r.status_code not in ok:
            log.error("PATCH %s failed [%s]: %s", path, r.status_code, r.text)
            raise RuntimeError(r.text)
        return r.json()

    def search_available_numbers(
        self,
        area_code: Optional[str] = None,
        country_code: str = "US",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search available DIDs"""
        params = {"filter[country_code]": country_code, "limit": limit}
        if area_code:
            params["filter[national_destination_code]"] = area_code
        data = self._get("/available_phone_numbers", params=params)
        return data.get("data", [])

    def order_number(self, phone_number: str) -> Dict[str, Any]:
        """Purchase a specific DID"""
        payload = {"phone_numbers": [{"phone_number": phone_number}]}
        data = self._post("/number_orders", json=payload)
        log.info("Ordered number: %s", phone_number)
        return data

    def get_or_create_retell_trunk(
        self,
        connection_name: str,
        sip_username: str,
        sip_password: str,
    ) -> Tuple[Dict[str, Any], str, str]:
        """Get or create Elastic SIP Trunk for Retell"""
        try:
            existing = self._get("/fqdn_connections", params={"filter[connection_name]": connection_name})
            connections = existing.get("data", [])
            if connections:
                conn = connections[0]
                log.info(f"Using existing trunk: {conn.get('id')}")
                return conn, sip_username, sip_password
        except Exception as e:
            log.warning(f"Error checking trunks: {e}")
        
        log.info(f"Creating Elastic SIP Trunk: {connection_name}")
        
        payload = {
            "connection_name": connection_name,
            "transport_protocol": "TCP",
            "default_on_hold_comfort_noise_enabled": True,
            "dtmf_type": "RFC 2833",
            "inbound": {
                "ani_number_format": "+E.164",
                "dnis_number_format": "+E.164",
                "codecs": ["G722", "PCMU", "PCMA"],
                "sip_region": "US",
                "timeout_1xx_secs": 5,
                "timeout_2xx_secs": 90
            },
            "outbound": {
                "ani_override_type": "always",
                "localization": "US"
            }
        }
        
        trunk_response = self._post("/fqdn_connections", json=payload)
        trunk_data = trunk_response.get("data", {})
        trunk_id = trunk_data.get("id")
        log.info(f"Created trunk: {trunk_id}")
        
        fqdn_payload = {
            "connection_id": trunk_id,
            "fqdn": "sip.retellai.com",
            "dns_record_type": "srv",
            "port": 5060
        }
        
        try:
            self._post("/fqdns", json=fqdn_payload)
            log.info(f"Added FQDN sip.retellai.com")
        except Exception as e:
            log.warning(f"FQDN already exists: {e}")
        
        return trunk_data, sip_username, sip_password

    def list_phone_numbers(self, phone_number: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if phone_number:
            params["filter[phone_number]"] = phone_number
        data = self._get("/phone_numbers", params=params)
        return data.get("data", [])

    def assign_number_to_connection(self, phone_number: str, connection_id: str) -> Dict[str, Any]:
        """Assign number to trunk"""
        items = self.list_phone_numbers(phone_number=phone_number)
        if not items:
            raise RuntimeError(f"Number not found: {phone_number}")
        number_id = items[0]["id"]
        payload = {"connection_id": connection_id}
        patched = self._patch(f"/phone_numbers/{number_id}", json=payload)
        log.info(f"Assigned {phone_number} to {connection_id}")
        return patched

    @staticmethod
    def make_call(to_number: str, from_number: str, connection_id: str | None = None, webhook_url: str | None = None) -> Optional[Dict[str, Any]]:
        try:
            params = {"to": to_number, "from_": from_number}
            if connection_id:
                params["connection_id"] = connection_id
            if webhook_url:
                params["webhook_url"] = webhook_url
            call = client.calls.dial(**params)
            return {"call_control_id": call.data.call_control_id}
        except Exception as e:
            log.error("Call error: %s", e)
            return None

    @staticmethod
    def send_sms(to_number: str, from_number: str, text: str, webhook_url: str | None = None) -> Optional[Dict]:
        try:
            params = {"to": to_number, "from_": from_number, "text": text}
            if webhook_url:
                params["webhook_url"] = webhook_url
            message = client.messages.create(**params)
            return {"id": message.data.id}
        except Exception as e:
            log.error("SMS error: %s", e)
            return None
