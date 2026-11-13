from unittest.mock import patch

from app.services.telnyx_service import TelnyxService


def test_new_trunk_payload_uses_a_dnis_format_telnyx_accepts():
    svc = TelnyxService()
    with patch.object(TelnyxService, "_get", return_value={"data": []}), \
         patch.object(TelnyxService, "_post", return_value={"data": {"id": "c9"}}) as post_call, \
         patch.object(TelnyxService, "ensure_outbound_voice_profile"), \
         patch.object(TelnyxService, "_ensure_retell_fqdn"):
        svc.get_or_create_retell_trunk("RootCall-Retell-1", "u", "p")
    payload = post_call.call_args.kwargs["json"]
    assert payload["inbound"]["dnis_number_format"] == "+e164"


def test_new_trunk_payload_uses_codec_names_telnyx_accepts():
    svc = TelnyxService()
    with patch.object(TelnyxService, "_get", return_value={"data": []}), \
         patch.object(TelnyxService, "_post", return_value={"data": {"id": "c9"}}) as post_call, \
         patch.object(TelnyxService, "ensure_outbound_voice_profile"), \
         patch.object(TelnyxService, "_ensure_retell_fqdn"):
        svc.get_or_create_retell_trunk("RootCall-Retell-1", "u", "p")
    codecs = post_call.call_args.kwargs["json"]["inbound"]["codecs"]
    assert codecs == ["G722", "G711U", "G711A"]


def test_retell_address_is_added_before_outbound_profile_is_attached():
    svc = TelnyxService()
    calls = []
    with patch.object(TelnyxService, "_get", return_value={"data": []}), \
         patch.object(TelnyxService, "_post", return_value={"data": {"id": "c9"}}), \
         patch.object(TelnyxService, "ensure_outbound_voice_profile",
                      side_effect=lambda *a, **k: calls.append("profile")), \
         patch.object(TelnyxService, "_ensure_retell_fqdn",
                      side_effect=lambda *a, **k: calls.append("fqdn")):
        svc.get_or_create_retell_trunk("RootCall-Retell-1", "u", "p")
    assert calls == ["fqdn", "profile"]


def test_retell_srv_record_is_sent_without_a_port():
    svc = TelnyxService()
    with patch.object(TelnyxService, "_get", return_value={"data": []}), \
         patch.object(TelnyxService, "_post", return_value={"data": {}}) as post_call:
        svc._ensure_retell_fqdn("c1")
    payload = post_call.call_args.kwargs["json"]
    assert payload["fqdn"] == "sip.retellai.com"
    assert payload["dns_record_type"] == "srv"
    assert "port" not in payload


def test_classic_trunk_survives_profile_attach_failure():
    from unittest.mock import patch
    from app.services.telnyx_service import TelnyxService
    with patch.object(TelnyxService, "__init__", lambda self: None), \
         patch.object(TelnyxService, "_get", return_value={"data": []}), \
         patch.object(TelnyxService, "_post", return_value={"data": {"id": "t1"}}), \
         patch.object(TelnyxService, "_ensure_retell_fqdn"), \
         patch.object(TelnyxService, "ensure_outbound_voice_profile",
                      side_effect=RuntimeError("must be fully configured")):
        trunk, _, _ = TelnyxService().get_or_create_retell_trunk("n", "u", "p")
    assert trunk["id"] == "t1"


def test_new_trunk_is_created_with_a_sip_login():
    svc = TelnyxService()
    with patch.object(TelnyxService, "_get", return_value={"data": []}), \
         patch.object(TelnyxService, "_post", return_value={"data": {"id": "c9"}}) as post_call, \
         patch.object(TelnyxService, "ensure_outbound_voice_profile"), \
         patch.object(TelnyxService, "_ensure_retell_fqdn"):
        svc.get_or_create_retell_trunk("RootCall-Retell-1", "user_1", "pw_1")
    payload = post_call.call_args.kwargs["json"]
    assert payload["user_name"] == "user_1"
    assert payload["password"] == "pw_1"


def test_trunk_without_login_is_detected_and_login_can_be_set():
    svc = TelnyxService()
    with patch.object(TelnyxService, "_get", return_value={"data": {"user_name": None}}):
        assert svc.trunk_needs_credentials("c1") is True
    with patch.object(TelnyxService, "_get", return_value={"data": {"user_name": "rootcall_1"}}):
        assert svc.trunk_needs_credentials("c1") is False
    with patch.object(TelnyxService, "_patch", return_value={}) as patch_call:
        svc.set_trunk_credentials("c1", "u", "p")
    assert patch_call.call_args.kwargs["json"] == {"user_name": "u", "password": "p"}


def test_telnyx_login_is_letters_and_numbers_only():
    from app.services.customer_onboarding import telnyx_sip_login
    username, password = telnyx_sip_login(82)
    assert username.isalnum() and password.isalnum()
    assert username.endswith("82") and len(password) >= 16
    assert telnyx_sip_login(82) == (username, password)
