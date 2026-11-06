"""Check the exact message a reviewer would send.

Auto-send and human-approved send both use these checks. Exact template
equality is an additional requirement only for the automatic path.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_CID = re.compile(r"cid:", re.IGNORECASE)
_IMG = re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_BARE_URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_SECRET = re.compile(r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")


def rendered_failures(message, *, allow_hosts, required_assets):
    """Return a list of problems. An empty list means the render is send-ready."""

    failures = []
    if not isinstance(message, dict):
        return ["message_invalid"]
    html = message.get("html")
    text = message.get("text")
    headers = message.get("headers")
    if not isinstance(html, str) or not isinstance(text, str) or not isinstance(headers, dict):
        return ["message_invalid"]
    if _CID.search(html) or _CID.search(text):
        failures.append("cid_reference")
    if _SECRET.search(html) or _SECRET.search(text):
        failures.append("secret_pattern")
    if _luhn_hit(html) or _luhn_hit(text):
        failures.append("payment_number_pattern")

    urls = _IMG.findall(html)
    urls.extend(_BARE_URL.findall(html))
    urls.extend(_BARE_URL.findall(text))
    hosts = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            failures.append("asset_not_https")
            continue
        hosts.append(parsed.netloc.lower())
    allow = {host.lower() for host in allow_hosts}
    if any(host not in allow for host in hosts):
        failures.append("asset_host_not_allowed")

    required = list(required_assets)
    for asset in required:
        if asset not in html:
            failures.append("required_asset_missing")
            break
        parsed = urlparse(asset)
        if parsed.scheme != "https" or parsed.netloc.lower() not in allow:
            failures.append("required_asset_not_allowed")
            break

    in_reply_to = headers.get("in_reply_to")
    references = headers.get("references")
    if not isinstance(in_reply_to, str) or not in_reply_to.startswith("<") or not in_reply_to.endswith(">"):
        failures.append("missing_in_reply_to")
    if not isinstance(references, list) or not references:
        failures.append("missing_references")
    elif any(not isinstance(item, str) or not item.startswith("<") for item in references):
        failures.append("missing_references")
    elif isinstance(in_reply_to, str) and in_reply_to not in references:
        failures.append("references_omit_in_reply_to")
    return failures


def _luhn_hit(text):
    digits = []
    run = []
    for char in text:
        if char.isdigit():
            run.append(char)
        elif char in " -":
            if run:
                run.append(char)
        else:
            digits.append("".join(run))
            run = []
    digits.append("".join(run))
    for raw in digits:
        number = "".join(ch for ch in raw if ch.isdigit())
        if 13 <= len(number) <= 19 and _luhn(number):
            return True
    return False


def _luhn(number):
    total = 0
    reverse = number[::-1]
    for index, char in enumerate(reverse):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
