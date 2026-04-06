import base64
import hashlib
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .canonical_json import canonical_json_bytes, derive_audit_id

def _now_utc_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _normalise_dim_map_int_keys(d: Dict[Any, Any]) -> Dict[str, Any]:
    # convert keys like 0,1,2 to "0","1","2"
    out: Dict[str, Any] = {}
    for k, v in d.items():
        out[str(k)] = v
    return out

def build_v1_payload(
    *,
    engine: str,
    engine_version: str,
    inputs_hash: str,
    max_dim: int,
    cell_counts: Dict[Any, int],
    boundary_squared_zero_verified: bool,
    thinness_verified: Optional[bool],
    betti: Dict[Any, int],
    torsion: Dict[Any, list],
    audit_id: Optional[str] = None,
    created_utc: Optional[str] = None,
    sign_with_private_pem: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_utc = created_utc or _now_utc_rfc3339()
    resolved_audit_id = audit_id if audit_id is not None else derive_audit_id(inputs_hash, resolved_utc)
    payload: Dict[str, Any] = {
        "schema_version": "audit_invariants.v1",
        "audit_id": resolved_audit_id,
        "created_utc": resolved_utc,
        "source": {
            "engine": engine,
            "engine_version": engine_version,
            "inputs_hash": inputs_hash,
        },
        "complex_summary": {
            "max_dim": int(max_dim),
            "cell_counts": _normalise_dim_map_int_keys(cell_counts),
            "boundary_squared_zero_verified": bool(boundary_squared_zero_verified),
        },
        "homology": {
            "betti": _normalise_dim_map_int_keys(betti),
            "torsion": _normalise_dim_map_int_keys(torsion),
        },
        "witnesses": {
            "cycles_optional": {"enabled": False, "encoding": "none", "data": None}
        },
        "advisories": {
            "structural_cavities": [],
            "torsion_parity_obstructions": [],
        },
        "integrity": {
            "payload_sha256": "",
            "signature_optional": None,
        },
    }

    if thinness_verified is not None:
        payload["complex_summary"]["thinness_verified"] = bool(thinness_verified)

    # canonical bytes are used for both the hash and the optional signature
    canon = canonical_json_bytes(payload)
    payload["integrity"]["payload_sha256"] = hashlib.sha256(canon).hexdigest()

    if sign_with_private_pem is not None:
        from .signing import sign_payload, public_pem_from_private_pem
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, load_pem_public_key,
        )
        sig_b64 = sign_payload(canon, sign_with_private_pem)
        public_pem = public_pem_from_private_pem(sign_with_private_pem)
        pub_key = load_pem_public_key(public_pem.encode("ascii"))
        pub_der_b64 = base64.b64encode(
            pub_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        ).decode("ascii")
        payload["integrity"]["signature_optional"] = {
            "scheme": "ed25519",
            "public_key_b64": pub_der_b64,
            "sig_b64": sig_b64,
        }

    return payload

def write_v1_payload(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
