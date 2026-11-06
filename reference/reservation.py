"""In-process reservation ledger for a single send attempt.

This is a reference for the atomic transitions. It is not a durable database
and it does not survive a process restart. A deployment must put the same
transitions in a store that outlives the sender. This module never calls SES.

States for one send key:

- absent: no claim
- handoff_started: this process won the claim and may call the provider once
- sent: the provider accepted the message
- ambiguous: the outcome is unknown, including a crash after the claim

There is no transition back to absent. A second claim, a restart that still
has the row, and an ambiguous result all refuse another send. Losing the
ledger on restart is not a retry mechanism. It is a gap the operator's store
has to close. This class will not invent that store.
"""

from __future__ import annotations

import threading

_DIGEST = "sha256:"


class ReservationLedger:
    def __init__(self):
        self._lock = threading.Lock()
        self._rows = {}

    def claim_handoff(self, send_key, payload_sha256):
        """Atomically move an absent key to handoff_started.

        Returns True for exactly one caller. Concurrent callers and every
        later call receive False.
        """

        if not isinstance(send_key, str) or not send_key or any(char.isspace() for char in send_key):
            return False
        if not isinstance(payload_sha256, str) or not payload_sha256.startswith(_DIGEST) or len(payload_sha256) != 71:
            return False
        with self._lock:
            if send_key in self._rows:
                return False
            self._rows[send_key] = {
                "state": "handoff_started",
                "payload_sha256": payload_sha256,
            }
            return True

    def state(self, send_key):
        with self._lock:
            row = self._rows.get(send_key)
            return None if row is None else row["state"]

    def mark_sent(self, send_key, provider_message_id):
        """Record a provider acceptance. This does not authorize another send."""

        if not isinstance(provider_message_id, str) or not provider_message_id:
            return False
        return self._move(send_key, "handoff_started", "sent", provider_message_id)

    def mark_ambiguous(self, send_key):
        """Record an unknown outcome. Do not send this key again."""

        return self._move(send_key, "handoff_started", "ambiguous", None)

    def _move(self, send_key, source, target, provider_message_id):
        with self._lock:
            row = self._rows.get(send_key)
            if row is None or row["state"] != source:
                return False
            row["state"] = target
            if provider_message_id is not None:
                row["provider_message_id"] = provider_message_id
            return True
