"""Retell.ai Integration Service - Automated Setup (Agent + Inbound/Outbound)"""
import logging
import os
import re
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

    def list_voices(self) -> List[Dict[str, Any]]:
        return self._get("/list-voices")

    def list_phone_numbers(self) -> List[Dict[str, Any]]:
        return self._get("/list-phone-numbers")

    def configure_call_webhook(self, agent_id: str, webhook_url: str):
        return self._patch(f"/update-agent/{agent_id}", {"webhook_url": webhook_url}, expected=200)

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
            self.publish_agent(agent_id, version=data.get("version"))
        return agent_id

    def publish_agent(self, agent_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        log.info("Publishing Retell Agent: %s", agent_id)
        if version is None:
            agent = self._get(f"/get-agent/{agent_id}")
            version = agent.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise RuntimeError("No valid agent version returned by Retell")
        return self._post(
            f"/publish-agent-version/{agent_id}",
            {"version": version},
            expected=(200, 201, 204),
        )

    def list_agents(self) -> List[Dict[str, Any]]:
        data = self._get("/list-agents", expected=200)
        if isinstance(data, list):
            return data
        return data.get("agents", [])

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

    def configure_transfer_tool(
        self, agent_id: str, transfer_number: Optional[str] = None,
        custom_sip_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Configure agent with transfer_call tool for forwarding legitimate calls"""
        if transfer_number and not re.fullmatch(r"\+[1-9]\d{1,14}", transfer_number):
            raise ValueError("Forwarding number must be in E.164 format")
        agent = self._get(f"/get-agent/{agent_id}")
        engine = agent.get("response_engine") or {}
        if engine.get("type") != "retell-llm" or not engine.get("llm_id"):
            raise RuntimeError("Transfer configuration requires a Retell LLM agent")
        llm_id = engine["llm_id"]
        llm = self._get(f"/get-retell-llm/{llm_id}")
        previous_transfer = next(
            (tool for tool in (llm.get("general_tools") or []) if tool.get("name") == "transfer_call"), {}
        )
        general_tools = [
            tool for tool in (llm.get("general_tools") or [])
            if tool.get("name") != "transfer_call"
        ]
        if not any(tool.get("type") == "end_call" for tool in general_tools):
            general_tools.append({
                "type": "end_call",
                "name": "end_call",
                "description": "End call for spam/scam callers"
            })
        if transfer_number:
            transfer_tool = {
                "type": "transfer_call",
                "name": "transfer_call",
                "description": "Transfer legitimate calls to the client's phone",
                "transfer_destination": {"type": "predefined", "number": transfer_number},
                "transfer_option": {"type": "cold_transfer"},
            }
            headers = custom_sip_headers if custom_sip_headers is not None else previous_transfer.get("custom_sip_headers")
            if headers:
                transfer_tool["custom_sip_headers"] = headers
            general_tools.append(transfer_tool)
            log.info(f"✅ Configured transfer to {transfer_number} for agent {agent_id}")
        else:
            log.info(f"⚠️  Removed transfer tool from agent {agent_id}")
        result = self._patch(
            f"/update-retell-llm/{llm_id}", {"general_tools": general_tools}, expected=200
        )
        self.publish_agent(agent_id)
        return result

    # ---------- Phone numbers / inbound & outbound binding ----------

    def create_trusted_transfer_flow(self, sip_username: Optional[str] = None) -> str:
        payload = {
            "start_speaker": "agent",
            "model_choice": {"type": "cascading", "model": "gpt-4.1"},
            "flex_mode": False,
            "start_node_id": "trusted_transfer",
            "nodes": [
                {
                    "id": "trusted_transfer", "type": "transfer_call",
                    "transfer_destination": {"type": "predefined", "number": "{{rootcall_forwarding}}"},
                    "transfer_option": {"type": "cold_transfer"},
                    "speak_during_execution": False,
                    "edge": {
                        "id": "transfer_failed", "destination_node_id": "transfer_failed_end",
                        "transition_condition": {"type": "prompt", "prompt": "Transfer failed"},
                    },
                },
                {
                    "id": "transfer_failed_end", "type": "end",
                    "speak_during_execution": True,
                    "instruction": {"type": "static_text", "text": "Sorry, we could not connect your call. Please try again later."},
                },
            ],
        }
        if sip_username:
            payload["nodes"][0]["custom_sip_headers"] = {"X-Telnyx-Username": sip_username}
        data = self._post("/create-conversation-flow", payload, expected=(200, 201))
        if not data.get("conversation_flow_id"):
            raise RuntimeError("Retell did not return a trusted transfer flow ID")
        return data["conversation_flow_id"]

    def create_trusted_transfer_agent(self, name: str, flow_id: str, source_agent_id: str, webhook_url: str) -> str:
        source = self._get(f"/get-agent/{source_agent_id}")
        if not source.get("voice_id"):
            raise RuntimeError("Screening agent has no configured voice")
        data = self._post("/create-agent", {
            "agent_name": name,
            "response_engine": {"type": "conversation-flow", "conversation_flow_id": flow_id},
            "voice_id": source["voice_id"],
            "language": source.get("language", "en-US"),
            "enable_backchannel": False,
            "webhook_url": webhook_url,
        }, expected=(201,))
        if not data.get("agent_id"):
            raise RuntimeError("Retell did not return a trusted transfer agent ID")
        return data["agent_id"]

    def configure_inbound_webhook(self, phone_number: str, webhook_url: str):
        return self._patch(
            f"/update-phone-number/{phone_number}", {"inbound_webhook_url": webhook_url}, expected=200,
        )

    def get_phone_number(self, phone_number: str):
        return self._get(f"/get-phone-number/{phone_number}")

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
        }
        if inbound_agent_id is not None:
            payload["inbound_agents"] = [{"agent_id": inbound_agent_id, "weight": 1.0}]
        if outbound_agent_id is not None:
            payload["outbound_agents"] = [{"agent_id": outbound_agent_id, "weight": 1.0}]
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
            patch["inbound_agents"] = [{"agent_id": inbound_agent_id, "weight": 1.0}]
        if outbound_agent_id is not None:
            patch["outbound_agents"] = [{"agent_id": outbound_agent_id, "weight": 1.0}]
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
retell_service = None

def get_retell_service():
    global retell_service
    if retell_service is None:
        retell_service = RetellService()
    return retell_service
