"""
test_exporter_matches_invariants.py

Verifies that the export pipeline (build_v1_payload) produces a payload
whose homological values agree with those returned by the engine for the
canonical triangle_classical example.

This is the "self-certification" test: the Python side asserts that what
it writes to JSON matches what it computed.
"""
import sys
import os
import json
import pytest

from examples import example_triangle_classical
from chain_complex import build_chain_complex
from homology import compute_homology
from export.canonical_json import payload_sha256_hex
from export.invariants_writer import build_v1_payload


# ── build the reference data once ────────────────────────────────────────────

@pytest.fixture(scope="module")
def triangle_payload():
    system = example_triangle_classical()
    cc = build_chain_complex(system)
    hom = compute_homology(cc)

    betti  = {str(k): hom[k].betti  for k in hom}
    torsion = {str(k): hom[k].torsion for k in hom}

    return build_v1_payload(
        audit_id="test-triangle",
        engine="test",
        engine_version="0.0.0",
        inputs_hash="0" * 64,
        max_dim=int(cc.max_dim),
        cell_counts={k: cc.rank(k) for k in range(cc.max_dim + 1)},
        boundary_squared_zero_verified=bool(cc.is_valid),
        thinness_verified=None,
        betti=betti,
        torsion=torsion,
        created_utc="2026-01-01T00:00:00Z",
    )


# ── schema envelope ───────────────────────────────────────────────────────────

def test_schema_version(triangle_payload):
    assert triangle_payload["schema_version"] == "audit_invariants.v1"


def test_audit_id_present(triangle_payload):
    assert triangle_payload["audit_id"] == "test-triangle"


def test_required_top_level_keys(triangle_payload):
    for key in ("schema_version", "audit_id", "created_utc", "source",
                "complex_summary", "homology", "integrity"):
        assert key in triangle_payload, f"missing key: {key}"


# ── homology values match the engine ─────────────────────────────────────────

def test_betti_0_contractible(triangle_payload):
    """Triangle is contractible: b0=1."""
    assert triangle_payload["homology"]["betti"]["0"] == 1


def test_betti_1_contractible(triangle_payload):
    """Triangle is contractible: b1=0."""
    assert triangle_payload["homology"]["betti"]["1"] == 0


def test_betti_2_contractible(triangle_payload):
    """Triangle is contractible: b2=0."""
    assert triangle_payload["homology"]["betti"]["2"] == 0


def test_torsion_all_empty(triangle_payload):
    """Classical triangle has no torsion."""
    for dim, coeff in triangle_payload["homology"]["torsion"].items():
        assert coeff == [], f"expected no torsion at dim {dim}, got {coeff}"


# ── complex summary ───────────────────────────────────────────────────────────

def test_complex_summary_max_dim(triangle_payload):
    assert triangle_payload["complex_summary"]["max_dim"] == 2


def test_complex_summary_cell_counts(triangle_payload):
    cc = triangle_payload["complex_summary"]["cell_counts"]
    # triangle: 3 vertices, 3 edges, 1 face
    assert cc["0"] == 3
    assert cc["1"] == 3
    assert cc["2"] == 1


def test_boundary_squared_zero_verified(triangle_payload):
    assert triangle_payload["complex_summary"]["boundary_squared_zero_verified"] is True


# ── integrity ─────────────────────────────────────────────────────────────────

def test_integrity_hash_is_64_hex(triangle_payload):
    h = triangle_payload["integrity"]["payload_sha256"]
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_integrity_hash_is_correct(triangle_payload):
    """The stored hash must match a fresh recomputation."""
    stored = triangle_payload["integrity"]["payload_sha256"]
    recomputed = payload_sha256_hex(triangle_payload)
    assert recomputed == stored


def test_integrity_hash_changes_on_mutation(triangle_payload):
    """Mutating a payload field after export must invalidate the stored hash."""
    import copy
    mutated = copy.deepcopy(triangle_payload)
    mutated["audit_id"] = "tampered"
    assert payload_sha256_hex(mutated) != triangle_payload["integrity"]["payload_sha256"]
