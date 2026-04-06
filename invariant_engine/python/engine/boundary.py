"""
boundary.py — Whitehead boundary operator ∂_W.

The boundary operator is derived from the regional system's adjacency
and boundary-contact structure. It maps each k-dimensional region to
a formal integer combination of (k-1)-dimensional regions.

Two modes of operation:

1. EXPLICIT: boundary contacts are declared with orientations.
   ∂_W is read directly from the declared contacts.

2. DERIVED: boundary contacts are inferred from adjacency axioms.
   Given a k-region R, its boundary constituents are all (k-1)-regions
   adjacent to R. Orientations must then be assigned consistently.

The key requirement: ∂_W must arise from geometric/relational structure,
not from algebraic assumption. The thinness condition ∂∘∂ = 0 is then
a *theorem* about the regional system, not an axiom.
"""

from __future__ import annotations
from typing import Optional
import numpy as np
from regions import RegionalSystem


def boundary_matrix_explicit(system: RegionalSystem, k: int) -> np.ndarray:
    """
    Build the boundary matrix ∂_k : C_k → C_{k-1} from explicit
    boundary contacts declared in the regional system.

    Returns an integer matrix of shape (n_{k-1}, n_k) where:
      - columns correspond to k-regions (sorted by name)
      - rows correspond to (k-1)-regions (sorted by name)
      - entry [i, j] is the orientation sign of contact, or 0
    """
    k_regions = system.region_names(dim=k)
    km1_regions = system.region_names(dim=k - 1)

    if not k_regions or not km1_regions:
        return np.zeros((len(km1_regions), len(k_regions)), dtype=int)

    row_idx = {name: i for i, name in enumerate(km1_regions)}
    col_idx = {name: j for j, name in enumerate(k_regions)}

    matrix = np.zeros((len(km1_regions), len(k_regions)), dtype=int)

    for j, rname in enumerate(k_regions):
        for (lower, sign) in system.boundary_contacts_of(rname):
            if lower in row_idx:
                matrix[row_idx[lower], j] += sign

    return matrix


def boundary_matrix_from_adjacency(
    system: RegionalSystem,
    k: int,
    orientation_fn=None
) -> np.ndarray:
    """
    Build ∂_k by inferring boundary contacts from adjacency.

    For each k-region R, its boundary constituents are all (k-1)-regions
    adjacent to R. Orientation is assigned by `orientation_fn`, which
    defaults to a canonical lexicographic alternating scheme.

    This is the "derived" mode where ∂_W emerges from relational structure.

    Parameters:
        system: the regional system
        k: dimension of source regions
        orientation_fn: callable(system, higher_name, lower_name, index) -> +1/-1
            If None, uses alternating signs by sorted position.
    """
    k_regions = system.region_names(dim=k)
    km1_regions = system.region_names(dim=k - 1)

    if not k_regions or not km1_regions:
        return np.zeros((len(km1_regions), len(k_regions)), dtype=int)

    row_idx = {name: i for i, name in enumerate(km1_regions)}

    matrix = np.zeros((len(km1_regions), len(k_regions)), dtype=int)

    for j, rname in enumerate(k_regions):
        # Find all (k-1)-dimensional neighbors
        neighbors = system.adjacency_neighbors(rname, dim=k - 1)
        for idx, lower in enumerate(neighbors):
            if lower in row_idx:
                if orientation_fn is not None:
                    sign = orientation_fn(system, rname, lower, idx)
                else:
                    sign = (-1) ** idx  # alternating by sorted position
                matrix[row_idx[lower], j] += sign

    return matrix


def get_boundary_matrix(
    system: RegionalSystem,
    k: int,
    mode: str = "explicit"
) -> np.ndarray:
    """
    Get the boundary matrix ∂_k for the given system.

    mode: "explicit" uses declared boundary contacts
          "adjacency" derives from adjacency relations
    """
    if mode == "explicit":
        return boundary_matrix_explicit(system, k)
    elif mode == "adjacency":
        return boundary_matrix_from_adjacency(system, k)
    else:
        raise ValueError(f"Unknown mode: {mode}")


def check_thinness(system: RegionalSystem, mode: str = "explicit") -> dict:
    """
    Check whether ∂_{k-1} ∘ ∂_k = 0 for all k.

    This is the thinness condition. If boundary contacts are derived from
    genuine geometric structure, this should hold. If it fails, the regional
    system has an orientation or structural defect.

    Returns a dict {k: (holds, defect_matrix)} for each relevant k.
    """
    results = {}
    d = system.max_dim()

    for k in range(2, d + 1):
        dk = get_boundary_matrix(system, k, mode=mode)
        dk_minus1 = get_boundary_matrix(system, k - 1, mode=mode)

        if dk.shape[0] != dk_minus1.shape[1]:
            # dimension mismatch — no (k-1)-regions to compose through
            results[k] = (True, np.zeros((dk_minus1.shape[0], dk.shape[1]), dtype=int))
            continue

        composition = dk_minus1 @ dk
        holds = np.all(composition == 0)
        results[k] = (holds, composition)

    return results


def thinness_report(system: RegionalSystem, mode: str = "explicit") -> str:
    """Human-readable thinness check."""
    results = check_thinness(system, mode=mode)
    lines = [f"Thinness check for '{system.name}' (mode={mode}):"]

    if not results:
        lines.append("  No compositions to check (max_dim < 2)")
        return "\n".join(lines)

    all_hold = True
    for k in sorted(results.keys()):
        holds, defect = results[k]
        status = "HOLDS" if holds else "FAILS"
        if not holds:
            all_hold = False
            max_defect = int(np.max(np.abs(defect)))
            lines.append(f"  ∂_{k-1} ∘ ∂_{k} = 0 : {status} (max defect = {max_defect})")
            lines.append(f"    defect matrix:\n{defect}")
        else:
            lines.append(f"  ∂_{k-1} ∘ ∂_{k} = 0 : {status}")

    if all_hold:
        lines.append("  >> Regional system forms a valid chain complex.")
    else:
        lines.append("  >> DEFECT: thinness violated — orientation or structural problem.")

    return "\n".join(lines)
