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


class TelnyxNoResults(RuntimeError):
    """Telnyx answers 400 / code 10031 when a number search matches nothing; that is an empty result."""


NO_RESULTS_CODE = "10031"


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
        if r.status_code == 400 and f'"{NO_RESULTS_CODE}"' in r.text:
            log.info("GET %s matched nothing", path)
            raise TelnyxNoResults(r.text)
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

    def ensure_outbound_voice_profile(
        self,
        connection_id: str,
        profile_name: str = "RootCall US Outbound",
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ensure a dedicated US outbound voice profile exists and is attached
        to this RootCall FQDN SIP connection. Safe to call repeatedly.
        """
        if not connection_id:
            raise ValueError("A Telnyx FQDN connection ID is required")

        connection_response = self._get(f"/fqdn_connections/{connection_id}")
        connection = connection_response.get("data", connection_response)
        outbound = connection.get("outbound") or {}
        attached_profile_id = outbound.get("outbound_voice_profile_id")

        configured_profile_id = os.getenv("TELNYX_OUTBOUND_VOICE_PROFILE_ID", "").strip()
        profile_id = profile_id or configured_profile_id or attached_profile_id

        profile = None
        if profile_id:
            profile_response = self._get(f"/outbound_voice_profiles/{profile_id}")
            profile = profile_response.get("data", profile_response)
        else:
            profiles_response = self._get(
                "/outbound_voice_profiles",
                params={"page[size]": 100},
            )
            profiles = profiles_response.get("data", [])
            profile = next(
                (item for item in profiles if item.get("name") == profile_name),
                None,
            )

        if not profile:
            created = self._post(
                "/outbound_voice_profiles",
                json={
                    "name": profile_name,
                    "traffic_type": "conversational",
                    "enabled": True,
                    "whitelisted_destinations": ["US"],
                },
            )
            profile = created.get("data", created)

        profile_id = profile.get("id")
        if not profile_id:
            raise RuntimeError("Telnyx did not return an outbound voice profile ID")

        # Keep existing allowed destinations and ensure US is permitted.
        destinations = list(profile.get("whitelisted_destinations") or [])
        profile_updates: Dict[str, Any] = {
            "name": profile.get("name") or profile_name,
        }
        if "US" not in destinations:
            destinations.append("US")
            profile_updates["whitelisted_destinations"] = destinations
        if profile.get("enabled") is False:
            profile_updates["enabled"] = True
        if len(profile_updates) > 1:
            self._patch(
                f"/outbound_voice_profiles/{profile_id}",
                json=profile_updates,
            )

        if attached_profile_id != profile_id:
            updated = self._patch(
                f"/fqdn_connections/{connection_id}",
                json={
                    "outbound": {
                        "outbound_voice_profile_id": profile_id,
                    }
                },
            )
            updated_connection = updated.get("data", updated)
            updated_profile_id = (
                (updated_connection.get("outbound") or {}).get("outbound_voice_profile_id")
            )
            if updated_profile_id and updated_profile_id != profile_id:
                raise RuntimeError("Telnyx did not attach the requested outbound voice profile")

            # Verify with a fresh read instead of assuming a successful PATCH.
            verified_response = self._get(f"/fqdn_connections/{connection_id}")
            verified = verified_response.get("data", verified_response)
            verified_profile_id = (
                (verified.get("outbound") or {}).get("outbound_voice_profile_id")
            )
            if verified_profile_id != profile_id:
                raise RuntimeError("Telnyx outbound voice profile assignment could not be verified")
            connection = verified

        log.info(
            "Telnyx outbound profile ready: connection=%s profile=%s",
            connection_id,
            profile_id,
        )
        return {
            "connection": connection,
            "outbound_voice_profile_id": profile_id,
        }

    def search_available_numbers(
        self,
        area_code: Optional[str] = None,
        country_code: str = "US",
        limit: int = 10,
        best_effort: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search available DIDs. Returns [] when nothing matches; best_effort also offers nearby numbers."""
        params = {"filter[country_code]": country_code, "limit": limit}
        if area_code:
            params["filter[national_destination_code]"] = area_code
        if best_effort:
            params["filter[best_effort]"] = "true"
        try:
            data = self._get("/available_phone_numbers", params=params)
        except TelnyxNoResults:
            return []
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
        outbound_voice_profile_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str, str]:
        """Get or create Elastic SIP Trunk for Retell"""
        existing = self._get("/fqdn_connections", params={"filter[connection_name]": connection_name})
        connections = [item for item in existing.get("data", [])
                       if item.get("connection_name") == connection_name]
        if connections:
            conn = connections[0]
            # Never rewrite auth, credentials, or the voice profile on an existing trunk.
            # Retell holds the credentials it was imported with, and changing the trunk
            # breaks Retell -> Telnyx legs (transfers, outbound calls).
            log.info(f"Using existing trunk unchanged: {conn.get('id')}")
            return conn, sip_username, sip_password

        log.info(f"Creating Elastic SIP Trunk: {connection_name}")
        
        payload = {
            "connection_name": connection_name,
            "transport_protocol": "TCP",
            "default_on_hold_comfort_noise_enabled": True,
            "dtmf_type": "RFC 2833",
            "inbound": {
                "ani_number_format": "+E.164",
                "dnis_number_format": "+e164",
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
        if outbound_voice_profile_id:
            payload["outbound"]["outbound_voice_profile_id"] = outbound_voice_profile_id
            payload["outbound"]["ip_authentication_method"] = "credential-authentication"
            payload["user_name"] = sip_username
            payload["password"] = sip_password
        
        trunk_response = self._post("/fqdn_connections", json=payload)
        trunk_data = trunk_response.get("data", {})
        trunk_id = trunk_data.get("id")
        log.info(f"Created trunk: {trunk_id}")
        self.ensure_outbound_voice_profile(trunk_id, profile_id=outbound_voice_profile_id)
        
        self._ensure_retell_fqdn(trunk_id)
        return trunk_data, sip_username, sip_password

    def _ensure_retell_fqdn(self, connection_id: str):
        existing = self._get("/fqdns", params={"filter[connection_id]": connection_id})
        if any(item.get("fqdn") == "sip.retellai.com"
               and str(item.get("connection_id")) == str(connection_id)
               for item in existing.get("data", [])):
            return
        fqdn_payload = {
            "connection_id": connection_id,
            "fqdn": "sip.retellai.com",
            "dns_record_type": "srv",
            "port": 5060
        }
        
        self._post("/fqdns", json=fqdn_payload)
        log.info(f"Added FQDN sip.retellai.com")
        
    def list_phone_numbers(self, phone_number: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if phone_number:
            params["filter[phone_number]"] = phone_number
        data = self._get("/phone_numbers", params=params)
        return data.get("data", [])

    def assign_number_to_connection(self, phone_number: str, connection_id: str) -> Dict[str, Any]:
        """Assign number to trunk"""
        items = [item for item in self.list_phone_numbers(phone_number=phone_number)
                 if item.get("phone_number") == phone_number]
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
