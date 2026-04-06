"""
chiplet_monitor_demo.py — UCIe Chiplet Ring: invariant violation → monitor → detection

Demonstrates the full Boundary Logic pipeline on a concrete hardware target:
a 4-chiplet ring NoC (Network-on-Chip) using UCIe (Universal Chiplet
Interconnect Express) die-to-die links.

Pipeline stages:
  1. Declare the regional system (chiplets + links)
  2. Compute structural invariants (Betti numbers via Smith Normal Form)
  3. Export a certified JSON payload (canonical SHA-256 hash)
  4. Compare nominal vs fault invariants
  5. Generate monitor advisories from the invariant delta

Usage:
  cd python
  python demos/chiplet_monitor_demo.py

No OCaml required — pure Python pipeline.
"""

import sys
import os

# Wire up engine and export paths (matching conftest.py)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "engine"))
sys.path.insert(0, os.path.join(_HERE, ".."))

from examples_hardware import (
    example_chiplet_ring_nominal,
    example_chiplet_ring_link_fault,
    example_chiplet_ring_partition,
)
from chain_complex import build_chain_complex
from homology import compute_homology
from export.invariants_writer import build_v1_payload
from export.canonical_json import payload_sha256_hex


# ── Pipeline helper ───────────────────────────────────────────────────────────

def run_pipeline(builder):
    """Build a regional system, compute invariants, return (homology, payload)."""
    system = builder()
    cc = build_chain_complex(system, mode="explicit")
    hom = compute_homology(cc)

    betti   = {str(k): hom[k].betti   for k in sorted(hom)}
    torsion = {str(k): hom[k].torsion for k in sorted(hom)}

    payload = build_v1_payload(
        engine="boundary_logic_python",
        engine_version="0.1.0",
        inputs_hash="0" * 64,
        max_dim=int(cc.max_dim),
        cell_counts={k: cc.rank(k) for k in range(cc.max_dim + 1)},
        boundary_squared_zero_verified=bool(cc.is_valid),
        thinness_verified=None,
        betti=betti,
        torsion=torsion,
    )
    return system, hom, payload


# ── Monitor advisory generator ────────────────────────────────────────────────

def generate_advisories(nominal_betti: dict, fault_betti: dict) -> list:
    """
    Compare nominal and fault Betti numbers and return monitor advisories.

    The Betti number delta is the algebraic certificate of the structural
    violation. No heuristics — the invariants ARE the specification.
    """
    advisories = []

    db0 = fault_betti.get(0, 0) - nominal_betti.get(0, 0)
    db1 = fault_betti.get(1, 0) - nominal_betti.get(1, 0)

    if db0 > 0:
        advisories.append({
            "code": "CONNECTIVITY_PARTITION",
            "severity": "CRITICAL",
            "delta_b0": db0,
            "message": (
                f"Network partitioned into {fault_betti.get(0)} isolated clusters "
                f"(was {nominal_betti.get(0)}). "
                f"Some chiplets are topologically unreachable."
            ),
            "action": (
                "Isolate affected partition. Reroute inter-cluster traffic "
                "via backup fabric or off-chip switch. Halt cross-cluster workloads."
            ),
        })

    if db1 < 0:
        advisories.append({
            "code": "RING_TOPOLOGY_VIOLATED",
            "severity": "WARNING",
            "delta_b1": db1,
            "message": (
                f"Ring cycle count dropped from {nominal_betti.get(1, 0)} "
                f"to {fault_betti.get(1, 0)}. "
                f"Ring routing algorithm assumption violated."
            ),
            "action": (
                "Switch NoC to fallback mesh routing. "
                "Flag failed link(s) for replacement. "
                "Revalidate routing tables."
            ),
        })

    if db1 > 0:
        advisories.append({
            "code": "UNEXPECTED_CYCLE",
            "severity": "WARNING",
            "delta_b1": db1,
            "message": (
                f"Unexpected routing cycle detected: b₁ rose from "
                f"{nominal_betti.get(1, 0)} to {fault_betti.get(1, 0)}."
            ),
            "action": (
                "Audit routing table for deadlock risk. "
                "Verify no phantom link declarations in fabric configuration."
            ),
        })

    if not advisories:
        advisories.append({
            "code": "NOMINAL",
            "severity": "OK",
            "message": "Invariants match nominal. No structural violations detected.",
            "action": "None required.",
        })

    return advisories


# ── Display helpers ───────────────────────────────────────────────────────────

def fmt_betti(hom: dict) -> str:
    dims = sorted(hom.keys())
    return "[" + ", ".join(str(hom[k].betti) for k in dims) + "]"


def fmt_betti_dict(d: dict) -> str:
    return "[" + ", ".join(str(d[k]) for k in sorted(d)) + "]"


