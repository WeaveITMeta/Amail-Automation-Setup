"""Restrict the outbound From address. Display names are not identities."""

from __future__ import annotations

from reference.binding import addr_spec

MAIL_CLASSES = frozenset({"transactional", "customer_support", "one_to_one", "promotional_bulk"})
_NEVER_FROM = frozenset({"mailer-daemon", "postmaster", "mailerdaemon"})
_NOT_REPLYABLE = frozenset({"noreply", "no-reply", "donotreply", "do-not-reply", "bounce", "bounces"})


def from_address_problem(address, *, mail_class, allowlist, verified_domain):
    """Return a problem code, or None when this From address may be used.

    The allowlist is per mail class. Customer support and one-to-one mail
    cannot use a no-reply local part. A street address is not an addr-spec
    and cannot be the sender identity.
    """

    if mail_class not in MAIL_CLASSES:
        return "mail_class_invalid"
    if not isinstance(verified_domain, str) or not verified_domain or "@" in verified_domain:
        return "from_domain_unverified"
    if not isinstance(allowlist, dict):
        return "sender_allowlist_missing"
    permitted = allowlist.get(mail_class)
    if not isinstance(permitted, list) or not permitted:
        return "sender_allowlist_missing"
    try:
        normalized = addr_spec(address)
        allowed = {addr_spec(item) for item in permitted}
    except (TypeError, ValueError):
        return "from_not_allowlisted"
    domain = normalized.split("@", 1)[1]
    if domain != verified_domain.strip().lower():
        return "from_domain_unverified"
    local = normalized.split("@", 1)[0]
    if local in _NEVER_FROM:
        return "from_role_reserved"
    if mail_class in {"customer_support", "one_to_one"} and local in _NOT_REPLYABLE:
        return "noreply_from_not_allowed"
    if normalized not in allowed:
        return "from_not_allowlisted"
    return None


def postal_address_problem(mail_class, postal_address, from_address):
    """Commercial bulk mail needs an operator postal address. It is not the From.

    Other classes do not receive a stand-in address from this library.
    A missing commercial address is a problem. A present address on support
    mail is not copied into the sender identity.
    """

    if mail_class != "promotional_bulk":
        return None
    if not isinstance(postal_address, str):
        return "postal_address_missing"
    text = " ".join(postal_address.split())
    if len(text) < 10 or "@" in text or "\n" in postal_address:
        return "postal_address_missing"
    try:
        identity = addr_spec(from_address)
    except (TypeError, ValueError):
        return "from_not_allowlisted"
    if text.lower() == identity:
        return "postal_address_is_not_a_from_identity"
    return None
