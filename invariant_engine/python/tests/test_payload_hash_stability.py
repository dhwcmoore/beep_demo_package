"""
test_payload_hash_stability.py

Verifies that the canonical JSON hash is:
1. Deterministic — same input always produces the same digest.
2. Key-order-independent — dict key order does not affect the digest.
3. Sensitive to value changes — mutating any field changes the digest.
4. Sensitive to field additions — adding a field changes the digest.
5. Integrity-field-excluded — the `integrity` block is NOT part of the hash.
6. Consistent with the stored hash in both fixture files.
"""
import json
import copy
import os
import pytest

from export.canonical_json import payload_sha256_hex, canonical_json_bytes, derive_audit_id
from export.invariants_writer import build_v1_payload

_HERE = os.path.dirname(__file__)
_SCHEMAS_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "schemas"))
_EXAMPLE_PATH   = os.path.join(_SCHEMAS_DIR, "audit_invariants.v1.example.json")
_GENERATED_PATH = os.path.join(_SCHEMAS_DIR, "audit_invariants.v1.generated.json")


# ── minimal valid payload for unit tests ─────────────────────────────────────

def _minimal_payload(betti=None, torsion=None):
    return {
        "schema_version": "audit_invariants.v1",
        "audit_id": "test-unit",
        "created_utc": "2026-01-01T00:00:00Z",
        "source": {
            "engine": "test",
            "engine_version": "0.0.0",
            "inputs_hash": "a" * 64,
        },
        "complex_summary": {
            "max_dim": 1,
            "cell_counts": {"0": 2, "1": 1},
            "boundary_squared_zero_verified": True,
        },
        "homology": {
            "betti":   betti   or {"0": 1, "1": 0},
            "torsion": torsion or {"0": [], "1": []},
        },
        "integrity": {
            "payload_sha256": "",
            "signature_optional": None,
        },
    }


# ── determinism ───────────────────────────────────────────────────────────────

def test_deterministic():
    p = _minimal_payload()
    assert payload_sha256_hex(p) == payload_sha256_hex(p)
    assert payload_sha256_hex(copy.deepcopy(p)) == payload_sha256_hex(p)


def test_key_order_independent():
    p1 = _minimal_payload()
    # Reconstruct with keys in a different insertion order
    p2 = {
        "integrity": p1["integrity"],
        "homology": p1["homology"],
        "audit_id": p1["audit_id"],
        "schema_version": p1["schema_version"],
        "source": p1["source"],
        "complex_summary": p1["complex_summary"],
        "created_utc": p1["created_utc"],
    }
    assert payload_sha256_hex(p1) == payload_sha256_hex(p2)


# ── sensitivity ───────────────────────────────────────────────────────────────

def test_sensitive_to_betti_change():
    p_orig = _minimal_payload(betti={"0": 1, "1": 0})
    p_mut  = _minimal_payload(betti={"0": 1, "1": 1})
    assert payload_sha256_hex(p_orig) != payload_sha256_hex(p_mut)


def test_sensitive_to_new_field():
    p = _minimal_payload()
    p_extra = copy.deepcopy(p)
    p_extra["extra_top_level"] = "added"
    assert payload_sha256_hex(p) != payload_sha256_hex(p_extra)


def test_sensitive_to_audit_id_change():
    p1 = _minimal_payload()
    p2 = copy.deepcopy(p1)
    p2["audit_id"] = "different-id"
    assert payload_sha256_hex(p1) != payload_sha256_hex(p2)


# ── integrity field excluded ──────────────────────────────────────────────────

def test_integrity_field_excluded():
    """Changing the value inside 'integrity' must NOT change the hash."""
    p1 = _minimal_payload()
    p2 = copy.deepcopy(p1)
    p2["integrity"]["payload_sha256"] = "b" * 64
    p2["integrity"]["signature_optional"] = {"some": "sig"}
    assert payload_sha256_hex(p1) == payload_sha256_hex(p2)


def test_integrity_key_entirely_absent_same_hash():
    """A payload without the integrity key at all should hash identically."""
    p = _minimal_payload()
    p_no_integrity = {k: v for k, v in p.items() if k != "integrity"}
    assert payload_sha256_hex(p) == payload_sha256_hex(p_no_integrity)


# ── fixture files match stored hashes ────────────────────────────────────────

def test_example_stored_hash_correct():
    with open(_EXAMPLE_PATH) as f:
        doc = json.load(f)
    stored = doc["integrity"]["payload_sha256"]
    recomputed = payload_sha256_hex(doc)
    assert recomputed == stored, (
        f"example fixture hash mismatch:\n  stored:     {stored}\n  recomputed: {recomputed}"
    )


def test_generated_stored_hash_correct():
    with open(_GENERATED_PATH) as f:
        doc = json.load(f)
    stored = doc["integrity"]["payload_sha256"]
    recomputed = payload_sha256_hex(doc)
    assert recomputed == stored, (
        f"generated fixture hash mismatch:\n  stored:     {stored}\n  recomputed: {recomputed}"
    )


# ── derived audit_id determinism ─────────────────────────────────────────────

def test_derive_audit_id_deterministic():
    """Same inputs → same audit_id, every time."""
    ih = "a" * 64
    ts = "2026-01-01T00:00:00Z"
    assert derive_audit_id(ih, ts) == derive_audit_id(ih, ts)


def test_derive_audit_id_sensitive_to_inputs_hash():
    """Different inputs_hash → different audit_id."""
    ts = "2026-01-01T00:00:00Z"
    assert derive_audit_id("a" * 64, ts) != derive_audit_id("b" * 64, ts)


def test_derive_audit_id_sensitive_to_timestamp():
    """Different created_utc → different audit_id."""
    ih = "a" * 64
    assert derive_audit_id(ih, "2026-01-01T00:00:00Z") != derive_audit_id(ih, "2026-06-01T00:00:00Z")


def test_derive_audit_id_is_64_char_hex():
    """Derived id is a lowercase 64-character hex string (SHA-256)."""
    aid = derive_audit_id("c" * 64, "2026-01-01T00:00:00Z")
    assert len(aid) == 64
    assert all(c in "0123456789abcdef" for c in aid)


def test_build_v1_payload_derives_audit_id_when_omitted():
    """build_v1_payload without audit_id sets a deterministic 64-char hex id."""
    ih = "d" * 64
    ts = "2026-03-04T00:00:00Z"
    p1 = build_v1_payload(
        engine="test", engine_version="0.0.0", inputs_hash=ih,
        max_dim=1, cell_counts={"0": 2, "1": 1},
        boundary_squared_zero_verified=True, thinness_verified=None,
        betti={"0": 1}, torsion={"0": []},
        created_utc=ts,
    )
    p2 = build_v1_payload(
        engine="test", engine_version="0.0.0", inputs_hash=ih,
        max_dim=1, cell_counts={"0": 2, "1": 1},
        boundary_squared_zero_verified=True, thinness_verified=None,
        betti={"0": 1}, torsion={"0": []},
        created_utc=ts,
    )
    assert p1["audit_id"] == p2["audit_id"]
    assert p1["audit_id"] == derive_audit_id(ih, ts)
    assert len(p1["audit_id"]) == 64


# ── canonical bytes are valid UTF-8 JSON ─────────────────────────────────────

def test_canonical_bytes_are_valid_json():
    p = _minimal_payload()
    raw = canonical_json_bytes(p)
    parsed = json.loads(raw.decode("utf-8"))
    assert "integrity" not in parsed
    assert "schema_version" in parsed
