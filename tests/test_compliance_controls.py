"""Reference checks for opt-out, suppression, feedback, and DNS text.

No network, no mailbox, and no DNS publish.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reference.dns_auth import dmarc_problems, ses_spf_change, spf_problems  # noqa: E402
from reference.feedback import hmac_authenticator, ingest_feedback  # noqa: E402
from reference.retry import retry_disposition  # noqa: E402
from reference.sender_policy import from_address_problem, postal_address_problem  # noqa: E402
from reference.sns_wake import assess_inbound_relay, string_to_sign  # noqa: E402
from reference.suppression import SuppressionLog  # noqa: E402
from reference.unsubscribe import decide_one_click, dkim_covers_one_click, list_unsubscribe_headers, one_click_token  # noqa: E402
from tests.test_reply_gate import ALLOWLIST, deliver, enabled_hello_policy, human_message, rates, request, template_message  # noqa: E402
from reference.binding import payload_sha256  # noqa: E402
from reference.reply_gate import delivery_allowed  # noqa: E402
from reference.reservation import ReservationLedger  # noqa: E402

TOPIC = "arn:aws:sns:us-east-1:EXAMPLE_ACCOUNT_ID:example-feedback"
CERT = "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-00000000000000000000000000000000.pem"
KEY = b"example-feedback-key"
SECRET = b"example-unsubscribe-secret"
NOW = datetime(2026, 11, 7, 2, 0, 30, tzinfo=timezone.utc)


def log():
    return SuppressionLog(Path(tempfile.mkdtemp()) / "suppression.jsonl")


def signed(message, authenticator, message_id="example-sns-feedback"):
    envelope = {
        "Type": "Notification",
        "MessageId": message_id,
        "TopicArn": TOPIC,
        "Message": json.dumps(message),
        "Timestamp": "2026-11-07T02:00:00.000Z",
        "SignatureVersion": "2",
        "SigningCertURL": CERT,
        "signature_valid": True,
    }
    material = string_to_sign(envelope)
    envelope["Signature"] = hmac.new(KEY, material.encode("utf-8"), hashlib.sha256).hexdigest()
    if authenticator is None:
        envelope["Signature"] = "0" * 64
    return envelope


def bounce(address, feedback_id, bounce_type="Permanent"):
    return {
        "notificationType": "Bounce",
        "bounce": {
            "bounceType": bounce_type,
            "bouncedRecipients": [{"emailAddress": address}],
            "feedbackId": feedback_id,
            "timestamp": "2026-11-07T02:00:00.000Z",
        },
    }


class UnsubscribeTests(unittest.TestCase):
    def test_get_does_not_suppress_and_post_is_idempotent(self):
        store = log()
        token = one_click_token(SECRET, "Pat <pat@example.net>", "news.example.com")
        request_post = {
            "method": "POST",
            "https": True,
            "uri": "https://example.com/unsubscribe/opaque",
            "content_type": "application/x-www-form-urlencoded",
            "body": "List-Unsubscribe=One-Click",
            "recipient": "pat@example.net",
            "list_id": "news.example.com",
            "token": token,
        }
        preview = dict(request_post, method="GET")
        self.assertEqual(decide_one_click(preview, store, secret=SECRET)["status"], "confirmation_only")
        self.assertIsNone(store.lookup("pat@example.net"))
        self.assertEqual(decide_one_click(request_post, store, secret=SECRET)["status"], "suppressed")
        again = decide_one_click(request_post, store, secret=SECRET)
        self.assertEqual(again["status"], "already_suppressed")
        self.assertFalse(again["wrote"])
        self.assertEqual(len(store.feedback_ids()), 0)
        rows = store.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)
        headed = dict(request_post, authorization="Bearer example")
        self.assertEqual(decide_one_click(headed, store, secret=SECRET)["reason"], "login_or_cookie_not_allowed")
        wrong = dict(request_post, body="List-Unsubscribe=Confirm", recipient="other@example.net")
        wrong["token"] = one_click_token(SECRET, "other@example.net", "news.example.com")
        self.assertEqual(decide_one_click(wrong, store, secret=SECRET)["reason"], "body_not_one_click")
        self.assertIsNone(store.lookup("other@example.net"))

    def test_promotional_headers_are_not_required_on_support(self):
        headers = list_unsubscribe_headers(
            https_uri="https://example.com/unsubscribe/opaque",
            mailto_uri="mailto:unsubscribe@example.com",
        )
        self.assertEqual(headers["list_unsubscribe_post"], "List-Unsubscribe=One-Click")
        self.assertTrue(dkim_covers_one_click(["List-Unsubscribe", "List-Unsubscribe-Post", "From"]))
        self.assertFalse(dkim_covers_one_click(["List-Unsubscribe"]))
        with self.assertRaises(ValueError):
            list_unsubscribe_headers(https_uri="http://example.com/unsubscribe/opaque")
        policy = enabled_hello_policy()
        policy["auto_reply"]["human_only_roles"].append("hello")
        policy["auto_reply"]["rules"][0]["enabled"] = False
        support = human_message()
        self.assertNotIn("list_unsubscribe", support["headers"])
        self.assertTrue(
            deliver(
                policy,
                support,
                req=request(),
                approval=_approval(support),
                allow_hosts=[],
                required_assets=[],
            )
        )
        promotional = human_message(
            **{
                "from": "news@example.com",
                "mail_class": "promotional_bulk",
                "template_id": "news-example",
            }
        )
        plain = dict(allow_hosts=[], required_assets=[])
        self.assertFalse(
            deliver(policy, promotional, req=request(role="marketing"), approval=_approval(promotional), **plain)
        )
        promotional["headers"] = dict(promotional["headers"], **headers)
        promotional["dkim_signed_headers"] = ["List-Unsubscribe", "List-Unsubscribe-Post"]
        blocked = deliver(
            policy,
            promotional,
            req=request(role="marketing"),
            approval=_approval(promotional),
            postal_address=None,
            **plain,
        )
        self.assertFalse(blocked)
        released = deliver(
            policy,
            promotional,
            req=request(role="marketing"),
            approval=_approval(promotional),
            postal_address="1 Example Plaza, Example City",
            **plain,
        )
        self.assertTrue(released)


class SuppressionAndFeedbackTests(unittest.TestCase):
    def test_suppression_survives_a_new_log_and_blocks_a_retry(self):
        path = Path(tempfile.mkdtemp()) / "suppression.jsonl"
        first = SuppressionLog(path)
        self.assertEqual(first.suppress("pat@example.net", reason="opt_out", source_id="opt-out-1"), "suppressed")
        second = SuppressionLog(path)
        self.assertIsNotNone(second.lookup("Pat <pat@example.net>"))
        policy = enabled_hello_policy()
        message = template_message()
        self.assertFalse(deliver(policy, message, suppression_log=second))
        self.assertEqual(
            retry_disposition(phase="before_claim", error="throttle", attempt=1, cap=3, suppressed=True),
            "do_not_send",
        )
        self.assertEqual(
            retry_disposition(phase="after_claim", error="timeout", attempt=1, cap=3, suppressed=False),
            "do_not_retry",
        )
        self.assertEqual(
            retry_disposition(phase="before_claim", error="throttle", attempt=1, cap=3, suppressed=False),
            "retry_before_claim",
        )
        self.assertFalse(deliver(policy, message, send_attempt=4))

    def test_feedback_requires_a_signature_freshness_and_replay_claim(self):
        store = log()
        authenticator = hmac_authenticator(KEY)
        rates_ok = {"events_last_minute": 0}
        first = ingest_feedback(
            signed(bounce("pat@example.net", "feedback-example-1"), authenticator),
            expected_topic_arn=TOPIC,
            authenticate=authenticator,
            log=store,
            now=NOW,
            rate_state=rates_ok,
        )
        self.assertEqual(first["disposition"], "applied")
        self.assertIsNotNone(store.lookup("pat@example.net"))
        forged = signed(bounce("other@example.net", "feedback-example-1"), authenticator, message_id="sns-replay")
        replay = ingest_feedback(
            forged,
            expected_topic_arn=TOPIC,
            authenticate=authenticator,
            log=store,
            now=NOW,
            rate_state=rates_ok,
        )
        self.assertEqual(replay["disposition"], "replay")
        self.assertEqual(replay["suppressed"], [])
        self.assertIsNone(store.lookup("other@example.net"))
        trusted_flag = signed(bounce("third@example.net", "feedback-example-2"), None)
        trusted_flag["signature_valid"] = True
        rejected = ingest_feedback(
            trusted_flag,
            expected_topic_arn=TOPIC,
            authenticate=authenticator,
            log=store,
            now=NOW,
            rate_state=rates_ok,
        )
        self.assertEqual(rejected["disposition"], "unauthenticated")
        self.assertIsNone(store.lookup("third@example.net"))
        stale = ingest_feedback(
            signed(bounce("fourth@example.net", "feedback-example-3"), authenticator, message_id="sns-stale"),
            expected_topic_arn=TOPIC,
            authenticate=authenticator,
            log=store,
            now=datetime(2026, 11, 7, 5, 0, tzinfo=timezone.utc),
            rate_state=rates_ok,
        )
        self.assertEqual(stale["disposition"], "timestamp_stale")
        transient = ingest_feedback(
            signed(bounce("fifth@example.net", "feedback-example-4", "Transient"), authenticator, message_id="sns-soft"),
            expected_topic_arn=TOPIC,
            authenticate=authenticator,
            log=store,
            now=NOW,
            rate_state=rates_ok,
        )
        self.assertEqual(transient["disposition"], "transient")
        self.assertIsNone(store.lookup("fifth@example.net"))
        mismatch = ingest_feedback(
            signed(bounce("sixth@example.net", "feedback-example-5"), authenticator, message_id="sns-topic"),
            expected_topic_arn=TOPIC + "-other",
            authenticate=authenticator,
            log=store,
            now=NOW,
            rate_state=rates_ok,
        )
        self.assertEqual(mismatch["disposition"], "topic_mismatch")
        flooded = ingest_feedback(
            signed(bounce("seventh@example.net", "feedback-example-6"), authenticator, message_id="sns-rate"),
            expected_topic_arn=TOPIC,
            authenticate=authenticator,
            log=store,
            now=NOW,
            rate_state={"events_last_minute": 60},
        )
        self.assertEqual(flooded["disposition"], "rate_limited")
        self.assertIsNone(store.lookup("seventh@example.net"))
        complaint = {
            "notificationType": "Complaint",
            "complaint": {
                "complaintFeedbackType": "abuse",
                "complainedRecipients": [{"emailAddress": "complainer@example.net"}],
                "feedbackId": "feedback-complaint-1",
            },
        }
        complained = ingest_feedback(
            signed(complaint, authenticator, message_id="sns-complaint"),
            expected_topic_arn=TOPIC,
            authenticate=authenticator,
            log=store,
            now=NOW,
            rate_state=rates_ok,
        )
        self.assertEqual(complained["disposition"], "applied")
        self.assertIsNotNone(store.lookup("complainer@example.net"))

    def test_inbound_relay_is_not_the_feedback_consumer(self):
        from tests.test_sns_wake import envelope

        relay = assess_inbound_relay(
            envelope(),
            expected_topic_arn="arn:aws:sns:us-east-1:EXAMPLE_ACCOUNT_ID:example-inbound",
            expected_bucket="example-com-inbound-mail",
            signature_valid=True,
        )
        self.assertEqual(relay["kind"], "inbound_s3_relay")
        self.assertFalse(relay["feedback_handled"])
        self.assertEqual(relay["reference"]["object_key"], "raw/EXAMPLE_OBJECT_KEY")
        self.assertEqual(relay["problems"], ["freshness_unproven", "replay_unproven", "rate_unproven"])
        bounce_relay = assess_inbound_relay(
            signed(bounce("pat@example.net", "feedback-not-on-the-relay"), hmac_authenticator(KEY)),
            expected_topic_arn=TOPIC,
            expected_bucket="example-com-inbound-mail",
            signature_valid=True,
        )
        self.assertFalse(bounce_relay["feedback_handled"])
        self.assertIsNone(bounce_relay["reference"])
        self.assertIn("not_an_s3_pointer", bounce_relay["problems"])


class DnsAndSenderTests(unittest.TestCase):
    def test_placeholder_spf_and_two_dmarc_records_are_permanent_errors(self):
        spf = spf_problems(["v=spf1 ip4:YOUR_SERVER_IP ~all"])
        self.assertIn("spf_placeholder_mechanism", spf)
        self.assertIn("spf_ip4_invalid", spf)
        dmarc = dmarc_problems(
            [
                "v=DMARC1; p=none;",
                "v=DMARC1; p=none; rua=mailto:dmarc-reports@example.com",
            ]
        )
        self.assertEqual(dmarc, ["dmarc_permanent_error_multiple"])
        unchanged = ses_spf_change(["v=spf1 ip4:YOUR_SERVER_IP ~all"], outbound_inventory_verified=False)
        self.assertFalse(unchanged["mutate"])
        self.assertEqual(unchanged["records"], ["v=spf1 ip4:YOUR_SERVER_IP ~all"])
        self.assertNotIn("include:amazonses.com", unchanged["records"][0])
        inventoried = ses_spf_change(["v=spf1 ip4:YOUR_SERVER_IP ~all"], outbound_inventory_verified=True)
        self.assertFalse(inventoried["mutate"])
        self.assertEqual(inventoried["reason"], "reference_does_not_publish_dns")

    def test_support_from_address_cannot_be_a_no_reply_or_a_postal_address(self):
        problem = from_address_problem(
            "noreply@example.com",
            mail_class="customer_support",
            allowlist={"customer_support": ["noreply@example.com", "support@example.com"]},
            verified_domain="example.com",
        )
        self.assertEqual(problem, "noreply_from_not_allowed")
        allowed = from_address_problem(
            "Support <support@example.com>",
            mail_class="customer_support",
            allowlist=ALLOWLIST,
            verified_domain="example.com",
        )
        self.assertIsNone(allowed)
        self.assertEqual(
            postal_address_problem("promotional_bulk", None, "news@example.com"),
            "postal_address_missing",
        )
        self.assertIsNone(postal_address_problem("customer_support", None, "support@example.com"))
        self.assertEqual(
            from_address_problem(
                "1 Example Plaza",
                mail_class="customer_support",
                allowlist=ALLOWLIST,
                verified_domain="example.com",
            ),
            "from_not_allowlisted",
        )

    def test_recipient_daily_cap_holds(self):
        from reference.reply_gate import decide

        decision = decide(request(), enabled_hello_policy(), rates(recipient_sent_last_day=3))
        self.assertEqual(decision["reasons"], ["rate_limited"])


def _approval(message):
    from tests.test_reply_gate import approval_for

    return approval_for(message)


class HashTests(unittest.TestCase):
    def test_support_example_digest_includes_mail_class(self):
        message = json.loads((ROOT / "examples" / "events" / "approved-delivery.json").read_text(encoding="utf-8"))
        self.assertEqual(message["mail_class"], "customer_support")
        self.assertNotIn("list_unsubscribe", message["headers"])
        approval = json.loads((ROOT / "examples" / "events" / "approval-record.json").read_text(encoding="utf-8"))
        self.assertEqual(approval["payload_sha256"], payload_sha256(message))
        self.assertFalse(
            delivery_allowed(
                request=request(role="support"),
                policy=json.loads(
                    (ROOT / "shared" / "policies" / "auto-reply-authorization.example.json").read_text(encoding="utf-8")
                ),
                rate_state=rates(),
                message=message,
                ledger=ReservationLedger(),
                suppression_log=log(),
                sender_allowlist=ALLOWLIST,
                verified_domain="example.com",
            )
        )


if __name__ == "__main__":
    unittest.main()
