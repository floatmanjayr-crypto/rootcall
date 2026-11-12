from unittest.mock import patch

from app.services.telnyx_service import TelnyxService


def test_existing_trunk_is_not_modified():
    svc = TelnyxService()
    existing = {"data": [{"id": "c1", "connection_name": "RootCall-Retell-1"}]}
    with patch.object(TelnyxService, "_get", return_value=existing), \
         patch.object(TelnyxService, "_patch") as patch_call, \
         patch.object(TelnyxService, "_post") as post_call:
        conn, user, pw = svc.get_or_create_retell_trunk(
            "RootCall-Retell-1", "u", "p", outbound_voice_profile_id="prof"
        )
    assert conn["id"] == "c1"
    patch_call.assert_not_called()
    post_call.assert_not_called()
