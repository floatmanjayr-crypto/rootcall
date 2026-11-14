import re
import unittest
from pathlib import Path

PORTAL = Path(__file__).resolve().parents[1] / "static" / "client-portal.html"


class PortalCopyTest(unittest.TestCase):
    def setUp(self):
        self.html = PORTAL.read_text(encoding="utf-8")

    def test_customer_visible_text_names_no_vendors(self):
        # Strip scripts, styles and tags: what is left is what a customer can read, plus toast/status
        # strings that live in script literals, which we check separately.
        visible = re.sub(r"<script.*?</script>|<style.*?</style>", "", self.html, flags=re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        self.assertNotRegex(visible, r"(?i)\b(retell|telnyx)\b")
        for phrase in ("Powered by Telnyx", "Searching Telnyx", "Retell workspace", "voices from Retell", "direct-to-Retell", "existing Telnyx number"):
            self.assertNotIn(phrase, self.html)

    def test_phone_input_is_friendly_and_normalized(self):
        self.assertIn("function normalizePhone(", self.html)
        self.assertNotIn("E.164 format", self.html)
        self.assertEqual(self.html.count("normalizePhone("), 3)  # definition + forwarding + contact

    def test_dashboard_has_a_setup_checklist_and_no_debug_logging_of_numbers(self):
        self.assertIn('id="get-started"', self.html)
        self.assertIn("renderGetStarted(setupState)", self.html)
        self.assertNotIn("console.log('My number response:'", self.html)


if __name__ == "__main__":
    unittest.main()


def test_success_page_confirms_payment_honestly():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "static" / "success.html").read_text(encoding="utf-8")
    assert "Welcome to RootCall" in html
    assert "onboarding.html" not in html
    assert "simulateProvisioning" not in html
    assert "/api/payments/status" in html
    assert "/api/payments/verify" not in html
