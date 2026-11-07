"""RFC 8058 one-click unsubscribe for promotional bulk mail.

GET and HEAD do not change suppression state. The one-click action is an
HTTPS POST whose body is List-Unsubscribe=One-Click. The POST is rejected
when it depends on a cookie, an Authorization header, or a login. A second
POST for the same recipient is a success and does not create a second row.

This module does not open a socket and it is not a deployed endpoint.
Customer-support and other one-to-one replies do not use these headers.
"""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl, urlparse

from reference.binding import addr_spec
from reference.suppression import SuppressionLog

_ONE_CLICK = "List-Unsubscribe=One-Click"


def one_click_token(secret, recipient, list_id):
    """Opaque token for one recipient on one list. The secret stays with the operator."""

    if not isinstance(secret, (bytes, bytearray)) or not secret:
        raise ValueError("unsubscribe secret is missing")
    if not isinstance(list_id, str) or not list_id or any(char.isspace() for char in list_id):
        raise ValueError("list id is missing")
    material = addr_spec(recipient) + "\n" + list_id
    return hmac.new(bytes(secret), material.encode("utf-8"), hashlib.sha256).hexdigest()


def list_unsubscribe_headers(*, https_uri, mailto_uri=None):
    """Build the two promotional headers. The HTTPS URI is required."""

    if not _https_uri(https_uri):
        raise ValueError("one-click URI must be https")
    values = [f"<{https_uri}>"]
    if mailto_uri is not None:
        if not isinstance(mailto_uri, str) or not mailto_uri.lower().startswith("mailto:"):
            raise ValueError("optional unsubscribe URI must be mailto")
        values.append(f"<{mailto_uri}>")
    return {
        "list_unsubscribe": ", ".join(values),
        "list_unsubscribe_post": _ONE_CLICK,
    }


def dkim_covers_one_click(signed_header_names):
    """True when the DKIM h= list includes both one-click header field names.

    This does not compute a signature. A missing list is not coverage.
    """

    if not isinstance(signed_header_names, list) or not signed_header_names:
        return False
    if any(not isinstance(item, str) for item in signed_header_names):
        return False
    names = {item.strip().lower() for item in signed_header_names}
    return "list-unsubscribe" in names and "list-unsubscribe-post" in names


def decide_one_click(request, log, *, secret):
    """Apply a one-click request. GET never suppresses, including with a valid token."""

    if not isinstance(log, SuppressionLog):
        raise ValueError("suppression log is missing")
    if not isinstance(request, dict):
        return _result("rejected", "request_invalid", False)
    method = str(request.get("method") or "").strip().upper()
    if method in {"GET", "HEAD"}:
        return _result("confirmation_only", "get_does_not_suppress", False)
    if method != "POST":
        return _result("rejected", "method_not_post", False)
    if request.get("https") is not True or not _https_uri(request.get("uri")):
        return _result("rejected", "https_required", False)
    if _present(request.get("authorization")) or _present(request.get("cookie")):
        return _result("rejected", "login_or_cookie_not_allowed", False)
    if not _one_click_body(request.get("content_type"), request.get("body")):
        return _result("rejected", "body_not_one_click", False)
    try:
        expected = one_click_token(secret, request.get("recipient"), request.get("list_id"))
        presented = request.get("token")
        matches = isinstance(presented, str) and hmac.compare_digest(expected, presented)
    except (TypeError, ValueError):
        return _result("rejected", "token_rejected", False)
    if not matches:
        return _result("rejected", "token_rejected", False)
    outcome = log.suppress(
        request.get("recipient"),
        reason="unsubscribe",
        source_id="unsubscribe:" + addr_spec(request.get("recipient")) + ":" + str(request.get("list_id")),
    )
    if outcome == "already_suppressed":
        return _result("already_suppressed", "idempotent_post", False)
    return _result("suppressed", "one_click_post", True)


def _result(status, reason, wrote):
    return {"effect": "suppress" if wrote else "none", "reason": reason, "status": status, "wrote": wrote}


def _present(value):
    return isinstance(value, str) and value.strip() != ""


def _https_uri(value):
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None


def _one_click_body(content_type, body):
    if not isinstance(content_type, str) or not isinstance(body, str):
        return False
    base = content_type.split(";", 1)[0].strip().lower()
    if base == "application/x-www-form-urlencoded":
        pairs = parse_qsl(body, keep_blank_values=True)
        return any(key == "List-Unsubscribe" and value == "One-Click" for key, value in pairs)
    if base == "multipart/form-data":
        marker = 'name="List-Unsubscribe"'
        return marker in body and "One-Click" in body and "Content-Disposition: form-data" in body
    return False
