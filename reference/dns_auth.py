"""Explain SPF and DMARC TXT sets. This module does not query or publish DNS.

A placeholder mechanism and two DMARC records are permerrors. Verifying an
outbound inventory does not authorize this library to add an SES include or
to rewrite a record.
"""

from __future__ import annotations

import ipaddress


def spf_problems(txt_records):
    """Problem codes for the SPF records in one name's TXT set."""

    if not isinstance(txt_records, list) or any(not isinstance(item, str) for item in txt_records):
        return ["spf_unreadable"]
    records = [item.strip() for item in txt_records if item.strip().lower().startswith("v=spf1")]
    problems = []
    if not records:
        problems.append("spf_missing")
    if len(records) > 1:
        problems.append("spf_permerror_multiple")
    for record in records:
        problems.extend(_spf_record_problems(record))
    return problems


def dmarc_problems(txt_records):
    """Problem codes for the DMARC records at one _dmarc name.

    Two records are a permanent error even when both say p=none. An rua on
    only one of them does not choose a winner.
    """

    if not isinstance(txt_records, list) or any(not isinstance(item, str) for item in txt_records):
        return ["dmarc_unreadable"]
    records = [item for item in txt_records if _is_dmarc(item)]
    problems = []
    if not records:
        problems.append("dmarc_missing")
    if len(records) > 1:
        problems.append("dmarc_permanent_error_multiple")
    for record in records:
        if "p=" not in record.lower().replace(" ", ""):
            problems.append("dmarc_policy_missing")
    return problems


def ses_spf_change(txt_records, *, outbound_inventory_verified):
    """Refuse to rewrite SPF. Inventory is not a publish action.

    The returned record list is the input list. `mutate` is always false.
    """

    if not isinstance(txt_records, list):
        txt_records = []
    reason = "outbound_inventory_unverified"
    if outbound_inventory_verified is True:
        reason = "reference_does_not_publish_dns"
    return {"mutate": False, "reason": reason, "records": list(txt_records)}


def _spf_record_problems(record):
    problems = []
    for part in record.split()[1:]:
        mechanism = part.lstrip("+-?~")
        if mechanism.lower().startswith("ip4:"):
            body = mechanism.split(":", 1)[1]
            if "your_server_ip" in body.lower():
                problems.append("spf_placeholder_mechanism")
            ip_text = body.split("/", 1)[0]
            try:
                ipaddress.IPv4Address(ip_text)
            except ValueError:
                problems.append("spf_ip4_invalid")
    return problems


def _is_dmarc(record):
    if not isinstance(record, str):
        return False
    compact = "".join(record.split()).lower()
    return compact.startswith("v=dmarc1;") or compact == "v=dmarc1"
