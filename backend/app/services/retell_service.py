"""Retell.ai Integration Service - Automated Setup (Agent + Inbound/Outbound)"""
import logging
import os
import requests
from typing import Any, Dict, List, Optional

from app.config import settings

log = logging.getLogger(__name__)


class RetellService:
    """Retell.ai conversational AI service (sync/requests version)"""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.retellai.com"):
        self.api_key = api_key or settings.RETELL_API_KEY
        self.base_url = base_url
        if not self.api_key:
            raise RuntimeError("Missing RETELL_API_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ---------- Low-level helpers ----------

    def _post(self, path: str, json: Dict[str, Any], expected: int | tuple = (200, 201)) -> Dict[str, Any]:
        r = requests.post(f"{self.base_url}{path}", json=json, headers=self.headers, timeout=30)
        if isinstance(expected, int):
            expected = (expected,)
        if r.status_code not in expected:
            log.error("POST %s failed [%s]: %s", path, r.status_code, r.text)
            raise RuntimeError(r.text)
        return r.json() if r.text else {}

    def _patch(self, path: str, json: Dict[str, Any], expected: int | tuple = (200,)) -> Dict[str, Any]:
        r = requests.patch(f"{self.base_url}{path}", json=json, headers=self.headers, timeout=30)
        if isinstance(expected, int):
            expected = (expected,)
        if r.status_code not in expected:
            log.error("PATCH %s failed [%s]: %s", path, r.status_code, r.text)
            raise RuntimeError(r.text)
        return r.json() if r.text else {}

    def _get(self, path: str, expected: int | tuple = (200,)) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}{path}", headers=self.headers, timeout=30)
        if isinstance(expected, int):
            expected = (expected,)
        if r.status_code not in expected:
            log.error("GET %s failed [%s]: %s", path, r.status_code, r.text)
            raise RuntimeError(r.text)
        return r.json() if r.text else {}

    # ---------- LLM ----------

    def create_llm(
        self,
        general_prompt: str,
        begin_message: str = "Hi! How can I help you today?",
        start_speaker: str = "agent",
        model: str = "gpt-4.1",
        kb_top_k: int = 3,
        kb_filter_score: float = 0.6,
    ) -> str:
        """Create a Retell LLM and return llm_id."""
        payload = {
            "model": model,
            "general_prompt": general_prompt,
            "start_speaker": start_speaker,
            "begin_message": begin_message,
            "kb_config": {"top_k": kb_top_k, "filter_score": kb_filter_score},
        }
        log.info("Creating Retell LLM")
        data = self._post("/create-retell-llm", payload, expected=(201,))
        llm_id = data.get("llm_id")
        if not llm_id:
            raise RuntimeError("No llm_id returned")
        log.info("✅ Created LLM: %s", llm_id)
        return llm_id

    def update_llm(
        self,
        llm_id: str,
        general_prompt: Optional[str] = None,
        begin_message: Optional[str] = None,
        start_speaker: Optional[str] = None,
    ) -> Dict[str, Any]:
        patch: Dict[str, Any] = {}
        if general_prompt is not None:
            patch["general_prompt"] = general_prompt
        if begin_message is not None:
            patch["begin_message"] = begin_message
        if start_speaker is not None:
            patch["start_speaker"] = start_speaker
        return self._patch(f"/update-retell-llm/{llm_id}", patch, expected=200)

    # ---------- Agent ----------

    def create_agent(
        self,
        name: str,
        llm_id: str,
        voice_id: str = "11labs-Adrian",
        language: str = "en-US",
        enable_backchannel: bool = True,
        backchannel_frequency: float = 0.8,
        responsiveness: float = 1.0,
        interruption_sensitivity: float = 1.0,
        publish: bool = True,
    ) -> str:
        """Create a Retell Agent backed by the given LLM, and optionally publish it."""
        payload = {
            "response_engine": {"type": "retell-llm", "llm_id": llm_id},
            "voice_id": voice_id,
            "agent_name": name,
            "language": language,
            "enable_backchannel": enable_backchannel,
            "backchannel_frequency": backchannel_frequency,
            "responsiveness": responsiveness,
            "interruption_sensitivity": interruption_sensitivity,
        }
        log.info("Creating Retell Agent: %s", name)
        data = self._post("/create-agent", payload, expected=(201,))
        agent_id = data.get("agent_id")
        if not agent_id:
            raise RuntimeError("No agent_id returned")
        log.info("✅ Created Agent: %s", agent_id)

        if publish:
            self.publish_agent(agent_id)
        return agent_id

    def publish_agent(self, agent_id: str) -> Dict[str, Any]:
        log.info("Publishing Retell Agent: %s", agent_id)
        return self._post(f"/publish-agent/{agent_id}", {}, expected=200)

    def list_agents(self) -> List[Dict[str, Any]]:
        data = self._get("/list-agents", expected=200)

    def update_agent(
        self,
        agent_id: str,
        general_tools: Optional[List[Dict[str, Any]]] = None,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update agent configuration including tools"""
        patch: Dict[str, Any] = {}
        if general_tools is not None:
            patch["general_tools"] = general_tools
        if agent_name is not None:
            patch["agent_name"] = agent_name
        log.info(f"Updating Retell Agent: {agent_id}")
        return self._patch(f"/update-agent/{agent_id}", patch, expected=200)

    def configure_transfer_tool(self, agent_id: str, transfer_number: Optional[str] = None) -> Dict[str, Any]:
        """Configure agent with transfer_call tool for forwarding legitimate calls"""
        general_tools = [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End call for spam/scam callers"
            }
        ]
        if transfer_number:
            general_tools.append({
                "type": "transfer_call",
                "name": "transfer_call",
                "description": "Transfer legitimate calls to the client's phone",
                "number": transfer_number
            })
            log.info(f"✅ Configured transfer to {transfer_number} for agent {agent_id}")
        else:
            log.info(f"⚠️  Removed transfer tool from agent {agent_id}")
        return self.update_agent(agent_id, general_tools=general_tools)
        # Sometimes API returns a list already
        if isinstance(data, list):
            return data
        return data.get("agents", [])

    # ---------- Phone numbers / inbound & outbound binding ----------

    def import_phone_number(
        self,
        phone_number: str,      # E.164 (+1813...)
        termination_uri: str,   # e.g., "sip.telnyx.com"
        sip_username: str,
        sip_password: str,
        inbound_agent_id: Optional[str] = None,
        outbound_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import (bind) your Telnyx number into Retell so Retell can receive inbound calls
        and originate outbound via your trunk. Also binds agents for inbound/outbound.
        """
        payload = {
            "phone_number": phone_number,
            "termination_uri": termination_uri,
            "sip_trunk_auth_username": sip_username,
            "sip_trunk_auth_password": sip_password,
            "inbound_agent_id": inbound_agent_id,
            "outbound_agent_id": outbound_agent_id,
        }
        log.info("Importing phone number to Retell: %s", phone_number)
        return self._post("/import-phone-number", payload, expected=(200, 201))

    def update_phone_number(
        self,
        phone_number: str,
        inbound_agent_id: Optional[str] = None,
        outbound_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        patch: Dict[str, Any] = {}
        if inbound_agent_id is not None:
            patch["inbound_agent_id"] = inbound_agent_id
        if outbound_agent_id is not None:
            patch["outbound_agent_id"] = outbound_agent_id
        log.info("Updating Retell phone number bindings: %s", phone_number)
        return self._patch(f"/update-phone-number/{phone_number}", patch, expected=200)

    # ---------- Calls (outbound) ----------

    def create_phone_call(self, from_number: str, to_number: str, override_agent_id: str) -> Dict[str, Any]:
        payload = {
            "from_number": from_number,
            "to_number": to_number,
            "override_agent_id": override_agent_id,
        }
        log.info("Placing call %s -> %s (agent=%s)", from_number, to_number, override_agent_id)
        return self._post("/v2/create-phone-call", payload, expected=(200, 201))

    def bulk_create_phone_calls(self, from_number: str, to_numbers: List[str], override_agent_id: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for num in to_numbers:
            try:
                res = self.create_phone_call(from_number, num, override_agent_id)
                results.append({"to": num, "status": "ok", "data": res})
            except Exception as e:
                results.append({"to": num, "status": "error", "error": str(e)})
        return results

    # ---------- High-level: one-shot setup ----------

    def setup_voice_ai_with_number(
        self,
        business_name: str,
        system_prompt: str,
        voice_id: str = "11labs-Adrian",
        begin_message: str = "Hi! How can I help you today?",
        publish_agent: bool = True,
        # Number import/binding
        telnyx_number: Optional[str] = None,    # required to bind
        telnyx_termination_uri: str = "sip.telnyx.com",
        telnyx_sip_username: Optional[str] = None,
        telnyx_sip_password: Optional[str] = None,
        # Outbound bulk
        leads: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Creates LLM + Agent (+ publishes), imports & binds Telnyx number in Retell,
        and optionally kicks off bulk outbound calls.
        """
        # 1) LLM
        llm_id = self.create_llm(general_prompt=system_prompt, begin_message=begin_message)

        # 2) Agent
        agent_name = f"{business_name} AI"
        agent_id = self.create_agent(
            name=agent_name,
            llm_id=llm_id,
            voice_id=voice_id,
            publish=publish_agent,
        )

        result: Dict[str, Any] = {"llm_id": llm_id, "agent_id": agent_id}

        # 3) Import/bind number for inbound/outbound (if provided)
        if telnyx_number:
            if not (telnyx_sip_username and telnyx_sip_password):
                raise RuntimeError("Need telnyx_sip_username and telnyx_sip_password to import/bind number")
            imported = self.import_phone_number(
                phone_number=telnyx_number,
                termination_uri=telnyx_termination_uri,
                sip_username=telnyx_sip_username,
                sip_password=telnyx_sip_password,
                inbound_agent_id=agent_id,
                outbound_agent_id=agent_id,
            )
            result["retell_number_import"] = imported

        # 4) Bulk outbound (optional)
        if leads and telnyx_number:
            bulk = self.bulk_create_phone_calls(
                from_number=telnyx_number,
                to_numbers=leads,
                override_agent_id=agent_id,
            )
            result["bulk"] = bulk

        return result

# Global singleton for legacy imports
retell_service = RetellService()
