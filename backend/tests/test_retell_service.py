import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch


def load_service():
    config = ModuleType("app.config")
    config.settings = SimpleNamespace(RETELL_API_KEY="unused-test-key")
    requests = ModuleType("requests")
    service_path = Path(__file__).resolve().parents[1] / "app/services/retell_service.py"
    spec = importlib.util.spec_from_file_location("retell_service_under_test", service_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.config": config, "requests": requests}):
        spec.loader.exec_module(module)
    return module


class RetellPublishingTest(unittest.TestCase):
    def setUp(self):
        self.module = load_service()
        self.service = self.module.RetellService(api_key="unused-test-key")

    def test_creation_publishes_returned_version(self):
        with patch.object(self.service, "_post", return_value={"agent_id": "agent-test", "version": 0}), patch.object(self.service, "publish_agent") as publish:
            agent_id = self.service.create_agent("Test", "llm-test")
        self.assertEqual(agent_id, "agent-test")
        publish.assert_called_once_with("agent-test", version=0)

    def test_publish_uses_version_endpoint_and_payload(self):
        with patch.object(self.service, "_post", return_value={}) as post:
            self.service.publish_agent("agent-test", version=2)
        post.assert_called_once_with(
            "/publish-agent-version/agent-test", {"version": 2}, expected=(200, 201, 204)
        )

    def test_existing_callers_fetch_current_version(self):
        with patch.object(self.service, "_get", return_value={"version": 3}) as get, patch.object(self.service, "_post", return_value={}) as post:
            self.service.publish_agent("agent-test")
        get.assert_called_once_with("/get-agent/agent-test")
        self.assertEqual(post.call_args.args[1], {"version": 3})

    def test_missing_version_does_not_send_publish_request(self):
        with patch.object(self.service, "_get", return_value={}), patch.object(self.service, "_post") as post:
            with self.assertRaisesRegex(RuntimeError, "No valid agent version"):
                self.service.publish_agent("agent-test")
        post.assert_not_called()

    def test_publish_accepts_empty_success_responses(self):
        for status_code in (200, 201, 204):
            with self.subTest(status_code=status_code):
                response = Mock(status_code=status_code, text="")
                with patch.object(self.module.requests, "post", return_value=response, create=True):
                    result = self.service.publish_agent("agent-test", version=0)
                self.assertEqual(result, {})

    def test_import_uses_weighted_agent_bindings(self):
        with patch.object(self.service, "_post", return_value={}) as post:
            self.service.import_phone_number(
                "+14075550100", "sip.telnyx.com", "sip-user", "sip-password",
                inbound_agent_id="agent-in", outbound_agent_id="agent-out",
            )
        post.assert_called_once_with("/import-phone-number", {
            "phone_number": "+14075550100",
            "termination_uri": "sip.telnyx.com",
            "sip_trunk_auth_username": "sip-user",
            "sip_trunk_auth_password": "sip-password",
            "inbound_agents": [{"agent_id": "agent-in", "weight": 1.0}],
            "outbound_agents": [{"agent_id": "agent-out", "weight": 1.0}],
        }, expected=(200, 201))

    def test_update_uses_weighted_agent_bindings(self):
        with patch.object(self.service, "_patch", return_value={}) as patch_request:
            self.service.update_phone_number(
                "+14075550100", inbound_agent_id="agent-in", outbound_agent_id="agent-out"
            )
        patch_request.assert_called_once_with("/update-phone-number/+14075550100", {
            "inbound_agents": [{"agent_id": "agent-in", "weight": 1.0}],
            "outbound_agents": [{"agent_id": "agent-out", "weight": 1.0}],
        }, expected=200)

    def test_service_authenticates_with_configured_key(self):
        self.assertEqual(self.service.headers["Authorization"], "Bearer unused-test-key")

    def test_transfer_updates_llm_preserves_tools_and_publishes(self):
        existing_tools = [{"type": "custom", "name": "lookup_contact"}]
        agent = {"response_engine": {"type": "retell-llm", "llm_id": "llm-test"}}
        with patch.object(self.service, "_get", side_effect=[agent, {"general_tools": existing_tools}]), \
                patch.object(self.service, "_patch", return_value={}) as update, \
                patch.object(self.service, "publish_agent") as publish:
            self.service.configure_transfer_tool("agent-test", "+12025550102")
        update.assert_called_once_with("/update-retell-llm/llm-test", {
            "general_tools": existing_tools + [
                {"type": "end_call", "name": "end_call", "description": "End call for spam/scam callers"},
                {
                    "type": "transfer_call", "name": "transfer_call",
                    "description": "Transfer legitimate calls to the client's phone",
                    "transfer_destination": {"type": "predefined", "number": "+12025550102"},
                    "transfer_option": {"type": "cold_transfer"},
                },
            ],
        }, expected=200)
        publish.assert_called_once_with("agent-test")

    def test_removing_transfer_preserves_other_tools(self):
        tools = [
            {"type": "end_call", "name": "end_call"},
            {"type": "transfer_call", "name": "transfer_call"},
            {"type": "custom", "name": "lookup_contact"},
        ]
        agent = {"response_engine": {"type": "retell-llm", "llm_id": "llm-test"}}
        with patch.object(self.service, "_get", side_effect=[agent, {"general_tools": tools}]), \
                patch.object(self.service, "_patch", return_value={}) as update, \
                patch.object(self.service, "publish_agent"):
            self.service.configure_transfer_tool("agent-test", None)
        self.assertEqual(update.call_args.args[1]["general_tools"], [tools[0], tools[2]])

    def test_invalid_forwarding_number_does_not_contact_provider(self):
        with patch.object(self.service, "_get") as get:
            with self.assertRaises(ValueError):
                self.service.configure_transfer_tool("agent-test", "invalid")
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()