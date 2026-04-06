import json
import hashlib
from typing import Any, Dict


def derive_audit_id(inputs_hash: str, created_utc: str) -> str:
    """Deterministic audit identifier: SHA-256 of '<inputs_hash>:<created_utc>'.

    Because both inputs are already present in the payload (source.inputs_hash
    and created_utc), a client can independently recompute this value and
    confirm that an audit from any point in time has not been tampered with.
    """
    raw = f"{inputs_hash}:{created_utc}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _canonicalise(obj: Any) -> Any:
    if isinstance(obj, dict):
        # remove integrity field entirely before hashing
        obj2 = {k: _canonicalise(v) for k, v in obj.items() if k != "integrity"}
        return {k: obj2[k] for k in sorted(obj2.keys())}
    if isinstance(obj, list):
        return [_canonicalise(v) for v in obj]
    return obj

def canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    canon = _canonicalise(payload)
    # Minimal JSON, stable ordering
    s = json.dumps(canon, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return s.encode("utf-8")

def payload_sha256_hex(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
