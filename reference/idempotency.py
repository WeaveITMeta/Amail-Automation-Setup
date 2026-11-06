"""Claim rules for append-only handled keys.

The store itself is not in this repository. A worker calls an atomic
create-if-absent on a durable store that survives workspace resets, then
honors the boolean that operation returns. Checking a local file first is
not the claim.
"""

from __future__ import annotations


def on_conditional_claim(*, created):
    """Return whether this wake may continue into parsing and drafting."""

    if created is True:
        return {
            "proceed": True,
            "outcome": "claimed",
            "next": "load_skill_then_read_woken_object",
        }
    if created is False:
        return {
            "proceed": False,
            "outcome": "duplicate_ignored",
            "next": "append_attempt_and_stop_before_read",
        }
    raise ValueError("conditional claim result must be a boolean")
