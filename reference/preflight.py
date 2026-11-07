"""Classify mail that must not become a reply, before any draft exists.

Header values are untrusted data. This module only detects automated notices,
tests, and no-reply senders. It does not decide that a person is allowed to send.
"""

from __future__ import annotations

from reference.binding import addr_spec

_NOTICE_CONTENT_PREFIXES = (
    "multipart/report",
    "message/delivery-status",
    "message/disposition-notification",
)
_NOREPLY_LOCAL_PARTS = frozenset(
    {
        "noreply",
        "no-reply",
        "donotreply",
        "do-not-reply",
        "mailer-daemon",
        "mailerdaemon",
        "postmaster",
        "bounce",
        "bounces",
    }
)
_PRECEDENCE_STOP = frozenset({"bulk", "junk", "list", "auto_reply", "auto-reply"})
_SUBJECT_PREFIXES = (
    "[test]",
    "[notice]",
    "automatic reply:",
    "undeliverable:",
    "delivery status notification",
)


def classify_inbound(headers, *, suppression_hit=False, own_addresses=()):
    """Return a stop reason, or None when drafting may be considered.

    `suppression_hit` is supplied by the trusted worker from the suppression
    list and the local opt-out store. The message body cannot clear it.
    `own_addresses` are this domain's outbound role addresses. Mail from one
    of them is a loop, not a new inquiry.
    """

    if suppression_hit:
        return "suppression_or_opt_out"
    if not isinstance(headers, dict):
        return "untrusted_headers_unreadable"

    folded = {str(key).lower(): "" if value is None else str(value) for key, value in headers.items()}
    if "return-path" in folded and folded.get("return-path", "").strip().lower() in {"", "<>"}:
        return "null_reverse_path"
    auto_submitted = folded.get("auto-submitted", "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return "test_or_notice"
    if folded.get("x-loop", "").strip():
        return "test_or_notice"
    suppress = folded.get("x-auto-response-suppress", "")
    tokens = {part.strip().lower() for part in suppress.replace(";", ",").split(",") if part.strip()}
    if tokens & {"all", "autoreply"}:
        return "test_or_notice"
    precedence = folded.get("precedence", "").strip().lower()
    if precedence in _PRECEDENCE_STOP:
        return "test_or_notice"
    if folded.get("list-id", "").strip() or folded.get("list-unsubscribe", "").strip():
        return "mailing_list"
    content_type = folded.get("content-type", "").strip().lower()
    if content_type.startswith(_NOTICE_CONTENT_PREFIXES):
        return "test_or_notice"
    subject = folded.get("subject", "").strip().lower()
    if subject.startswith(_SUBJECT_PREFIXES):
        return "test_or_notice"
    sender = folded.get("from", "")
    local = _local_part(sender)
    if local in _NOREPLY_LOCAL_PARTS:
        return "noreply_sender"
    try:
        identity = addr_spec(sender)
    except ValueError:
        identity = ""
    owned = set()
    for item in own_addresses:
        try:
            owned.add(addr_spec(item))
        except (TypeError, ValueError):
            return "untrusted_headers_unreadable"
    if identity and identity in owned:
        return "own_address_loop"
    return None


def _local_part(from_header):
    text = from_header.strip().lower()
    if "<" in text and ">" in text:
        text = text.split("<", 1)[1].split(">", 1)[0]
    if "@" not in text:
        return ""
    return text.split("@", 1)[0].strip()
