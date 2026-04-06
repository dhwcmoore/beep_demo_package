"""
cluster_monitor_demo.py — 4-node compute cluster: invariant violation → monitor → detection
"""

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "engine"))
sys.path.insert(0, os.path.join(_HERE, ".."))

from examples_infrastructure import (
    example_cluster_nominal,
    example_cluster_link_fault,
    example_cluster_partition,
)
from chain_complex import build_chain_complex
from homology import compute_homology
from export.invariants_writer import build_v1_payload


def run_pipeline(builder):
    system = builder()
    cc = build_chain_complex(system, mode="explicit")
    hom = compute_homology(cc)

    betti = {str(k): hom[k].betti for k in sorted(hom)}

    payload = build_v1_payload(
        engine="boundary_logic_python",
        engine_version="0.1.0",
        inputs_hash="0" * 64,
        max_dim=int(cc.max_dim),
        cell_counts={k: cc.rank(k) for k in range(cc.max_dim + 1)},
        boundary_squared_zero_verified=bool(cc.is_valid),
        thinness_verified=None,
        betti=betti,
        torsion={}
    )

    return system, hom, payload


def main():
    print("=== Cluster Invariant Demo ===")

    sys_nom, hom_nom, pay_nom = run_pipeline(example_cluster_nominal)
    nom_betti = {int(k): v for k, v in pay_nom["homology"]["betti"].items()}

    sys_fault, hom_fault, pay_fault = run_pipeline(example_cluster_link_fault)
    fault_betti = {int(k): v for k, v in pay_fault["homology"]["betti"].items()}

    print("Nominal Betti:", nom_betti)
    print("Fault Betti:", fault_betti)


if __name__ == "__main__":
    main()
