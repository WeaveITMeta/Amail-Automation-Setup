"""Checks for an SNS HTTPS wake before any MIME is read.

The function does not fetch certificates and does not send HTTP. The Worker
or other adapter verifies the SNS signature over `string_to_sign` using the
certificate at the validated URL, then passes `signature_valid=True`. A JSON
field named Signature is not itself proof.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from reference.object_ref import object_reference


def string_to_sign(envelope):
    """Build the SNS version-2 string to sign for a Notification."""

    if not isinstance(envelope, dict):
        raise ValueError("SNS envelope is missing")
    if envelope.get("Type") != "Notification":
        raise ValueError("SNS type is not Notification")
    if envelope.get("SignatureVersion") != "2":
        raise ValueError("SNS signature version must be 2")
    fields = ["Message", "MessageId"]
    if "Subject" in envelope and envelope.get("Subject") not in (None, ""):
        fields.append("Subject")
    fields.extend(["Timestamp", "TopicArn", "Type"])
    lines = []
    for field in fields:
        value = envelope.get(field)
        if not isinstance(value, str) or value == "":
            raise ValueError(f"SNS field {field} is missing")
        lines.append(field)
        lines.append(value)
    return "\n".join(lines) + "\n"


def signing_cert_url_ok(url, region):
    """True only for an SNS certificate URL in the topic's region."""

    if not isinstance(url, str) or not isinstance(region, str) or not region:
        return False
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path or ""
    if parsed.scheme != "https":
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.port not in (None, 443):
        return False
    if host != f"sns.{region}.amazonaws.com":
        return False
    if not path.startswith("/SimpleNotificationService-") or not path.endswith(".pem"):
        return False
    if ".." in path.split("/"):
        return False
    return True


def subscribe_url_ok(url, region):
    """True only for a SubscribeURL on the SNS host for this region.

    Query parameters are part of the real confirmation URL. The host is not
    allowed to be anything else, which is what keeps confirmation from
    becoming a request to an arbitrary site.
    """

    if not isinstance(url, str) or not isinstance(region, str) or not region:
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        return False
    if parsed.port not in (None, 443):
        return False
    if (parsed.hostname or "") != f"sns.{region}.amazonaws.com":
        return False
    return True


def wake_from_verified_notification(envelope, *, expected_topic_arn, expected_bucket, signature_valid):
    """Return the object reference after the signature check has succeeded."""

    if signature_valid is not True:
        raise ValueError("SNS signature was not verified")
    if not isinstance(expected_topic_arn, str) or envelope.get("TopicArn") != expected_topic_arn:
        raise ValueError("SNS topic does not match the configured topic")
    region = _region(expected_topic_arn)
    if not signing_cert_url_ok(envelope.get("SigningCertURL"), region):
        raise ValueError("SNS signing certificate URL is not an SNS URL for this region")
    string_to_sign(envelope)
    try:
        payload = json.loads(envelope["Message"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("SNS message is not the SES receipt JSON") from exc
    action = (((payload or {}).get("receipt") or {}).get("action") or {})
    if action.get("type") != "S3":
        raise ValueError("SES action is not the S3 pointer")
    return object_reference(
        {"bucket": action.get("bucketName"), "object_key": action.get("objectKey")},
        expected_bucket,
    )


def _region(topic_arn):
    parts = topic_arn.split(":")
    if len(parts) < 6 or parts[0] != "arn" or parts[1] != "aws" or parts[2] != "sns" or not parts[3]:
        raise ValueError("SNS topic ARN is not usable")
    return parts[3]
