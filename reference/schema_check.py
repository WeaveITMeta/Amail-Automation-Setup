"""Validate JSON against the small subset of JSON Schema used in this repo.

Unsupported keywords raise, so a schema cannot look checked when it is not.
"""

from __future__ import annotations

import re

_IGNORED = {"$schema", "$id", "title", "description", "default", "examples"}
_SUPPORTED = _IGNORED | {
    "type",
    "enum",
    "const",
    "pattern",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
}


def validate(instance, schema, path="$"):
    unknown = set(schema) - _SUPPORTED
    if unknown:
        raise ValueError(f"unsupported schema keywords at {path}: {sorted(unknown)}")
    errors = []
    expected = schema.get("type")
    if expected and not _type_ok(instance, expected):
        return [f"{path}: expected {expected}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: not in enum")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: pattern mismatch")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    if expected == "object" and isinstance(instance, dict):
        required = schema.get("required", [])
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key in required:
            if key not in instance:
                errors.append(f"{path}.{key}: required")
        for key, value in instance.items():
            child = f"{path}.{key}"
            if key in props:
                errors.extend(validate(value, props[key], child))
            elif additional is False:
                errors.append(f"{child}: additional property")
            elif isinstance(additional, dict):
                errors.extend(validate(value, additional, child))
    if expected == "array" and isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))
    return errors


def _type_ok(instance, expected):
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    raise ValueError(f"unsupported type {expected}")
