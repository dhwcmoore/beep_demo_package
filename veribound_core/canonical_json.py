import json
from typing import Any


def _normalise(obj: Any) -> Any:
    """
    Recursively normalise Python objects into a form suitable for deterministic JSON.

    Rules:
    - dict keys sorted later by json.dumps(sort_keys=True)
    - lists preserved in order
    - tuples converted to lists
    - booleans / None / ints / strings preserved
    - floats rendered by Python's JSON encoder
    """
    if isinstance(obj, dict):
        return {str(k): _normalise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalise(v) for v in obj]
    if isinstance(obj, tuple):
        return [_normalise(v) for v in obj]
    return obj


def canonicalise_json_bytes(obj: Any) -> bytes:
    """
    Deterministically serialise JSON-compatible data to UTF-8 bytes.
    """
    normalised = _normalise(obj)
    text = json.dumps(
        normalised,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return text.encode("utf-8")


def canonicalise_json_text(obj: Any) -> str:
    return canonicalise_json_bytes(obj).decode("utf-8")