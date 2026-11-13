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


    def test_screening_prompt_binds_owner_privately_and_rejects_other_names(self):
        prompt = self.module.build_scam_screening_prompt("Jordan Example")
        self.assertIn("Jordan Example", prompt)
        self.assertIn("Never reveal or suggest the stored owner name", prompt)
        self.assertIn("A name match is not authentication", prompt)
        self.assertIn("recipient-routing rule", prompt)
        self.assertIn("do not transfer", prompt.lower())
        self.assertIn("bank, credit union, card issuer", prompt)


    def test_prompt_accepts_first_or_last_name_as_recipient_variants(self):
        prompt = self.module.build_scam_screening_prompt("Jordan Example")
        self.assertIn("first name alone", prompt)
        self.assertIn("last name alone", prompt)
        self.assertIn("ignoring capitalization", prompt)
        self.assertIn("Your FIRST spoken message must be:", prompt)
        self.assertIn("before asking what the call is about", prompt)
        self.assertIn('If the protected owner is "Jordan Example" and the caller says "Michael"', prompt)
        self.assertIn("do not say \"what would you like to speak to michael about?\"", prompt.lower())

    def test_screening_prompt_fails_closed_without_owner_identity(self):
        prompt = self.module.build_scam_screening_prompt(None)
        self.assertIn("OWNER IDENTITY IS NOT CONFIGURED", prompt)
        self.assertIn("do not transfer any caller", prompt)

    def test_screening_prompt_preserves_existing_handbook_without_nesting_on_resync(self):
        handbook = "ROOT CALL — ADVANCED SCAM SHIELD\\nOriginal greeting and screening rules."
        first_sync = self.module.build_scam_screening_prompt("Jordan Example", handbook)
        self.assertIn(handbook, first_sync)
        self.assertIn("Who would you like to speak with?", first_sync)
        second_sync = self.module.build_scam_screening_prompt("Jordan Example", first_sync)
        self.assertEqual(second_sync.count("ROOTCALL ORIGINAL HANDBOOK BEGIN"), 1)
        self.assertEqual(second_sync.count(handbook), 1)

    def test_update_screening_identity_updates_prompt_and_greeting_without_publishing_agent(self):
        agent = {"response_engine": {"type": "retell-llm", "llm_id": "llm-test"}}
        llm = {"general_prompt": "Original master handbook text"}
        with patch.object(self.service, "_get", side_effect=[agent, llm]) as get, patch.object(self.service, "update_llm", return_value={"ok": True}) as update_llm, patch.object(self.service, "publish_agent") as publish:
            result = self.service.update_screening_identity("agent-test", "Jordan Example")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(get.call_args_list[0].args[0], "/get-agent/agent-test")
        self.assertEqual(get.call_args_list[1].args[0], "/get-retell-llm/llm-test")
        self.assertEqual(update_llm.call_args.kwargs["llm_id"], "llm-test")
        self.assertIn("Jordan Example", update_llm.call_args.kwargs["general_prompt"])
        self.assertIn("Original master handbook text", update_llm.call_args.kwargs["general_prompt"])
        self.assertEqual(
            update_llm.call_args.kwargs["begin_message"],
            "Hello, you've reached RootCall AI Assistant. Who would you like to speak with?"
        )
        publish.assert_not_called()

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

    def test_transfer_updates_llm_preserves_tools_and_sip_invite_without_republishing(self):
        existing_tools = [{"type": "custom", "name": "lookup_contact"}]
        agent = {"response_engine": {"type": "retell-llm", "llm_id": "llm-test"}}
        with patch.object(self.service, "_get", side_effect=[agent, {"general_tools": existing_tools}]), \
                patch.object(self.service, "_patch", return_value={}) as update, \
                patch.object(self.service, "publish_agent") as publish:
            self.service.configure_transfer_tool("agent-test", "+12025550102")
        update.assert_called_once_with("/update-retell-llm/llm-test", {
            "general_tools": existing_tools + [
                {"type": "end_call", "name": "end_call", "description": "End calls that are identified as spam, scams, or unsafe."},
                {
                    "type": "transfer_call", "name": "transfer_call",
                    "description": "Transfer a screened legitimate caller to this RootCall customer's personal phone.",
                    "transfer_destination": {"type": "predefined", "number": "+12025550102"},
                    "transfer_option": {"type": "cold_transfer", "cold_transfer_mode": "sip_invite"},
                },
            ],
        }, expected=200)
        publish.assert_not_called()

    def test_published_llm_is_copied_and_agent_moved_to_it(self):
        agent = {"response_engine": {"type": "retell-llm", "llm_id": "llm-old"}, "version": 3, "is_published": True}
        llm = {"general_prompt": "P", "begin_message": "B", "model": "gpt-4.1", "general_tools": [], "version": 3}
        calls = []

        def fake_post(path, payload, expected=None):
            calls.append((path, payload))
            if path == "/create-retell-llm":
                return {"llm_id": "llm-new"}
            return {"version": 4}

        with patch.object(self.service, "_get", side_effect=[agent, llm]), \
                patch.object(self.service, "_patch", side_effect=[RuntimeError("Cannot update published LLM"), {}]) as patched, \
                patch.object(self.service, "_post", side_effect=fake_post), \
                patch.object(self.service, "publish_agent") as publish:
            self.service.configure_transfer_tool("agent-test", "+12025550102")
        created = dict(calls)["/create-retell-llm"]
        self.assertEqual(created["general_prompt"], "P")
        self.assertEqual(created["begin_message"], "B")
        self.assertTrue(any(t.get("name") == "transfer_call" for t in created["general_tools"]))
        self.assertNotIn("version", created)
        self.assertEqual(dict(calls)["/create-agent-version/agent-test"], {"base_version": 3})
        self.assertEqual(patched.call_args.args[0], "/update-agent/agent-test")
        self.assertEqual(patched.call_args.args[1]["response_engine"], {"type": "retell-llm", "llm_id": "llm-new"})
        publish.assert_called_once_with("agent-test", version=4)

    def test_other_llm_update_errors_are_not_swallowed(self):
        agent = {"response_engine": {"type": "retell-llm", "llm_id": "llm-old"}}
        with patch.object(self.service, "_get", side_effect=[agent, {"general_tools": []}]), \
                patch.object(self.service, "_patch", side_effect=RuntimeError("rate limited")), \
                patch.object(self.service, "_post") as post:
            with self.assertRaises(RuntimeError):
                self.service.configure_transfer_tool("agent-test", "+12025550102")
        post.assert_not_called()

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

    def test_voice_change_creates_and_publishes_only_the_returned_draft(self):
        with patch.object(self.service, "list_voices", return_value=[{"voice_id": "voice-test"}]), \
                patch.object(self.service, "_get", side_effect=[
                    {"version": 3, "is_published": True}, {"version": 4},
                ]), patch.object(self.service, "_post", return_value={"version": 4}) as post, \
                patch.object(self.service, "_patch", return_value={"voice_id": "voice-test"}) as update, \
                patch.object(self.service, "publish_agent") as publish:
            self.service.update_voice("agent-test", "voice-test")
        post.assert_called_once_with("/create-agent-version/agent-test", {"base_version": 3}, expected=(200, 201))
        update.assert_called_once_with("/update-agent/agent-test", {"version": 4, "voice_id": "voice-test"}, expected=200)
        publish.assert_called_once_with("agent-test", version=4)

    def test_voice_change_does_not_publish_a_different_draft(self):
        with patch.object(self.service, "list_voices", return_value=[{"voice_id": "voice-test"}]), \
                patch.object(self.service, "_get", side_effect=[
                    {"version": 3, "is_published": True}, {"version": 5},
                ]), patch.object(self.service, "_post", return_value={"version": 4}), \
                patch.object(self.service, "_patch", return_value={}), \
                patch.object(self.service, "publish_agent") as publish:
            with self.assertRaisesRegex(RuntimeError, "refusing to publish"):
                self.service.update_voice("agent-test", "voice-test")
        publish.assert_not_called()

    def test_voice_catalog_accepts_list_and_wrapped_provider_responses(self):
        voices = [{"voice_id": "voice-test"}]
        for response in (voices, {"voices": voices}):
            with self.subTest(response=response), patch.object(self.service, "_get", return_value=response):
                self.assertEqual(self.service.list_voices(), voices)


if __name__ == "__main__":
    unittest.main()