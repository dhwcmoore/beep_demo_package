import hashlib
from typing import Any

from veribound_core.canonical_json import canonicalise_json_bytes


def sha256_hex_for_object(obj: Any) -> str:
    canonical = canonicalise_json_bytes(obj)
    return hashlib.sha256(canonical).hexdigest()


def verify_sha256_hex(obj: Any, expected_hex: str) -> bool:
    actual = sha256_hex_for_object(obj)
    return actual == expected_hex