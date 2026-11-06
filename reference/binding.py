"""Bind an approval or a template to the exact bytes that would be sent.

A person approves an artifact in whatever review tool the operator uses.
This module does not read chat, and a sentence such as "approved" is not an
approval. The review tool stores one SHA-256 digest of the canonical delivery
document. The sender recomputes that digest from the message it is about to
hand to SES. The two strings must match, and the approval id is single-use.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re

from reference.templates import render_template

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_APPROVAL_ID = re.compile(r"^approval_[a-z0-9_]{8,80}$")
_ADDR = re.compile(r"^[a-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def addr_spec(value):
    """Return the bare lowercase addr-spec. Display names are not identities."""

    if not isinstance(value, str):
        raise ValueError("address is missing")
    text = value.strip()
    if text.lower() in {"", "<>"}:
        raise ValueError("null address")
    if "<" in text and ">" in text:
        text = text.split("<", 1)[1].split(">", 1)[0].strip()
    text = text.lower()
    if not _ADDR.fullmatch(text):
        raise ValueError("address is not a single addr-spec")
    return text


def payload_sha256(message):
    """Digest the delivery document. A different recipient or body is a different digest."""

    document = canonical_delivery(message)
    blob = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def canonical_delivery(message):
    if not isinstance(message, dict):
        raise ValueError("message is missing")
    headers = message.get("headers")
    if not isinstance(headers, dict):
        raise ValueError("headers are missing")
    references = headers.get("references")
    in_reply_to = headers.get("in_reply_to")
    if not isinstance(in_reply_to, str) or not isinstance(references, list):
        raise ValueError("threading headers are missing")
    to = _addr_list(message.get("to"), minimum=1)
    return {
        "bcc": _addr_list(message.get("bcc", []), minimum=0),
        "cc": _addr_list(message.get("cc", []), minimum=0),
        "draft_id": _token(message.get("draft_id"), "draft_id"),
        "from": addr_spec(message.get("from")),
        "html": _body(message.get("html")),
        "in_reply_to": in_reply_to,
        "references": [str(item) for item in references],
        "subject": _body(message.get("subject")),
        "template_id": _token(message.get("template_id"), "template_id"),
        "template_version": _token(message.get("template_version"), "template_version"),
        "text": _body(message.get("text")),
        "to": to,
    }


def approval_problem(message, approval, consumed_approval_ids):
    """Return a problem string, or None when this approval matches this message once.

    Chat text is not an input. Replay protection is the consumed id set the
    sender persists after a successful handoff to SES. This function does not
    write that set.
    """

    if not isinstance(approval, dict):
        return "approval_invalid"
    if approval.get("permission") != "send" or approval.get("decision") != "approved":
        return "approval_invalid"
    if approval.get("approver") != "person":
        return "approval_invalid"
    approval_id = approval.get("approval_id")
    if not isinstance(approval_id, str) or not _APPROVAL_ID.fullmatch(approval_id):
        return "approval_invalid"
    if not isinstance(consumed_approval_ids, (set, frozenset, list, tuple)):
        return "approval_replay_state_missing"
    if approval_id in set(consumed_approval_ids):
        return "approval_replay"
    digest = approval.get("payload_sha256")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        return "approval_digest_invalid"
    try:
        expected = payload_sha256(message)
    except (TypeError, ValueError):
        return "message_not_bound"
    if not hmac.compare_digest(expected, digest):
        return "approval_mismatch"
    if approval.get("draft_id") != message.get("draft_id"):
        return "approval_mismatch"
    if approval.get("template_id") != message.get("template_id"):
        return "approval_mismatch"
    if str(approval.get("template_version")) != str(message.get("template_version")):
        return "approval_mismatch"
    if approval.get("subject") != message.get("subject"):
        return "approval_mismatch"
    try:
        if addr_spec(approval.get("from")) != addr_spec(message.get("from")):
            return "approval_mismatch"
        approved_to = [addr_spec(item) for item in approval.get("to")]
        actual_to = [addr_spec(item) for item in message.get("to")]
    except (TypeError, ValueError):
        return "approval_mismatch"
    if approved_to != actual_to:
        return "approval_mismatch"
    return None


def template_problem(message, *, text_source, html_source, subject, version, variables, template_id):
    """The automatic body must be the trusted template after allowed substitutions."""

    if not isinstance(message, dict):
        return "template_body_mismatch"
    if message.get("template_id") != template_id:
        return "template_id_mismatch"
    if str(message.get("template_version")) != str(version):
        return "template_version_mismatch"
    if message.get("subject") != subject:
        return "template_subject_mismatch"
    try:
        rendered_text = render_template(text_source, variables)
        rendered_html = render_template(html_source, variables)
    except (TypeError, ValueError):
        return "template_variables_rejected"
    if message.get("text") != rendered_text or message.get("html") != rendered_html:
        return "template_body_mismatch"
    return None


def _addr_list(values, *, minimum):
    if not isinstance(values, list):
        raise ValueError("address list is missing")
    if len(values) < minimum:
        raise ValueError("address list is empty")
    return [addr_spec(item) for item in values]


def _body(value):
    if not isinstance(value, str) or value == "":
        raise ValueError("delivery field is empty")
    return value


def _token(value, label):
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ValueError(f"{label} is missing")
    return value
