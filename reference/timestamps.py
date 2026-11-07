"""UTC timestamp parsing for replay windows. No network."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_utc(value):
    """Parse an RFC 3339 timestamp. Naive values are rejected."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp missing")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp needs a timezone")
    return parsed.astimezone(timezone.utc)


def age_problem(stamp, now, *, max_age_seconds, skew_seconds):
    """Return a problem code, or None when the stamp is inside the window."""

    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("clock is missing a timezone")
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int) or max_age_seconds < 1:
        raise ValueError("max age is invalid")
    if isinstance(skew_seconds, bool) or not isinstance(skew_seconds, int) or skew_seconds < 0:
        raise ValueError("skew is invalid")
    delta = (now - stamp).total_seconds()
    if delta < -skew_seconds:
        return "timestamp_in_future"
    if delta > max_age_seconds:
        return "timestamp_stale"
    return None
