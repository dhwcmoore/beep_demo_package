"""
invariants.py — Fullness gap, closure defect, and structural diagnostics.

These invariants go beyond standard Betti numbers and torsion. They measure
properties of the regional system that are specific to the point-free setting.

Fullness gap: How saturated is the relation space?
  Given an abstraction scheme defining a space P of possible relations,
  and realised relations R ⊆ P, the fullness gap is |P| - |R|.

Closure defect: How far is the boundary operator from being exact?
  Measures the gap between geometric thinness and algebraic exactness.

Structural redundancy: Ratio of generators to independent cycles.
"""

from __future__ import annotations
import numpy as np
from regions import RegionalSystem
from chain_complex import ChainComplex, build_overlap_nerve
from homology import compute_homology, smith_normal_form, diagonal_entries


def possible_adjacencies(system: RegionalSystem) -> int:
    """
    Count the maximum number of adjacencies that could exist
    between regions of adjacent dimensions.

    This is the size of the "possible relation space" P.
    """
    count = 0
    d = system.max_dim()
    for k in range(1, d + 1):
        nk = len(system.regions(dim=k))
        nkm1 = len(system.regions(dim=k - 1))
        count += nk * nkm1
    return count


def realised_adjacencies(system: RegionalSystem) -> int:
    """
    Count adjacencies that actually exist between regions
    of adjacent dimensions.

    This is |R|, the realised subset of P.
    """
    count = 0
    d = system.max_dim()
    for k in range(1, d + 1):
        k_names = system.region_names(dim=k)
        for rname in k_names:
            neighbors = system.adjacency_neighbors(rname, dim=k - 1)
            count += len(neighbors)
    return count


def fullness_gap(system: RegionalSystem) -> dict:
    """
    Compute the fullness gap: how far the realised relation structure
    is from maximal saturation.

    Returns:
        possible: |P| total possible codim-1 adjacencies
        realised: |R| actual adjacencies
        gap: |P| - |R|
        saturation: |R| / |P| (0 to 1)
    """
    P = possible_adjacencies(system)
    R = realised_adjacencies(system)
    return {
        "possible": P,
        "realised": R,
        "gap": P - R,
        "saturation": R / P if P > 0 else 1.0,
    }


def closure_defect(cc: ChainComplex) -> dict:
    """
    Measure the closure defect of the chain complex.

    For each dimension k, compute:
      - rank of ∂_k (= dim of image)
      - nullity of ∂_k (= dim of kernel)
      - rank of ∂_{k+1}
      - defect = nullity(∂_k) - rank(∂_{k+1}) - betti_k

    If the complex is valid (∂∘∂=0), defect should be 0 everywhere.
    Nonzero defect indicates inconsistency.

    Also computes the "exactness ratio": how close each Betti number
    is to zero (measuring how close the complex is to being exact).
    """
    hom = compute_homology(cc)
    results = {}

    for k in range(cc.max_dim + 1):
        nk = cc.rank(k)
        if nk == 0:
            results[k] = {"rank_dk": 0, "nullity_dk": 0, "rank_dk1": 0,
                          "betti": 0, "defect": 0, "exactness_ratio": 1.0}
            continue

        dk = cc.boundary_matrix(k)
        dk1 = cc.boundary_matrix(k + 1)

        # Rank of ∂_k
        if dk.size == 0 or np.all(dk == 0):
            rank_dk = 0
        else:
            _, Dk, _ = smith_normal_form(dk)
            rank_dk = sum(1 for d in diagonal_entries(Dk) if d != 0)

        nullity_dk = nk - rank_dk

        # Rank of ∂_{k+1}
        if dk1.size == 0 or np.all(dk1 == 0):
            rank_dk1 = 0
        else:
            _, Dk1, _ = smith_normal_form(dk1)
            rank_dk1 = sum(1 for d in diagonal_entries(Dk1) if d != 0)

        betti = hom[k].betti
        defect = nullity_dk - rank_dk1 - betti

        # Exactness ratio: 1 means exact (H_k = 0), 0 means maximally inexact
        if nullity_dk > 0:
            exactness = 1.0 - (betti / nullity_dk)
        else:
            exactness = 1.0

        results[k] = {
            "rank_dk": rank_dk,
            "nullity_dk": nullity_dk,
            "rank_dk1": rank_dk1,
            "betti": betti,
            "defect": defect,
            "exactness_ratio": exactness,
        }

    return results


def structural_redundancy(cc: ChainComplex) -> dict:
    """
    Measure structural redundancy: ratio of total generators to
    independent features (Betti numbers).

    High redundancy means many generators contribute to boundaries
    rather than to independent cycles. This is a measure of how
    "efficient" the regional decomposition is.
    """
    hom = compute_homology(cc)
    total_generators = sum(cc.rank(k) for k in range(cc.max_dim + 1))
    total_betti = sum(hom[k].betti for k in hom)

    return {
        "total_generators": total_generators,
        "total_betti": total_betti,
        "redundancy": (total_generators - total_betti) / total_generators
        if total_generators > 0 else 0.0,
    }


def full_diagnostic(system: RegionalSystem, cc: ChainComplex) -> str:
    """Complete diagnostic report."""
    lines = [f"=== Full Diagnostic: {system.name} ==="]
    lines.append("")

    # Fullness
    fg = fullness_gap(system)
    lines.append("Fullness Gap:")
    lines.append(f"  possible adjacencies: {fg['possible']}")
    lines.append(f"  realised adjacencies: {fg['realised']}")
    lines.append(f"  gap: {fg['gap']}")
    lines.append(f"  saturation: {fg['saturation']:.3f}")
    lines.append("")

    # Closure defect
    cd = closure_defect(cc)
    lines.append("Closure Defect:")
    for k in sorted(cd.keys()):
        d = cd[k]
        lines.append(
            f"  dim {k}: rank(∂_k)={d['rank_dk']}, "
            f"null(∂_k)={d['nullity_dk']}, "
            f"rank(∂_{{k+1}})={d['rank_dk1']}, "
            f"β_k={d['betti']}, "
            f"exactness={d['exactness_ratio']:.3f}"
        )
    lines.append("")

    # Redundancy
    sr = structural_redundancy(cc)
    lines.append("Structural Redundancy:")
    lines.append(f"  generators: {sr['total_generators']}")
    lines.append(f"  total Betti: {sr['total_betti']}")
    lines.append(f"  redundancy: {sr['redundancy']:.3f}")

    # Overlap nerve (only when overlap data is present)
    if system._overlap:
        lines.append("")
        nerve = build_overlap_nerve(system)
        nerve_hom = compute_homology(nerve)
        lines.append("Overlap Nerve Homology:")
        lines.append(f"  (nerve vertices: {nerve.generators.get(0, [])})")
        lines.append(f"  (nerve edges:    {nerve.generators.get(1, [])})")
        lines.append(f"  (nerve faces:    {nerve.generators.get(2, [])})")
        for k in sorted(nerve_hom.keys()):
            h = nerve_hom[k]
            tors = ", ".join(f"Z/{t}Z" for t in h.torsion) if h.torsion else "none"
            lines.append(f"  H_{k}(nerve) = Z^{h.betti}, torsion: {tors}")

    return "\n".join(lines)