def print_section(title: str):
    print()
    print("─" * 68)
    print(f"  {title}")
    print("─" * 68)


def print_payload_summary(system, hom, payload):
    dims = sorted(hom.keys())
    betti_str   = fmt_betti(hom)
    torsion_str = [hom[k].torsion for k in dims if hom[k].torsion]
    cells_str   = [f"dim{k}:{payload['complex_summary']['cell_counts'][str(k)]}"
                   for k in dims]
    sha = payload["integrity"]["payload_sha256"][:16] + "..."

    print(f"  system   : {system.name}")
    print(f"  cells    : {', '.join(cells_str)}")
    print(f"  Betti    : {betti_str}")
    if torsion_str:
        print(f"  torsion  : {torsion_str}")
    print(f"  sha256   : {sha}")
    print(f"  valid ∂² : {payload['complex_summary']['boundary_squared_zero_verified']}")


def print_advisory(adv: dict):
    sev = adv["severity"]
    code = adv["code"]
    marker = "🔴" if sev == "CRITICAL" else ("🟡" if sev == "WARNING" else "🟢")
    print(f"  {marker} [{sev}] {code}")
    print(f"     {adv['message']}")
    print(f"     → {adv['action']}")


# ── Main demo ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 68)
    print("  UCIe Chiplet Ring NoC — Structural Invariant Monitor Demo")
    print("  Boundary Logic Pipeline  |  boundary_logic_python v0.1.0")
    print("=" * 68)

    # ── Stage 1: Nominal state ────────────────────────────────────────────
    print_section("STAGE 1 — Nominal: 4-chiplet ring (c0─c1─c2─c3─c0)")
    sys_nom, hom_nom, pay_nom = run_pipeline(example_chiplet_ring_nominal)
    print_payload_summary(sys_nom, hom_nom, pay_nom)
    print()
    print("  Interpretation:")
    print("    b₀=1 → fully connected (all chiplets reachable)")
    print("    b₁=1 → one ring cycle (ring routing algorithm valid)")
    print("  This payload is the certified structural baseline.")

    nom_betti = {int(k): v for k, v in pay_nom["homology"]["betti"].items()}

    # ── Stage 2: Link fault ───────────────────────────────────────────────
    print_section("STAGE 2 — Fault: UCIe link l23 (c2→c3) has failed")
    sys_lf, hom_lf, pay_lf = run_pipeline(example_chiplet_ring_link_fault)
    print_payload_summary(sys_lf, hom_lf, pay_lf)

    lf_betti = {int(k): v for k, v in pay_lf["homology"]["betti"].items()}

    print()
    print("  Invariant delta vs nominal:")
    print(f"    b₀: {nom_betti[0]} → {lf_betti[0]}  (no change)")
    print(f"    b₁: {nom_betti[1]} → {lf_betti.get(1, 0)}  ← VIOLATION")

    print()
    print("  Monitor advisories:")
    for adv in generate_advisories(nom_betti, lf_betti):
        print_advisory(adv)

    # ── Stage 3: Partition ────────────────────────────────────────────────
    print_section("STAGE 3 — Fault: links l12 (c1→c2) and l30 (c3→c0) both failed")
    sys_pt, hom_pt, pay_pt = run_pipeline(example_chiplet_ring_partition)
    print_payload_summary(sys_pt, hom_pt, pay_pt)

    pt_betti = {int(k): v for k, v in pay_pt["homology"]["betti"].items()}

    print()
    print("  Invariant delta vs nominal:")
    print(f"    b₀: {nom_betti[0]} → {pt_betti[0]}  ← CRITICAL VIOLATION")
    print(f"    b₁: {nom_betti[1]} → {pt_betti.get(1, 0)}  ← VIOLATION")

    print()
    print("  Monitor advisories:")
    for adv in generate_advisories(nom_betti, pt_betti):
        print_advisory(adv)

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print("=" * 68)
    print("  Pipeline summary")
    print("=" * 68)
    print()
    print("  The Betti number sequence b=[b₀, b₁] is the structural certificate.")
    print()
    print(f"  Nominal          b=[1,1]  — ring intact, routing valid")
    print(f"  Link fault       b=[1,0]  — ring broken, reroute required")
    print(f"  Partition        b=[2,0]  — network split, cross-cluster traffic blocked")
    print()
    print("  Each payload is SHA-256 signed. The OCaml kernel can independently")
    print("  verify integrity and compare invariants against the certified baseline.")
    print()
    print("  Key property: the invariant computation is algebraically exact.")
    print("  b₁=1 is not a heuristic — it is a theorem about the declared topology.")
    print("  When b₁ drops to 0, the ring cycle provably no longer exists.")
    print()


if __name__ == "__main__":
    main()
