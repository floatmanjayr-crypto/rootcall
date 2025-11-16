# app/services/telnyx_service.py
from __future__ import annotations
import os
import logging
from typing import List, Dict, Any, Optional, Tuple

import requests
from telnyx import Telnyx  # pip install telnyx
from app.config import settings

log = logging.getLogger(__name__)

TLX_API_KEY = settings.TELNYX_API_KEY
TLX_BASE = os.getenv("TELNYX_BASE", "https://api.telnyx.com/v2")

client = Telnyx(api_key=TLX_API_KEY)


class TelnyxService:
    """Telnyx provisioning + calls"""

    def __init__(self, api_key: Optional[str] = None, base_url: str = TLX_BASE):
        self.api_key = api_key or TLX_API_KEY
        if not self.api_key:
            raise RuntimeError("Missing TELNYX_API_KEY")
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------ Helper: HTTP wrappers ------------------

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

    # ------------------ Numbers: search + order ------------------

    def search_available_numbers(
        self,
        area_code: Optional[str] = None,
        country_code: str = "US",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search available DIDs. Returns a list of items (each includes 'phone_number' and metadata).
        """
        params = {"filter[country_code]": country_code, "limit": limit}
        if area_code:
            params["filter[national_destination_code]"] = area_code  # NPA/area code
        data = self._get("/available_phone_numbers", params=params)
        return data.get("data", [])

    def order_number(self, phone_number: str) -> Dict[str, Any]:
        """
        Purchase a specific DID (E.164).
        """
        payload = {"phone_numbers": [{"phone_number": phone_number}]}
        data = self._post("/phone_number_orders", json=payload)
        log.info("📞 Ordered Telnyx number: %s", phone_number)
        return data

    # ------------------ SIP Credential Connection ------------------

    def list_credential_connections(self, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if name_filter:
            params["filter[connection_name]"] = name_filter
        data = self._get("/credential_connections", params=params)
        return data.get("data", [])

    def get_or_create_credential_connection(
        self,
        connection_name: str,
        sip_username: Optional[str] = None,
        sip_password: Optional[str] = None,
        webhook_url: Optional[str] = None,
        sip_region: Optional[str] = None,  # e.g., "oregon" (optional)
    ) -> Tuple[Dict[str, Any], str, str]:
        """
        Returns (connection, username, password).
        If exists and credentials provided are None, we attempt to read existing username (password is not retrievable).
        If not found, create with provided username/password. If you don't pass username/password, we auto-generate.
        """
        existing = self.list_credential_connections(name_filter=connection_name)
        if existing:
            conn = existing[0]
            # Existing creds: username is available; password cannot be read back.
            username = conn.get("sip_username") or sip_username or ""
            password = sip_password or ""  # you must store your own; API won't return it
            log.info("Using existing Telnyx credential connection '%s' (id=%s)", connection_name, conn.get("id"))
            return conn, username, password

        # Create new credential connection
        payload: Dict[str, Any] = {"connection_name": connection_name}
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if sip_username:
            payload["sip_username"] = sip_username
        if sip_password:
            payload["sip_password"] = sip_password
        if sip_region:
            payload["sip_region"] = sip_region

        conn = self._post("/credential_connections", json=payload).get("data") or {}
        username = conn.get("sip_username") or (sip_username or "")
        # Note: API does not return password on create for security; store what you sent.
        password = sip_password or ""
        log.info("✅ Created Telnyx credential connection '%s' (id=%s)", connection_name, conn.get("id"))
        return conn, username, password

    # ------------------ Assign numbers to connection (inbound routing) ------------------

    def list_phone_numbers(self, phone_number: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if phone_number:
            params["filter[phone_number]"] = phone_number
        data = self._get("/phone_numbers", params=params)
        return data.get("data", [])

    def assign_number_to_connection(self, phone_number: str, connection_id: str) -> Dict[str, Any]:
        """
        Attach a purchased phone number to a credential connection so inbound
        calls route to your trunk.
        """
        items = self.list_phone_numbers(phone_number=phone_number)
        if not items:
            raise RuntimeError(f"Phone number not found in your account: {phone_number}")
        number_id = items[0]["id"]
        payload = {"connection_id": connection_id}
        patched = self._patch(f"/phone_numbers/{number_id}", json=payload)
        log.info("🔗 Assigned %s to connection %s", phone_number, connection_id)
        return patched

    # ------------------ Call Control (outbound) ------------------

    @staticmethod
    def make_call(
        to_number: str,
        from_number: str,
        connection_id: str | None = None,
        webhook_url: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Initiate an outbound call via Call Control (Telnyx SDK)."""
        try:
            params = {"to": to_number, "from_": from_number}
            if connection_id:
                params["connection_id"] = connection_id
            if webhook_url:
                params["webhook_url"] = webhook_url
            call = client.calls.dial(**params)
            return {
                "call_control_id": call.data.call_control_id,
                "call_session_id": getattr(call.data, "call_session_id", None),
            }
        except Exception as e:
            log.error("Error making call: %s", e)
            return None

    @staticmethod
    def answer_call(call_control_id: str) -> bool:
        try:
            client.calls.actions(call_control_id).answer()
            return True
        except Exception as e:
            log.error("Error answering call: %s", e)
            return False

    @staticmethod
    def hangup_call(call_control_id: str) -> bool:
        try:
            client.calls.actions(call_control_id).hangup()
            return True
        except Exception as e:
            log.error("Error hanging up call: %s", e)
            return False

    @staticmethod
    def speak_text(call_control_id: str, text: str, voice: str = "female", language: str = "en-US") -> bool:
        try:
            client.calls.actions(call_control_id).speak(payload=text, voice=voice, language=language)
            return True
        except Exception as e:
            log.error("Error speaking text: %s", e)
            return False

    @staticmethod
    def start_recording(call_control_id: str, format: str = "mp3", channels: str = "single") -> bool:
        try:
            client.calls.actions(call_control_id).record_start(format=format, channels=channels)
            return True
        except Exception as e:
            log.error("Error starting recording: %s", e)
            return False

    @staticmethod
    def stop_recording(call_control_id: str) -> bool:
        try:
            client.calls.actions(call_control_id).record_stop()
            return True
        except Exception as e:
            log.error("Error stopping recording: %s", e)
            return False

    @staticmethod
    def send_sms(to_number: str, from_number: str, text: str, webhook_url: str | None = None) -> Optional[Dict]:
        try:
            params = {"to": to_number, "from_": from_number, "text": text}
            if webhook_url:
                params["webhook_url"] = webhook_url
            message = client.messages.create(**params)
            return {"id": message.data.id}
        except Exception as e:
            log.error("Error sending SMS: %s", e)
            return None

    # ------------------ High-level: Provision for Retell inbound ------------------

    def provision_number_with_credentials(
        self,
        desired_area_code: Optional[str],
        connection_name: str,
        sip_username: Optional[str] = None,
        sip_password: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        1) Search + order a number
        2) Create (or reuse) a Credential Connection
        3) Assign the number to that connection
        Returns the number, connection, and SIP creds you’ll pass to Retell.import_phone_number(...)
        """
        # 1) Search + order
        results = self.search_available_numbers(area_code=desired_area_code, limit=1)
        if not results:
            raise RuntimeError("No numbers available for requested area code")
        phone_number = results[0]["phone_number"]
        self.order_number(phone_number)

        # 2) Connection (get or create)
        conn, username, password = self.get_or_create_credential_connection(
            connection_name=connection_name,
            sip_username=sip_username,
            sip_password=sip_password,
            webhook_url=webhook_url,
        )

        # 3) Assign number → connection
        self.assign_number_to_connection(phone_number, conn["id"])

        return {
            "phone_number": phone_number,
            "connection": conn,
            "sip_username": username,
            "sip_password": password,  # if you created a new one this will be what you passed
        }

# ====== OVP + Provisioning Helpers (safe append) ======
import requests
from typing import List, Optional, Dict, Any

