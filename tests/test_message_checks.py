"""Message, template, and library checks."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reference.binding import payload_sha256  # noqa: E402
from reference.idempotency import on_conditional_claim  # noqa: E402
from reference.object_ref import object_reference  # noqa: E402
from reference.preflight import classify_inbound  # noqa: E402
from reference.send_ready import rendered_failures  # noqa: E402
from reference.templates import render_template  # noqa: E402
from scripts.validate_library import validate  # noqa: E402


class MessageTests(unittest.TestCase):
    def test_notice_and_suppression_stop_before_a_draft(self):
        self.assertEqual(
            classify_inbound({"Auto-Submitted": "auto-replied", "From": "pat@example.net", "Subject": "Hi"}),
            "test_or_notice",
        )
        self.assertEqual(
            classify_inbound({"From": "Mailer-Daemon <mailer-daemon@example.net>", "Subject": "bounce"}),
            "noreply_sender",
        )
        self.assertEqual(classify_inbound({"From": "pat@example.net", "Subject": "Hello"}, suppression_hit=True), "suppression_or_opt_out")
        self.assertIsNone(classify_inbound({"From": "Pat Lee <pat@example.net>", "Subject": "Question about ACME", "Auto-Submitted": "no"}))
        self.assertEqual(
            classify_inbound({"From": "news@example.net", "List-Id": "<news.example.net>", "Subject": "Weekly"}),
            "mailing_list",
        )
        self.assertEqual(
            classify_inbound({"From": "news@example.net", "List-Unsubscribe": "<https://example.net/u>", "Subject": "Weekly"}),
            "mailing_list",
        )
        self.assertEqual(classify_inbound({"From": "pat@example.net", "Return-Path": "<>", "Subject": "Hi"}), "null_reverse_path")
        self.assertEqual(
            classify_inbound({"From": "pat@example.net", "X-Auto-Response-Suppress": "All", "Subject": "Hi"}),
            "test_or_notice",
        )
        self.assertEqual(
            classify_inbound(
                {"From": "hello@example.com", "Subject": "Hi"},
                own_addresses=["Hello <hello@example.com>"],
            ),
            "own_address_loop",
        )

    def test_claim_happens_before_a_second_run(self):
        self.assertTrue(on_conditional_claim(created=True)["proceed"])
        duplicate = on_conditional_claim(created=False)
        self.assertFalse(duplicate["proceed"])
        self.assertEqual(duplicate["outcome"], "duplicate_ignored")
        with self.assertRaises(ValueError):
            on_conditional_claim(created=None)

    def test_object_comes_from_the_wake_only(self):
        wake = {"bucket": "example-com-inbound-mail", "object_key": "raw/EXAMPLE_OBJECT_KEY"}
        self.assertEqual(
            object_reference(wake, "example-com-inbound-mail")["access"],
            "read_only",
        )
        with self.assertRaises(ValueError):
            object_reference({"bucket": "other-bucket", "object_key": "raw/EXAMPLE_OBJECT_KEY"}, "example-com-inbound-mail")
        with self.assertRaises(ValueError):
            object_reference({"bucket": "example-com-inbound-mail", "object_key": "raw/../secret"}, "example-com-inbound-mail")

    def test_template_rejects_inbound_placeholders(self):
        source = (ROOT / "shared" / "templates" / "hello-first-inquiry.html").read_text(encoding="utf-8")
        rendered = render_template(source, {"organization": "ACME", "role_display": "Hello"})
        self.assertIn("https://assets.example.com/email/hello/mark.png", rendered)
        self.assertNotIn("{{", rendered)
        with self.assertRaises(ValueError):
            render_template(source + "{{subject}}", {"organization": "ACME", "role_display": "Hello", "subject": "injected"})

    def test_rendered_html_requires_https_artwork_and_threading(self):
        html = render_template(
            (ROOT / "shared" / "templates" / "hello-first-inquiry.html").read_text(encoding="utf-8"),
            {"organization": "ACME", "role_display": "Hello"},
        )
        text = render_template(
            (ROOT / "shared" / "templates" / "hello-first-inquiry.txt").read_text(encoding="utf-8"),
            {"organization": "ACME", "role_display": "Hello"},
        )
        message = {
            "html": html,
            "text": text,
            "headers": {
                "in_reply_to": "<example-message@example.net>",
                "references": ["<example-message@example.net>"],
            },
        }
        self.assertEqual(
            rendered_failures(
                message,
                allow_hosts=["assets.example.com"],
                required_assets=["https://assets.example.com/email/hello/mark.png"],
            ),
            [],
        )
        broken = dict(message, html=html.replace("https://", "cid:"))
        self.assertIn("cid_reference", rendered_failures(broken, allow_hosts=["assets.example.com"], required_assets=[]))
        unthreaded = dict(message, headers={})
        self.assertIn(
            "missing_in_reply_to",
            rendered_failures(unthreaded, allow_hosts=["assets.example.com"], required_assets=["https://assets.example.com/email/hello/mark.png"]),
        )

    def test_example_approval_matches_the_example_delivery(self):
        message = json.loads((ROOT / "examples" / "events" / "approved-delivery.json").read_text(encoding="utf-8"))
        approval = json.loads((ROOT / "examples" / "events" / "approval-record.json").read_text(encoding="utf-8"))
        self.assertEqual(approval["payload_sha256"], payload_sha256(message))

    def test_library_validator(self):
        self.assertEqual(validate(), [])


if __name__ == "__main__":
    unittest.main()
