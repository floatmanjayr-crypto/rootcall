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
