"""Render fixed templates. Inbound mail cannot add placeholders."""

from __future__ import annotations

import re

ALLOWED_PLACEHOLDERS = frozenset({"organization", "role_display"})
_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def render_template(source, variables):
    """Substitute trusted variables and reject any other placeholder."""

    if not isinstance(source, str) or not isinstance(variables, dict):
        raise ValueError("template inputs are invalid")
    unknown_vars = set(variables) - ALLOWED_PLACEHOLDERS
    if unknown_vars:
        raise ValueError("template variables are limited to organization and role_display")
    found = set(_PLACEHOLDER.findall(source))
    if not found <= ALLOWED_PLACEHOLDERS:
        raise ValueError("template contains an unapproved placeholder")
    missing = found - set(variables)
    if missing:
        raise ValueError("template variable is missing")
    for key, value in variables.items():
        if not isinstance(value, str) or not value or "\n" in value or "<" in value or ">" in value:
            raise ValueError("template variable is not plain text")

    def replace(match):
        return variables[match.group(1)]

    return _PLACEHOLDER.sub(replace, source)
