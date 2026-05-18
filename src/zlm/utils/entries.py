from __future__ import annotations

from typing import Any, cast

import orjson


def validate_entry(entry: object) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise TypeError("entry must be a dict")

    typed_entry = cast(dict[str, Any], entry)

    if "type" not in typed_entry:
        raise ValueError("entry must contain a 'type' key")

    if "body" not in typed_entry:
        raise ValueError("entry must contain a 'body' key")

    if not isinstance(typed_entry["type"], str):
        raise TypeError("entry['type'] must be a string")

    return {"type": typed_entry["type"], "body": typed_entry["body"]}


def serialize_entry(entry: object) -> bytes:
    return orjson.dumps(validate_entry(entry))


def deserialize_entry(payload: bytes) -> dict[str, Any]:
    decoded = orjson.loads(payload)
    return validate_entry(decoded)