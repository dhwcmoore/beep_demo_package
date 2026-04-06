#!/usr/bin/env python3
"""
bridge/test_bridge_scenarios.py

Python-level regression suite for the BEEP → LoopAudit bridge.

Tests three things:

  1. Unit tests for the pure transformation functions in export_loopaudit_payload
     (compatibility_status, advisory extraction, transition building).

  2. Structural validation of the four bridge payload fixtures (A–D),
     asserting schema_version, field presence, and internal consistency.

  3. Scenario classification: given the four fixtures, check that each one
     has the expected obstruction signature using the same logic the OCaml
     audit runner applies — implemented here as a pure-Python mirror of
     beep_bridge_mapping.ml so the two sides can be diffed if they diverge.

The Python mirror is intentionally kept minimal and close to the OCaml source
so that any divergence between the two implementations is immediately visible.

Usage:
    python3 bridge/test_bridge_scenarios.py
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Import the functions under test from the exporter
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))
from bridge.export_loopaudit_payload import (
    _compatibility_status,
    extract_per_stage_advisories,
    build_derived_transitions,
    build_regions,
)


# ---------------------------------------------------------------------------
# Python mirror of the OCaml audit logic
# (beep_bridge_mapping.ml, expressed in Python for cross-checking)
# ---------------------------------------------------------------------------

@dataclass
class Cert:
    b0: int
    b1: int
    advisories: list[str] = field(default_factory=list)

@dataclass
class Section:
    region: str
    system: str
    cert: Cert

@dataclass
class Mismatch:
    src_region: str
    dst_region: str
    expected_cert: Cert
    observed_cert: Cert
    theorems_fired: list[str]

@dataclass
class Triple:
    region_a: str
    region_b: str
    region_c: str
    baseline_cert: Cert
    observed_b: Cert
    observed_c: Cert
    failure_modes: list[str]


def _expected_transport(sections: list[Section], transitions: list[dict], src: Section) -> Cert:
    t = next((t for t in transitions if t["from_region"] == src.region), None)
    if t is None:
        return src.cert
    status = t["compatibility_status"]
    if status == "coherent":
        return src.cert
    elif status == "ring_broken":
        return Cert(b0=src.cert.b0, b1=0)
    elif status == "partitioned":
        b0_after = t["delta"]["b0"][1]
        return Cert(b0=b0_after, b1=src.cert.b1)
    elif status == "ring_broken_and_partitioned":
        b0_after = t["delta"]["b0"][1]
        return Cert(b0=b0_after, b1=0)
    else:
        return src.cert  # unknown: conservative preserve


def _check_ring_loss(baseline: Cert, observed: Cert) -> bool:
    return baseline.b1 > 0 and observed.b1 == 0


def _check_partition(baseline: Cert, observed: Cert) -> bool:
    return observed.b0 > baseline.b0


def _check_obstruction_lift(expected: Cert, observed: Cert) -> bool:
    return expected.b0 != observed.b0 or expected.b1 != observed.b1


def compute_mismatches(sections: list[Section], transitions: list[dict]) -> list[Mismatch]:
    if len(sections) < 2:
        return []
    baseline_cert = sections[0].cert
    mismatches = []
    for i in range(1, len(sections)):
        dst = sections[i]
        src = sections[i - 1]
        expected = _expected_transport(sections, transitions, src)
        observed = dst.cert
        fired = []
        if _check_ring_loss(baseline_cert, observed):
            fired.append("ring_loss")
        if _check_partition(baseline_cert, observed):
            fired.append("partition")
        if _check_obstruction_lift(expected, observed):
            fired.append("obstruction_lift")
        if fired:
            mismatches.append(Mismatch(
                src_region=src.region,
                dst_region=dst.region,
                expected_cert=expected,
                observed_cert=observed,
                theorems_fired=fired,
            ))
    return mismatches


def build_triples(baseline: Section, mismatches: list[Mismatch]) -> list[Triple]:
    if not mismatches:
        return []
    if len(mismatches) == 1:
        m = mismatches[0]
        return [Triple(
            region_a=baseline.region,
            region_b=m.dst_region,
            region_c=m.dst_region,
            baseline_cert=baseline.cert,
            observed_b=m.observed_cert,
            observed_c=m.observed_cert,
            failure_modes=sorted(set(m.theorems_fired)),
        )]
    triples = []
    for i in range(len(mismatches) - 1):
        m1, m2 = mismatches[i], mismatches[i + 1]
        modes = sorted(set(m1.theorems_fired + m2.theorems_fired))
        triples.append(Triple(
            region_a=baseline.region,
            region_b=m1.dst_region,
            region_c=m2.dst_region,
            baseline_cert=baseline.cert,
            observed_b=m1.observed_cert,
            observed_c=m2.observed_cert,
            failure_modes=modes,
        ))
    return triples


def audit_payload(payload: dict) -> dict:
    """Run the Python-mirror audit. Returns a dict matching the OCaml report shape."""
    obs = payload["structural_observations"]
    sections = [
        Section(
            region=s["region_id"],
            system=s["system"],
            cert=Cert(b0=s["b0"], b1=s["b1"], advisories=s["advisories"]),
        )
        for s in obs
    ]
    transitions = payload["derived_transitions"]
    mismatches = compute_mismatches(sections, transitions)
    baseline = sections[0] if sections else None
    triples = build_triples(baseline, mismatches) if baseline else []
    return {
        "scenario_id":            payload["scenario_id"],
        "status":                 "SS_Obstructed" if triples else "SS_Coherent",
        "mismatches":             mismatches,
        "triples":                triples,
        "rupture_witness_count":  len(payload["rupture_observations"]),
    }


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0


def ok(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)


def section(title: str):
    print(f"\n── {title}")


# ---------------------------------------------------------------------------
# Unit tests: pure transformation functions
# ---------------------------------------------------------------------------

def test_compatibility_status():
    section("_compatibility_status")
    ok("coherent",                   _compatibility_status(1, 1, 1, 1) == "coherent")
    ok("ring_broken",                _compatibility_status(1, 1, 1, 0) == "ring_broken")
    ok("partitioned",                _compatibility_status(1, 1, 2, 1) == "partitioned")
    ok("ring_broken_and_partitioned",_compatibility_status(1, 1, 2, 0) == "ring_broken_and_partitioned")
    ok("b1 already 0 → not ring_broken", _compatibility_status(1, 0, 1, 0) == "coherent")
    ok("b0 same b1 drops from 0 → not ring_broken (already broken)",
       _compatibility_status(1, 0, 1, 0) == "coherent")


def test_advisory_extraction():
    section("extract_per_stage_advisories")
    raw = (
        "STAGE 1 — Nominal\n"
        "  Betti : [1, 1]\n"
        "STAGE 2 — Fault\n"
        "  Betti : [1, 0]\n"
        "  [WARNING] CLUSTER_RING_VIOLATED\n"
        "STAGE 3 — Partition\n"
        "  Betti : [2, 0]\n"
        "  [CRITICAL] CONNECTIVITY_PARTITION\n"
        "  [WARNING] CLUSTER_RING_VIOLATED\n"
    )
    result = extract_per_stage_advisories(raw)
    ok("stage 1: no advisories",      result.get(1, []) == [])
    ok("stage 2: CLUSTER_RING_VIOLATED", result.get(2, []) == ["CLUSTER_RING_VIOLATED"])
    ok("stage 3: both advisories",    result.get(3, []) == ["CONNECTIVITY_PARTITION", "CLUSTER_RING_VIOLATED"])


def test_derived_transitions():
    section("build_derived_transitions")
    obs = [
        {"region_id": "warmup", "b0": 1, "b1": 1},
        {"region_id": "phase1", "b0": 1, "b1": 0},
        {"region_id": "phase2", "b0": 2, "b1": 0},
    ]
    ts = build_derived_transitions(obs)
    ok("two transitions produced",        len(ts) == 2)
    ok("warmup→phase1 status ring_broken", ts[0]["compatibility_status"] == "ring_broken")
    ok("phase1→phase2 status partitioned", ts[1]["compatibility_status"] == "partitioned")
    ok("warmup→phase1 b1 delta [1,0]",    ts[0]["delta"]["b1"] == [1, 0])
    ok("phase1→phase2 b0 delta [1,2]",    ts[1]["delta"]["b0"] == [1, 2])


# ---------------------------------------------------------------------------
# Structural payload validation
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCENА_PAYLOAD = Path(__file__).parent.parent / "output" / "beep_loopaudit_payload.json"


def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    with open(path) as f:
        return json.load(f)


def validate_payload_structure(payload: dict, label: str):
    """Assert required top-level fields and internal consistency."""
    ok(f"{label}: schema_version present",
       payload.get("schema_version") == "beep.loopaudit.bridge.v1")
    ok(f"{label}: scenario_id present",     "scenario_id" in payload)
    ok(f"{label}: timeline.regions non-empty",
       len(payload.get("timeline", {}).get("regions", [])) > 0)
    ok(f"{label}: structural_observations non-empty",
       len(payload.get("structural_observations", [])) > 0)

    # Every structural observation region_id must appear in timeline.regions
    region_ids = {r["region_id"] for r in payload["timeline"]["regions"]}
    for obs in payload["structural_observations"]:
        ok(f"{label}: obs region_id {obs['region_id']!r} in timeline",
           obs["region_id"] in region_ids)

    # Every derived_transition must reference known regions
    for t in payload.get("derived_transitions", []):
        ok(f"{label}: transition {t['from_region']}→{t['to_region']} regions exist",
           t["from_region"] in region_ids and t["to_region"] in region_ids)

    # Rupture observations: confirmed_index >= candidate_index when present
    for r in payload.get("rupture_observations", []):
        if r.get("confirmed_index") is not None:
            ok(f"{label}: confirmed_index >= candidate_index",
               r["confirmed_index"] >= r["candidate_index"])


def test_payload_structures():
    section("Payload structure — scenA (live output)")
    if SCENА_PAYLOAD.exists():
        validate_payload_structure(json.loads(SCENА_PAYLOAD.read_text()), "scenA")
    else:
        print("  SKIP  scenA payload not found (run export first)")

    section("Payload structure — scenB_coherent")
    validate_payload_structure(load_fixture("scenB_coherent_payload.json"), "scenB")

    section("Payload structure — scenC_ring_loss_only")
    validate_payload_structure(load_fixture("scenC_ring_loss_only_payload.json"), "scenC")

    section("Payload structure — scenD_partition_no_rupture")
    validate_payload_structure(load_fixture("scenD_partition_no_rupture_payload.json"), "scenD")


# ---------------------------------------------------------------------------
# Scenario classification tests
# ---------------------------------------------------------------------------

def test_scenario_classifications():
    section("Scenario classification — scenA (ring_loss + partition, 2 rupture witnesses)")
    if SCENА_PAYLOAD.exists():
        a = audit_payload(json.loads(SCENА_PAYLOAD.read_text()))
        ok("scenA: SS_Obstructed",            a["status"] == "SS_Obstructed")
        ok("scenA: 1 obstruction triple",     len(a["triples"]) == 1)
        ok("scenA: triple covers warmup→phase1→phase2",
           (a["triples"][0].region_a, a["triples"][0].region_b, a["triples"][0].region_c)
           == ("warmup", "phase1", "phase2"))
        ok("scenA: ring_loss in failure modes",    "ring_loss" in a["triples"][0].failure_modes)
        ok("scenA: partition in failure modes",    "partition" in a["triples"][0].failure_modes)
        ok("scenA: obstruction_lift NOT in modes", "obstruction_lift" not in a["triples"][0].failure_modes)
        ok("scenA: 2 rupture witnesses",           a["rupture_witness_count"] == 2)
    else:
        print("  SKIP  scenA payload not found")

    section("Scenario classification — scenB (coherent nominal run)")
    b = audit_payload(load_fixture("scenB_coherent_payload.json"))
    ok("scenB: SS_Coherent",                b["status"] == "SS_Coherent")
    ok("scenB: 0 obstruction triples",      len(b["triples"]) == 0)
    ok("scenB: 0 mismatches",               len(b["mismatches"]) == 0)
    ok("scenB: 0 rupture witnesses",        b["rupture_witness_count"] == 0)

    section("Scenario classification — scenC (ring loss only, no partition)")
    c = audit_payload(load_fixture("scenC_ring_loss_only_payload.json"))
    ok("scenC: SS_Obstructed",              c["status"] == "SS_Obstructed")
    ok("scenC: 1 obstruction triple",       len(c["triples"]) == 1)
    ok("scenC: triple covers warmup→phase1→phase2",
       (c["triples"][0].region_a, c["triples"][0].region_b, c["triples"][0].region_c)
       == ("warmup", "phase1", "phase2"))
    ok("scenC: ring_loss in failure modes",    "ring_loss" in c["triples"][0].failure_modes)
    ok("scenC: partition NOT in failure modes","partition" not in c["triples"][0].failure_modes)
    ok("scenC: obstruction_lift NOT in modes", "obstruction_lift" not in c["triples"][0].failure_modes)
    ok("scenC: 1 rupture witness",             c["rupture_witness_count"] == 1)

    section("Scenario classification — scenD (partition, no rupture precursor)")
    d = audit_payload(load_fixture("scenD_partition_no_rupture_payload.json"))
    ok("scenD: SS_Obstructed",              d["status"] == "SS_Obstructed")
    ok("scenD: 1 obstruction triple",       len(d["triples"]) == 1)
    ok("scenD: degenerate triple (B=C)",
       d["triples"][0].region_b == d["triples"][0].region_c)
    ok("scenD: ring_loss in failure modes",    "ring_loss" in d["triples"][0].failure_modes)
    ok("scenD: partition in failure modes",    "partition" in d["triples"][0].failure_modes)
    ok("scenD: 0 rupture witnesses",           d["rupture_witness_count"] == 0)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("BEEP → LoopAudit bridge regression suite")
    print("=" * 50)

    test_compatibility_status()
    test_advisory_extraction()
    test_derived_transitions()
    test_payload_structures()
    test_scenario_classifications()

    print(f"\n{'=' * 50}")
    print(f"Results: {PASS} passed, {FAIL} failed")

    if FAIL:
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
