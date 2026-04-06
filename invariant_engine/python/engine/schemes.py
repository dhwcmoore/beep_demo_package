"""
schemes.py — Abstraction schemes over regional systems.

An abstraction scheme defines a *lens* through which a regional system
is viewed. Different schemes over the same underlying territory can yield
different chain complexes and different invariants.

A scheme consists of:
  - A selection of which regions to include (resolution)
  - A choice of adjacency predicate (connectivity)
  - A choice of orientation convention

Varying the scheme and comparing invariants is the key operation that
distinguishes this framework from classical cellular homology. In classical
topology, the decomposition is scaffolding you prove away. Here, the scheme
is part of the data.

Persistence across schemes = structural robustness.
Scheme-dependent features = artifacts of abstraction.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
from regions import RegionalSystem, Region
from chain_complex import ChainComplex, build_chain_complex
from homology import compute_homology, HomologyGroup


@dataclass
class AbstractionScheme:
    """
    An abstraction scheme over a regional system.

    Attributes:
        name: identifier for this scheme
        region_filter: function(Region) -> bool, which regions to include
        adjacency_override: optional function(sys, a, b) -> bool,
            replacing the system's adjacency with a different predicate
        mode: "explicit" or "adjacency" for boundary derivation
        orientation_fn: optional custom orientation function
    """
    name: str
    region_filter: Callable[[Region], bool] = lambda r: True
    adjacency_override: Optional[Callable] = None
    mode: str = "explicit"
    orientation_fn: Optional[Callable] = None


def apply_scheme(
    system: RegionalSystem,
    scheme: AbstractionScheme
) -> RegionalSystem:
    """
    Apply an abstraction scheme to a regional system, producing a
    new (filtered/modified) regional system.
    """
    new_sys = RegionalSystem(name=f"{system.name}|{scheme.name}")

    # Filter regions
    included = set()
    for r in system._regions.values():
        if scheme.region_filter(r):
            new_sys.add_region(r.name, r.dim, **r.data)
            included.add(r.name)

    # Copy or override adjacency
    if scheme.adjacency_override is not None:
        # Use custom adjacency predicate
        names = list(included)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if scheme.adjacency_override(system, a, b):
                    new_sys.add_adjacency(a, b)
    else:
        # Copy existing adjacency (filtered)
        seen = set()
        for (a, b) in system._adjacency:
            if a in included and b in included:
                pair = (min(a, b), max(a, b))
                if pair not in seen:
                    new_sys.add_adjacency(a, b)
                    seen.add(pair)

    # Copy boundary contacts (filtered)
    for (higher, lower, sign) in system._boundary_contacts:
        if higher in included and lower in included:
            # Re-add without the assertion check (already validated)
            new_sys._boundary_contacts.append((higher, lower, sign))

    # Copy overlaps (filtered)
    for (a, b) in system._overlap:
        if a in included and b in included:
            new_sys._overlap.add((a, b))

    return new_sys


def compare_schemes(
    system: RegionalSystem,
    schemes: list[AbstractionScheme]
) -> dict:
    """
    Apply multiple abstraction schemes to the same system and compare
    the resulting invariants.

    Returns a dict with scheme names as keys and result dicts as values.
    Each result contains the filtered system, chain complex, and homology.
    """
    results = {}

    for scheme in schemes:
        filtered = apply_scheme(system, scheme)
        cc = build_chain_complex(filtered, mode=scheme.mode)
        hom = compute_homology(cc)

        betti = [hom[k].betti for k in sorted(hom.keys())]
        torsion = {k: hom[k].torsion for k in hom if hom[k].torsion}
        euler = sum((-1) ** k * hom[k].betti for k in hom)

        results[scheme.name] = {
            "system": filtered,
            "chain_complex": cc,
            "homology": hom,
            "betti": betti,
            "torsion": torsion,
            "euler": euler,
        }

    return results


def persistence_report(
    system: RegionalSystem,
    schemes: list[AbstractionScheme]
) -> str:
    """
    Compare schemes and report which features persist across all schemes
    vs which are scheme-dependent.
    """
    results = compare_schemes(system, schemes)
    lines = [f"Persistence analysis for '{system.name}' across {len(schemes)} schemes:"]
    lines.append("")

    # Collect Betti numbers per scheme
    all_betti = {}
    for sname, res in results.items():
        all_betti[sname] = res["betti"]
        lines.append(f"  Scheme '{sname}':")
        lines.append(f"    regions: {[r.name for r in res['system'].regions()]}")
        lines.append(f"    Betti: {res['betti']}")
        lines.append(f"    Euler: {res['euler']}")
        if res["torsion"]:
            lines.append(f"    Torsion: {res['torsion']}")
        lines.append("")

    # Check what persists
    betti_lists = list(all_betti.values())
    if len(betti_lists) > 1:
        # Find max length
        max_len = max(len(b) for b in betti_lists)
        padded = [b + [0] * (max_len - len(b)) for b in betti_lists]

        persistent = []
        varying = []
        for k in range(max_len):
            vals = [p[k] for p in padded]
            if len(set(vals)) == 1:
                persistent.append((k, vals[0]))
            else:
                varying.append((k, vals))

        if persistent:
            lines.append("  PERSISTENT features (same across all schemes):")
            for k, v in persistent:
                lines.append(f"    β_{k} = {v}")

        if varying:
            lines.append("  SCHEME-DEPENDENT features:")
            for k, vals in varying:
                lines.append(f"    β_{k} varies: {dict(zip(all_betti.keys(), vals))}")

    return "\n".join(lines)
