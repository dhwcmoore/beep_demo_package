"""
test_fixture_invariants.py

Verifies homological invariants for two canonical non-trivial examples:

1. S¹ (circle) — ``example_loop_no_fill``
   H₀ = Z, H₁ = Z, H₂ = 0
   Betti: [1, 1, 0]   no torsion

2. RP² (real projective plane) — ``example_projective_plane``
   H₀ = Z, H₁ = Z/2  (torsion — invisible to free rank), H₂ = 0
   Betti: [1, 0, 0]   torsion[1] = [2]

Both are end-to-end tests: engine → chain complex → homology → build_v1_payload.
They also verify that the exported payload carries the correct invariants and
a self-consistent integrity hash.
"""
import pytest

from examples import example_loop_no_fill, example_projective_plane
from chain_complex import build_chain_complex
from homology import compute_homology
from export.invariants_writer import build_v1_payload
from export.canonical_json import payload_sha256_hex


# ── shared fixture builder ────────────────────────────────────────────────────

def _run(example_fn, audit_id: str):
    system = example_fn()
    cc = build_chain_complex(system)
    hom = compute_homology(cc)

    betti   = {str(k): hom[k].betti   for k in hom}
    torsion = {str(k): hom[k].torsion for k in hom}

    return build_v1_payload(
        audit_id=audit_id,
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


# ── S¹ (circle / loop_no_fill) ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def circle_payload():
    return _run(example_loop_no_fill, "test-circle")


def test_circle_schema_version(circle_payload):
    assert circle_payload["schema_version"] == "audit_invariants.v1"


def test_circle_betti_0(circle_payload):
    """S¹ is connected: b0 = 1."""
    assert circle_payload["homology"]["betti"]["0"] == 1


def test_circle_betti_1(circle_payload):
    """S¹ has one independent cycle: b1 = 1."""
    assert circle_payload["homology"]["betti"]["1"] == 1


def test_circle_betti_2(circle_payload):
    """S¹ is 1-dimensional: b2 = 0."""
    assert circle_payload["homology"]["betti"].get("2", 0) == 0


def test_circle_no_torsion(circle_payload):
    """S¹ has no torsion in any dimension."""
    for dim, coeff in circle_payload["homology"]["torsion"].items():
        assert coeff == [], f"unexpected torsion at dim {dim}: {coeff}"


def test_circle_max_dim(circle_payload):
    """loop_no_fill has only 0- and 1-cells: max_dim = 1."""
    assert circle_payload["complex_summary"]["max_dim"] == 1


def test_circle_cell_counts(circle_payload):
    """3 vertices, 3 edges."""
    cc = circle_payload["complex_summary"]["cell_counts"]
    assert cc["0"] == 3
    assert cc["1"] == 3


def test_circle_boundary_squared_zero(circle_payload):
    assert circle_payload["complex_summary"]["boundary_squared_zero_verified"] is True


def test_circle_hash_consistent(circle_payload):
    stored = circle_payload["integrity"]["payload_sha256"]
    assert payload_sha256_hex(circle_payload) == stored


# ── RP² (real projective plane) ───────────────────────────────────────────────

@pytest.fixture(scope="module")
def rp2_payload():
    return _run(example_projective_plane, "test-rp2")


def test_rp2_schema_version(rp2_payload):
    assert rp2_payload["schema_version"] == "audit_invariants.v1"


def test_rp2_betti_0(rp2_payload):
    """RP² is connected: b0 = 1."""
    assert rp2_payload["homology"]["betti"]["0"] == 1


def test_rp2_betti_1(rp2_payload):
    """RP² has no free H₁ (only torsion): b1 = 0."""
    assert rp2_payload["homology"]["betti"]["1"] == 0


def test_rp2_betti_2(rp2_payload):
    """RP² is non-orientable: b2 = 0."""
    assert rp2_payload["homology"]["betti"]["2"] == 0


def test_rp2_torsion_dim1(rp2_payload):
    """RP² has Z/2 torsion in H₁: torsion[1] = [2]."""
    assert rp2_payload["homology"]["torsion"]["1"] == [2], (
        f"expected [2], got {rp2_payload['homology']['torsion']['1']}"
    )


def test_rp2_torsion_dim0_empty(rp2_payload):
    """No torsion in H₀."""
    assert rp2_payload["homology"]["torsion"]["0"] == []


def test_rp2_torsion_dim2_empty(rp2_payload):
    """No torsion in H₂."""
    assert rp2_payload["homology"]["torsion"].get("2", []) == []


def test_rp2_max_dim(rp2_payload):
    """projective_plane has cells up to dim 2."""
    assert rp2_payload["complex_summary"]["max_dim"] == 2


def test_rp2_cell_counts(rp2_payload):
    """2 vertices, 3 edges, 2 faces."""
    cc = rp2_payload["complex_summary"]["cell_counts"]
    assert cc["0"] == 2
    assert cc["1"] == 3
    assert cc["2"] == 2


def test_rp2_boundary_squared_zero(rp2_payload):
    assert rp2_payload["complex_summary"]["boundary_squared_zero_verified"] is True


def test_rp2_hash_consistent(rp2_payload):
    stored = rp2_payload["integrity"]["payload_sha256"]
    assert payload_sha256_hex(rp2_payload) == stored
