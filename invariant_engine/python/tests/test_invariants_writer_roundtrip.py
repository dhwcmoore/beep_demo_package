"""
test_invariants_writer_roundtrip.py

Verifies that the full write → read roundtrip is lossless:

1. Build a payload from the triangle_classical example.
2. Write it to a temporary JSON file with write_v1_payload.
3. Read the file back with json.load.
4. Assert that betti, torsion, and cell_counts are byte-for-byte identical.
5. Assert that the stored payload_sha256 re-validates against a fresh
   recomputation (the hash does not corrupt on serialisation).
6. Assert that all required top-level keys survive the roundtrip.
7. Verify that the manifest sidecar can be built from the written payload
   and carries the correct payload_sha256.
"""
import json
import os
import tempfile

import pytest

from examples import example_triangle_classical
from chain_complex import build_chain_complex
from homology import compute_homology
from export.invariants_writer import build_v1_payload, write_v1_payload
from export.canonical_json import payload_sha256_hex
from export.manifest import build_run_manifest_from_payload, write_run_manifest


# ── build the reference payload once ─────────────────────────────────────────

@pytest.fixture(scope="module")
def written_and_read():
    """
    Returns (original_payload, roundtripped_payload, tmp_path).
    Writes to a temp file and reads it back.
    """
    system = example_triangle_classical()
    cc = build_chain_complex(system)
    hom = compute_homology(cc)

    betti   = {str(k): hom[k].betti   for k in hom}
    torsion = {str(k): hom[k].torsion for k in hom}

    original = build_v1_payload(
        audit_id="roundtrip-test",
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

    with tempfile.NamedTemporaryFile(
        suffix=".json", mode="w", delete=False, encoding="utf-8"
    ) as f:
        tmp_path = f.name

    try:
        write_v1_payload(tmp_path, original)
        with open(tmp_path, encoding="utf-8") as f:
            roundtripped = json.load(f)
        yield original, roundtripped, tmp_path
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── top-level key survival ────────────────────────────────────────────────────

def test_required_keys_survive(written_and_read):
    _, rt, _ = written_and_read
    for key in ("schema_version", "audit_id", "created_utc", "source",
                "complex_summary", "homology", "integrity"):
        assert key in rt, f"missing key after roundtrip: {key}"


# ── betti numbers ─────────────────────────────────────────────────────────────

def test_betti_roundtrip(written_and_read):
    orig, rt, _ = written_and_read
    assert rt["homology"]["betti"] == orig["homology"]["betti"]


def test_betti_values_triangle(written_and_read):
    _, rt, _ = written_and_read
    assert rt["homology"]["betti"]["0"] == 1
    assert rt["homology"]["betti"]["1"] == 0
    assert rt["homology"]["betti"]["2"] == 0


# ── torsion ───────────────────────────────────────────────────────────────────

def test_torsion_roundtrip(written_and_read):
    orig, rt, _ = written_and_read
    assert rt["homology"]["torsion"] == orig["homology"]["torsion"]


def test_torsion_empty_triangle(written_and_read):
    _, rt, _ = written_and_read
    for dim, coeff in rt["homology"]["torsion"].items():
        assert coeff == [], f"unexpected torsion at dim {dim}"


# ── complex summary ───────────────────────────────────────────────────────────

def test_cell_counts_roundtrip(written_and_read):
    orig, rt, _ = written_and_read
    assert rt["complex_summary"]["cell_counts"] == orig["complex_summary"]["cell_counts"]


def test_max_dim_roundtrip(written_and_read):
    _, rt, _ = written_and_read
    assert rt["complex_summary"]["max_dim"] == 2


# ── integrity hash survives serialisation ─────────────────────────────────────

def test_stored_hash_survives(written_and_read):
    orig, rt, _ = written_and_read
    assert rt["integrity"]["payload_sha256"] == orig["integrity"]["payload_sha256"]


def test_hash_revalidates_after_roundtrip(written_and_read):
    """A fresh recomputation from the roundtripped doc must match the stored hash."""
    _, rt, _ = written_and_read
    stored = rt["integrity"]["payload_sha256"]
    assert payload_sha256_hex(rt) == stored


# ── manifest sidecar ──────────────────────────────────────────────────────────

def test_manifest_payload_sha256(written_and_read):
    orig, _, tmp_path = written_and_read
    manifest = build_run_manifest_from_payload(tmp_path, orig)
    assert manifest["payload_sha256"] == orig["integrity"]["payload_sha256"]


def test_manifest_required_keys(written_and_read):
    orig, _, tmp_path = written_and_read
    manifest = build_run_manifest_from_payload(tmp_path, orig)
    for key in ("manifest_version", "created_utc", "audit_id",
                "schema_version", "engine", "engine_version",
                "output_file", "payload_sha256"):
        assert key in manifest, f"missing manifest key: {key}"


def test_manifest_write_read(written_and_read):
    """Writing and re-reading the manifest preserves the payload_sha256."""
    orig, _, tmp_path = written_and_read
    manifest = build_run_manifest_from_payload(
        tmp_path, orig, created_utc="2026-01-01T00:00:00Z"
    )

    with tempfile.NamedTemporaryFile(
        suffix=".manifest.json", mode="w", delete=False, encoding="utf-8"
    ) as f:
        mf_path = f.name

    try:
        write_run_manifest(mf_path, manifest)
        with open(mf_path, encoding="utf-8") as f:
            read_back = json.load(f)
        assert read_back["payload_sha256"] == orig["integrity"]["payload_sha256"]
        assert read_back["manifest_version"] == "run_manifest.v1"
    finally:
        if os.path.exists(mf_path):
            os.unlink(mf_path)
