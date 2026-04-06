"""
chain_complex.py — Chain complex formation from boundary matrices.

Given a regional system and a boundary mode, this module assembles the
full chain complex:

    C_d  →  C_{d-1}  →  ...  →  C_1  →  C_0  →  0

Each C_k = Z^{n_k} where n_k is the number of k-dimensional regions.
Each ∂_k is represented as an integer matrix.

The chain complex is the algebraic stabilisation of geometric differentiation.
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from regions import RegionalSystem
from boundary import get_boundary_matrix, check_thinness


@dataclass
class ChainComplex:
    """
    A chain complex over Z.

    Attributes:
        generators: dict mapping dimension k to list of region names
        matrices: dict mapping dimension k to the matrix ∂_k (shape n_{k-1} x n_k)
        max_dim: highest dimension present
        is_valid: whether ∂∘∂ = 0 holds everywhere
        system_name: name of the source regional system
    """
    generators: dict[int, list[str]]
    matrices: dict[int, np.ndarray]
    max_dim: int
    is_valid: bool
    system_name: str

    def rank(self, k: int) -> int:
        """Number of generators in dimension k."""
        return len(self.generators.get(k, []))

    def boundary_matrix(self, k: int) -> np.ndarray:
        """Get ∂_k. Returns zero matrix if k is out of range."""
        if k in self.matrices:
            return self.matrices[k]
        # return appropriately shaped zero matrix
        nk = self.rank(k)
        nkm1 = self.rank(k - 1)
        return np.zeros((nkm1, nk), dtype=int)

    def summary(self) -> str:
        lines = [f"ChainComplex from '{self.system_name}'"]
        lines.append(f"  valid (∂∘∂=0): {self.is_valid}")
        for k in range(self.max_dim, -1, -1):
            n = self.rank(k)
            lines.append(f"  C_{k} = Z^{n}  generators: {self.generators.get(k, [])}")
        for k in range(self.max_dim, 0, -1):
            m = self.matrices.get(k)
            if m is not None:
                lines.append(f"  ∂_{k} ({m.shape[0]}x{m.shape[1]}):")
                lines.append(f"{m}")
        return "\n".join(lines)


def build_overlap_nerve(system: RegionalSystem) -> ChainComplex:
    """
    Build the Čech nerve chain complex from the overlap relation.

    Vertices (0-simplices): all region names appearing in at least one overlap pair.
    Edges   (1-simplices): unordered pairs {A, B} with A overlaps B.
    Faces   (2-simplices): unordered triples {A, B, C} where every pair overlaps.

    Standard alternating-sign simplicial boundary:
        ∂₁ {a,b}   = b − a          (a < b lexicographically)
        ∂₂ {a,b,c} = {b,c} − {a,c} + {a,b}   (a < b < c)

    The nerve of an open cover is always a simplicial complex, so ∂∘∂ = 0
    holds by construction.  The resulting homology captures how the overlapping
    regions are connected to each other — independently of the incidence chain
    complex built from boundary contacts.

    If system._overlap is empty the returned complex has no generators.
    """
    import itertools

    # Canonical edge set: pairs stored with a < b (lexicographic)
    raw = system._overlap  # set of (a, b) including both orientations
    edge_set: set[tuple[str, str]] = set()
    for (a, b) in raw:
        if a != b:
            pair = (min(a, b), max(a, b))
            edge_set.add(pair)

    edges: list[tuple[str, str]] = sorted(edge_set)

    # Vertices: every name appearing in at least one edge
    verts: list[str] = sorted({r for pair in edges for r in pair})

    # Triangles: triples (a,b,c) with a<b<c where all three pairs are in edge_set
    tris = []
    for a, b, c in itertools.combinations(verts, 3):
        if (a, b) in edge_set and (a, c) in edge_set and (b, c) in edge_set:
            tris.append((a, b, c))

    # Index maps
    vert_idx = {v: i for i, v in enumerate(verts)}
    edge_idx = {e: i for i, e in enumerate(edges)}

    generators: dict[int, list[str]] = {}
    matrices: dict[int, np.ndarray] = {}

    # 0-chains
    generators[0] = list(verts)

    # 1-chains and ∂₁ : verts × edges
    generators[1] = [f"{{{a},{b}}}" for (a, b) in edges]
    if verts and edges:
        d1 = np.zeros((len(verts), len(edges)), dtype=int)
        for j, (a, b) in enumerate(edges):
            d1[vert_idx[a], j] = -1   # remove a → sign (−1)^0 · ... standard orientation
            d1[vert_idx[b], j] = +1
        matrices[1] = d1
    else:
        matrices[1] = np.zeros((len(verts), len(edges)), dtype=int)

    # 2-chains and ∂₂ : edges × triangles
    generators[2] = [f"{{{a},{b},{c}}}" for (a, b, c) in tris]
    if edges and tris:
        d2 = np.zeros((len(edges), len(tris)), dtype=int)
        for j, (a, b, c) in enumerate(tris):
            # ∂{a,b,c} = {b,c} − {a,c} + {a,b}
            d2[edge_idx[(b, c)], j] = +1
            d2[edge_idx[(a, c)], j] = -1
            d2[edge_idx[(a, b)], j] = +1
        matrices[2] = d2
    else:
        matrices[2] = np.zeros((len(edges), len(tris)), dtype=int)

    max_dim = 2 if tris else (1 if edges else 0)

    # Verify ∂₁ ∘ ∂₂ = 0 rather than trusting convention alone.
    # A single sign error anywhere would silently survive is_valid=True.
    if tris and edges and verts:
        is_valid = bool(np.all(matrices[1] @ matrices[2] == 0))
    else:
        is_valid = True

    return ChainComplex(
        generators=generators,
        matrices=matrices,
        max_dim=max_dim,
        is_valid=is_valid,
        system_name=system.name + "_nerve",
    )


def build_chain_complex(
    system: RegionalSystem,
    mode: str = "explicit"
) -> ChainComplex:
    """
    Build the full chain complex from a regional system.

    Parameters:
        system: the regional system
        mode: "explicit" or "adjacency" — how boundary contacts are determined
    """
    d = system.max_dim()

    generators = {}
    matrices = {}

    for k in range(d + 1):
        generators[k] = system.region_names(dim=k)

    for k in range(1, d + 1):
        matrices[k] = get_boundary_matrix(system, k, mode=mode)

    # check validity
    thinness = check_thinness(system, mode=mode)
    is_valid = all(holds for (holds, _) in thinness.values())

    return ChainComplex(
        generators=generators,
        matrices=matrices,
        max_dim=d,
        is_valid=is_valid,
        system_name=system.name,
    )
