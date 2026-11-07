"""Authenticated bounce and complaint ingestion.

This is the outbound feedback consumer. It is not the inbound S3 relay.
The relay may validate an SNS signature and a topic. It does not suppress
recipients and it does not interpret bounce or complaint payloads.

The authenticator receives the SNS string-to-sign and the Signature field.
A JSON flag named signature_valid is ignored. This module does not fetch the
signing certificate. The operator's authenticator has to do that verification,
or an equivalent provider check, before it returns true.

Permanent bounces and complaints are suppressed on the first claim of the
provider feedback id. A replay does not apply a different recipient list.
Transient bounces are recorded and do not suppress. Stale, unverified, and
rate-limited notifications are not claimed, so a later good delivery can
still be applied.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from reference.sns_wake import signing_cert_url_ok, string_to_sign
from reference.suppression import SuppressionLog
from reference.timestamps import age_problem, parse_utc

_MAX_RECIPIENTS = 50
_COMPLAINT_SUPPRESS = frozenset({"abuse", "fraud", "virus", "other"})
_COMPLAINT_IGNORE = frozenset({"not-spam"})


def hmac_authenticator(key):
    """Test and local authenticator. Production SNS verification uses the certificate."""

    if not isinstance(key, (bytes, bytearray)) or not key:
        raise ValueError("feedback key is missing")

    def authenticate(material, signature):
        if not isinstance(material, str) or not isinstance(signature, str):
            return False
        expected = hmac.new(bytes(key), material.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    return authenticate


def ingest_feedback(
    envelope,
    *,
    expected_topic_arn,
    authenticate,
    log,
    now,
    rate_state,
    max_age_seconds=3600,
    skew_seconds=300,
    max_events_per_minute=60,
):
    """Verify, deduplicate, and maybe suppress. Never called by the inbound relay."""

    if not isinstance(log, SuppressionLog):
        return _done("log_missing", [])
    if not callable(authenticate):
        return _done("unauthenticated", [])
    structural = _structural_problem(envelope, expected_topic_arn)
    if structural:
        return _done(structural, [])
    try:
        material = string_to_sign(envelope)
    except (TypeError, ValueError):
        return _done("malformed", [])
    if authenticate(material, envelope.get("Signature")) is not True:
        return _done("unauthenticated", [])
    limited = _rate_problem(rate_state, max_events_per_minute)
    if limited:
        return _done(limited, [])
    try:
        stamp = parse_utc(envelope.get("Timestamp"))
        fresh = age_problem(stamp, now, max_age_seconds=max_age_seconds, skew_seconds=skew_seconds)
    except (TypeError, ValueError):
        return _done("malformed", [])
    if fresh:
        return _done(fresh, [])
    try:
        payload = json.loads(envelope.get("Message"))
    except (TypeError, ValueError):
        return _done("malformed", [])
    parsed = _parse_feedback(payload)
    if parsed["disposition"] in {"malformed", "not_a_suppression_event"}:
        return _done(parsed["disposition"], [])
    try:
        claimed = log.apply_feedback(parsed["feedback_id"], addresses=parsed["addresses"], reason=parsed["reason"])
    except (TypeError, ValueError):
        return _done("malformed", [])
    if claimed == "replay":
        return _done("replay", [])
    return _done(parsed["disposition"], list(parsed["addresses"]))


def _structural_problem(envelope, expected_topic_arn):
    if not isinstance(envelope, dict):
        return "malformed"
    if not isinstance(expected_topic_arn, str) or envelope.get("TopicArn") != expected_topic_arn:
        return "topic_mismatch"
    parts = expected_topic_arn.split(":")
    if len(parts) < 4 or not parts[3]:
        return "topic_mismatch"
    if not signing_cert_url_ok(envelope.get("SigningCertURL"), parts[3]):
        return "certificate_untrusted"
    return None


def _rate_problem(rate_state, cap):
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        return "rate_unproven"
    if not isinstance(rate_state, dict):
        return "rate_unproven"
    used = rate_state.get("events_last_minute")
    if isinstance(used, bool) or not isinstance(used, int) or used < 0:
        return "rate_unproven"
    if used >= cap:
        return "rate_limited"
    return None


def _parse_feedback(payload):
    empty = {"addresses": [], "disposition": "malformed", "feedback_id": "", "reason": "needs_review"}
    if not isinstance(payload, dict):
        return empty
    kind = payload.get("notificationType")
    if kind is None:
        kind = payload.get("eventType")
    if kind == "Bounce":
        return _bounce(payload.get("bounce"))
    if kind == "Complaint":
        return _complaint(payload.get("complaint"))
    if kind in {"Delivery", "DeliveryDelay", "Reject", "Send"}:
        return {"addresses": [], "disposition": "not_a_suppression_event", "feedback_id": "", "reason": "needs_review"}
    return empty


def _bounce(bounce):
    if not isinstance(bounce, dict):
        return {"addresses": [], "disposition": "malformed", "feedback_id": "", "reason": "needs_review"}
    feedback_id = bounce.get("feedbackId")
    if not isinstance(feedback_id, str) or not feedback_id:
        return {"addresses": [], "disposition": "malformed", "feedback_id": "", "reason": "needs_review"}
    recipients = _emails(bounce.get("bouncedRecipients"))
    if recipients is None:
        return {"addresses": [], "disposition": "malformed", "feedback_id": feedback_id, "reason": "needs_review"}
    kind = bounce.get("bounceType")
    if kind == "Permanent":
        return {"addresses": recipients, "disposition": "applied", "feedback_id": feedback_id, "reason": "hard_bounce"}
    if kind == "Transient":
        return {"addresses": [], "disposition": "transient", "feedback_id": feedback_id, "reason": "transient"}
    if kind == "Undetermined":
        return {"addresses": [], "disposition": "needs_review", "feedback_id": feedback_id, "reason": "needs_review"}
    return {"addresses": [], "disposition": "malformed", "feedback_id": feedback_id, "reason": "needs_review"}


def _complaint(complaint):
    if not isinstance(complaint, dict):
        return {"addresses": [], "disposition": "malformed", "feedback_id": "", "reason": "needs_review"}
    feedback_id = complaint.get("feedbackId")
    if not isinstance(feedback_id, str) or not feedback_id:
        return {"addresses": [], "disposition": "malformed", "feedback_id": "", "reason": "needs_review"}
    recipients = _emails(complaint.get("complainedRecipients"))
    if recipients is None:
        return {"addresses": [], "disposition": "malformed", "feedback_id": feedback_id, "reason": "needs_review"}
    feedback_type = complaint.get("complaintFeedbackType")
    if feedback_type in _COMPLAINT_IGNORE:
        return {"addresses": [], "disposition": "needs_review", "feedback_id": feedback_id, "reason": "needs_review"}
    if feedback_type is not None and feedback_type not in _COMPLAINT_SUPPRESS:
        return {"addresses": [], "disposition": "needs_review", "feedback_id": feedback_id, "reason": "needs_review"}
    return {"addresses": recipients, "disposition": "applied", "feedback_id": feedback_id, "reason": "complaint"}


def _emails(recipients):
    if not isinstance(recipients, list) or not recipients or len(recipients) > _MAX_RECIPIENTS:
        return None
    found = []
    for item in recipients:
        if not isinstance(item, dict):
            return None
        address = item.get("emailAddress")
        if not isinstance(address, str) or not address:
            return None
        found.append(address)
    return found


def _done(disposition, suppressed):
    return {"disposition": disposition, "suppressed": suppressed}
