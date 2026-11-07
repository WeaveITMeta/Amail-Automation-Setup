"""Header and sender checks that depend on the mail class.

Promotional bulk mail requires both RFC 8058 headers and proof that a DKIM
signature covers those header names. Customer support does not. One-to-one
and transactional mail do not become promotional because a rubric passed.
"""

from __future__ import annotations

from reference.sender_policy import MAIL_CLASSES, from_address_problem, postal_address_problem
from reference.unsubscribe import dkim_covers_one_click

_ONE_CLICK = "List-Unsubscribe=One-Click"


def delivery_blockers(message, *, action, sender_allowlist, verified_domain, postal_address=None):
    """Return problem codes. An empty list means this class may proceed to the gate."""

    if not isinstance(message, dict):
        return ["message_invalid"]
    mail_class = message.get("mail_class")
    if mail_class not in MAIL_CLASSES:
        return ["mail_class_invalid"]
    headers = message.get("headers")
    if not isinstance(headers, dict):
        return ["message_invalid"]
    problems = []
    sender = from_address_problem(
        message.get("from"),
        mail_class=mail_class,
        allowlist=sender_allowlist,
        verified_domain=verified_domain,
    )
    if sender:
        problems.append(sender)
    postal = postal_address_problem(mail_class, postal_address, message.get("from"))
    if postal and postal not in problems:
        problems.append(postal)
    problems.extend(_header_problems(mail_class, action, headers, message.get("dkim_signed_headers")))
    return problems


def _header_problems(mail_class, action, headers, signed_header_names):
    problems = []
    unsubscribe = headers.get("list_unsubscribe", "")
    unsubscribe_post = headers.get("list_unsubscribe_post", "")
    if not isinstance(unsubscribe, str) or not isinstance(unsubscribe_post, str):
        return ["unsubscribe_headers_invalid"]
    auto_submitted = headers.get("auto_submitted", "")
    if not isinstance(auto_submitted, str):
        return ["auto_submitted_invalid"]
    has_one_click = bool(unsubscribe.strip() or unsubscribe_post.strip())
    if mail_class == "promotional_bulk":
        if "<https://" not in unsubscribe.lower():
            problems.append("list_unsubscribe_missing")
        if unsubscribe_post != _ONE_CLICK:
            problems.append("list_unsubscribe_post_missing")
        if not dkim_covers_one_click(signed_header_names):
            problems.append("dkim_coverage_unproven")
        if auto_submitted == "auto-replied":
            problems.append("promotional_marked_as_reply")
        return problems
    if has_one_click:
        problems.append("one_click_not_for_this_class")
    if mail_class == "customer_support" and auto_submitted not in {"", "no"}:
        problems.append("support_reply_marked_automatic")
    if mail_class == "one_to_one" and action == "template_send" and auto_submitted != "auto-replied":
        problems.append("auto_submitted_required")
    return problems
