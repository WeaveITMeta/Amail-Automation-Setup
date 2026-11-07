"""Append-only suppression log consulted again before every send attempt.

The file is the reference contract: each lookup re-reads it, and each write
is flushed and fsynced before it returns. A second process, a second host, or
a disk that disappears with the worker is not covered. Point the path at an
operator store outside this repository. A skill-file instruction is not a
suppression record, and this class is not evidence that a live sender uses it.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from reference.binding import addr_spec

_REASONS = frozenset({"hard_bounce", "complaint", "unsubscribe", "opt_out"})
_ROOT = Path(__file__).resolve().parents[1]


class SuppressionLog:
    def __init__(self, path):
        if not isinstance(path, (str, Path)):
            raise ValueError("suppression path is missing")
        self.path = Path(path)
        try:
            self.path.resolve().relative_to(_ROOT)
        except ValueError:
            pass
        else:
            raise ValueError("suppression log must live outside the repository")
        self._lock = threading.Lock()

    def lookup(self, address):
        """Return the newest matching record, or None. Always re-reads the file."""

        normalized = addr_spec(address)
        with self._lock:
            found = None
            for record in self._read():
                if normalized in _record_addresses(record):
                    found = record
            return found

    def suppress(self, address, *, reason, source_id):
        """Record a suppression once. A second call for the same address is success."""

        normalized = addr_spec(address)
        if reason not in _REASONS:
            raise ValueError("suppression reason is not allowed")
        if not isinstance(source_id, str) or not source_id or any(char.isspace() for char in source_id):
            raise ValueError("suppression source id is missing")
        with self._lock:
            if any(normalized in _record_addresses(record) for record in self._read()):
                return "already_suppressed"
            self._append(
                {
                    "address": normalized,
                    "reason": reason,
                    "source_id": source_id,
                    "type": "suppression",
                }
            )
            return "suppressed"

    def apply_feedback(self, feedback_id, *, addresses, reason):
        """Claim a provider feedback id and suppress only on the first claim.

        A replay returns without reading the new address list into the log.
        The first claim wins, including a claim that suppresses nobody.
        """

        if not isinstance(feedback_id, str) or not feedback_id or any(char.isspace() for char in feedback_id):
            raise ValueError("feedback id is missing")
        if reason not in _REASONS | {"transient", "needs_review"}:
            raise ValueError("feedback reason is not allowed")
        if not isinstance(addresses, list):
            raise ValueError("feedback addresses are missing")
        normalized = [addr_spec(item) for item in addresses]
        if reason not in {"hard_bounce", "complaint"} and normalized:
            raise ValueError("this feedback reason cannot suppress")
        with self._lock:
            for record in self._read():
                if record.get("type") == "feedback" and record.get("feedback_id") == feedback_id:
                    return "replay"
            self._append(
                {
                    "addresses": normalized,
                    "feedback_id": feedback_id,
                    "reason": reason,
                    "type": "feedback",
                }
            )
            return "applied"

    def feedback_ids(self):
        with self._lock:
            return [record.get("feedback_id") for record in self._read() if record.get("type") == "feedback"]

    def _append(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def _read(self):
        if not self.path.is_file():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def recipients_suppressed(log, message):
    """True when any To, Cc, or Bcc address is already in the log."""

    if not isinstance(log, SuppressionLog) or not isinstance(message, dict):
        return True
    for key in ("to", "cc", "bcc"):
        values = message.get(key)
        if not isinstance(values, list):
            return True
        for item in values:
            if log.lookup(item) is not None:
                return True
    return False


def _record_addresses(record):
    if not isinstance(record, dict):
        return set()
    found = set()
    if isinstance(record.get("address"), str):
        found.add(record["address"])
    addresses = record.get("addresses")
    if isinstance(addresses, list):
        found.update(item for item in addresses if isinstance(item, str))
    return found
