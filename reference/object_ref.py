"""Resolve the raw MIME object from the wake, never from the message body."""

from __future__ import annotations


def object_reference(wake, configured_bucket):
    """Return the bucket and key the reader is allowed to fetch.

    `wake` is the trusted envelope from the active wake path. MIME headers
    and bodies are intentionally not inputs.
    """

    if not isinstance(wake, dict):
        raise ValueError("wake envelope is missing")
    if not isinstance(configured_bucket, str) or not configured_bucket:
        raise ValueError("configured bucket is missing")
    bucket = wake.get("bucket")
    key = wake.get("object_key")
    if bucket != configured_bucket:
        raise ValueError("wake bucket does not match the configured inbound bucket")
    if not isinstance(key, str) or not key or key.startswith("/") or key.endswith("/"):
        raise ValueError("wake object key is missing")
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("wake object key is unsafe")
    return {"bucket": bucket, "object_key": key, "access": "read_only"}
