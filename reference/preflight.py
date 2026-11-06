"""Classify mail that must not become a reply, before any draft exists.

Header values are untrusted data. This module only detects automated notices,
tests, and no-reply senders. It does not decide that a person is allowed to send.
"""

from __future__ import annotations

_NOTICE_CONTENT_PREFIXES = (
    "multipart/report",
    "message/delivery-status",
    "message/disposition-notification",
)
_NOREPLY_LOCAL_PARTS = frozenset(
    {"noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster"}
)


def classify_inbound(headers, *, suppression_hit=False):
    """Return a stop reason, or None when drafting may be considered.

    `suppression_hit` is supplied by the trusted worker from the suppression
    list and the local opt-out store. The message body cannot clear it.
    """

    if suppression_hit:
        return "suppression_or_opt_out"
    if not isinstance(headers, dict):
        return "untrusted_headers_unreadable"

    folded = {str(key).lower(): "" if value is None else str(value) for key, value in headers.items()}
    auto_submitted = folded.get("auto-submitted", "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return "test_or_notice"
    precedence = folded.get("precedence", "").strip().lower()
    if precedence in {"bulk", "junk", "list", "auto_reply"}:
        return "test_or_notice"
    content_type = folded.get("content-type", "").strip().lower()
    if content_type.startswith(_NOTICE_CONTENT_PREFIXES):
        return "test_or_notice"
    subject = folded.get("subject", "").strip().lower()
    if subject.startswith("[test]") or subject.startswith("[notice]"):
        return "test_or_notice"
    sender = folded.get("from", "")
    local = _local_part(sender)
    if local in _NOREPLY_LOCAL_PARTS:
        return "noreply_sender"
    return None


def _local_part(from_header):
    text = from_header.strip().lower()
    if "<" in text and ">" in text:
        text = text.split("<", 1)[1].split(">", 1)[0]
    if "@" not in text:
        return ""
    return text.split("@", 1)[0].strip()
