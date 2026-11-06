"""SNS wake checks. No network."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reference.sns_wake import (  # noqa: E402
    signing_cert_url_ok,
    string_to_sign,
    subscribe_url_ok,
    wake_from_verified_notification,
)

TOPIC = "arn:aws:sns:us-east-1:EXAMPLE_ACCOUNT_ID:example-inbound"
CERT = "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-00000000000000000000000000000000.pem"


def envelope():
    message = {
        "notificationType": "Received",
        "receipt": {
            "action": {
                "type": "S3",
                "bucketName": "example-com-inbound-mail",
                "objectKey": "raw/EXAMPLE_OBJECT_KEY",
            }
        },
        "mail": {"source": "attacker-supplied-bucket.example.net"},
    }
    return {
        "Type": "Notification",
        "MessageId": "example-sns-id",
        "TopicArn": TOPIC,
        "Subject": "SES receipt",
        "Message": json.dumps(message),
        "Timestamp": "2026-11-06T00:00:00.000Z",
        "SignatureVersion": "2",
        "Signature": "example-signature",
        "SigningCertURL": CERT,
    }


class SnsWakeTests(unittest.TestCase):
    def test_string_to_sign_includes_subject_when_present(self):
        signed = string_to_sign(envelope())
        self.assertIn("\nSubject\nSES receipt\n", signed)
        self.assertTrue(signed.endswith("Type\nNotification\n"))

    def test_certificate_url_is_pinned_to_the_topic_region(self):
        self.assertTrue(signing_cert_url_ok(CERT, "us-east-1"))
        self.assertFalse(signing_cert_url_ok("http://sns.us-east-1.amazonaws.com/SimpleNotificationService-a.pem", "us-east-1"))
        self.assertFalse(signing_cert_url_ok("https://sns.eu-west-1.amazonaws.com/SimpleNotificationService-a.pem", "us-east-1"))
        self.assertFalse(signing_cert_url_ok("https://evil.example.net/SimpleNotificationService-a.pem", "us-east-1"))
        self.assertFalse(signing_cert_url_ok(CERT + "?x=1", "us-east-1"))

    def test_subscribe_url_cannot_leave_sns(self):
        self.assertTrue(subscribe_url_ok("https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription&Token=example", "us-east-1"))
        self.assertFalse(subscribe_url_ok("https://example.net/sns", "us-east-1"))

    def test_wake_requires_a_verified_signature_and_the_configured_bucket(self):
        with self.assertRaises(ValueError):
            wake_from_verified_notification(
                envelope(),
                expected_topic_arn=TOPIC,
                expected_bucket="example-com-inbound-mail",
                signature_valid=False,
            )
        forged = envelope()
        forged["TopicArn"] = "arn:aws:sns:us-east-1:EXAMPLE_ACCOUNT_ID:other"
        with self.assertRaises(ValueError):
            wake_from_verified_notification(
                forged,
                expected_topic_arn=TOPIC,
                expected_bucket="example-com-inbound-mail",
                signature_valid=True,
            )
        wake = wake_from_verified_notification(
            envelope(),
            expected_topic_arn=TOPIC,
            expected_bucket="example-com-inbound-mail",
            signature_valid=True,
        )
        self.assertEqual(wake["object_key"], "raw/EXAMPLE_OBJECT_KEY")
        self.assertEqual(wake["access"], "read_only")


class AwsTemplateTests(unittest.TestCase):
    def test_receipt_rule_stores_a_pointer_and_does_not_set_message_kms(self):
        rule = json.loads((ROOT / "examples" / "aws" / "create-receipt-rule.example.json").read_text(encoding="utf-8"))
        action = rule["Rule"]["Actions"][0]["S3Action"]
        self.assertEqual(action["BucketName"], "example-com-inbound-mail")
        self.assertNotIn("KmsKeyArn", action)
        blob = json.dumps(rule)
        self.assertNotIn("AKIA", blob)
        self.assertNotRegex(blob, r":[0-9]{12}:")


if __name__ == "__main__":
    unittest.main()
