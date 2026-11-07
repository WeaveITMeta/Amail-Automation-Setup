"""Retry caps for work that has not yet been handed to the provider.

A claimed send key is never an automatic retry. Transient errors may be
retried only before the claim, and only under the attempt cap. Suppression,
authentication failure, and permanent provider results do not retry.
"""

from __future__ import annotations

TRANSIENT_ERRORS = frozenset({"throttle", "timeout", "unavailable"})
PERMANENT_ERRORS = frozenset(
    {"rejected", "suppressed", "hard_bounce", "complaint", "unauthenticated", "malformed", "stale", "replay"}
)
MAX_ATTEMPT_CAP = 3


def transient_attempt_cap(policy):
    """Return the policy cap, or None when it is missing or above the ceiling."""

    if not isinstance(policy, dict):
        return None
    auto = policy.get("auto_reply")
    if not isinstance(auto, dict):
        return None
    limits = auto.get("rate_limits")
    if not isinstance(limits, dict):
        return None
    cap = limits.get("max_transient_send_attempts")
    if isinstance(cap, bool) or not isinstance(cap, int) or not 1 <= cap <= MAX_ATTEMPT_CAP:
        return None
    return cap


def attempt_allowed(policy, send_attempt):
    cap = transient_attempt_cap(policy)
    if cap is None:
        return False
    if isinstance(send_attempt, bool) or not isinstance(send_attempt, int):
        return False
    return 1 <= send_attempt <= cap


def retry_disposition(*, phase, error, attempt, cap, suppressed):
    """Say whether another try is allowed. After the claim, the answer is no."""

    if suppressed:
        return "do_not_send"
    if phase != "before_claim":
        return "do_not_retry"
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1 or cap > MAX_ATTEMPT_CAP:
        return "do_not_retry"
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        return "do_not_retry"
    if error in PERMANENT_ERRORS or error is None:
        return "do_not_retry"
    if error in TRANSIENT_ERRORS and attempt < cap:
        return "retry_before_claim"
    return "do_not_retry"
