"""
regions.py — Core data structures for point-free regional systems.

A RegionalSystem consists of:
  - A finite set of named regions, each with a dimension label
  - An adjacency relation (symmetric, between regions of any dimension)
  - An overlap relation (symmetric, reflexive)
  - Boundary-contact pairs (directed: region R has boundary-contact with region B
    when B is a codimension-1 region adjacent to R that "bounds" it)

Regions are NOT required to be simplices, cells, or CW pieces.
The boundary operator will be derived from adjacency structure, not from
pre-labelled face lists.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class Region:
    """A named region with a dimension label."""
    name: str
    dim: int
    data: dict = field(default_factory=dict)  # arbitrary metadata

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Region):
            return self.name == other.name
        return NotImplemented

    def __repr__(self):
        return f"Reg({self.name}, dim={self.dim})"


class RegionalSystem:
    """
    A point-free regional system.

    Stores regions with dimension labels and two fundamental relations:
      - adjacency: regions that share a boundary-contact
      - overlap: regions that share interior content

    Boundary-contact is directional: (R, B, sign) means region B of
    dimension dim(R)-1 is a boundary constituent of R with orientation sign.
    These are NOT pre-labelled faces — they are derived or declared from
    adjacency axioms.
    """

    def __init__(self, name: str = "unnamed"):
        self.name = name
        self._regions: dict[str, Region] = {}
        self._adjacency: set[tuple[str, str]] = set()
        self._overlap: set[tuple[str, str]] = set()
        # boundary contacts: (higher_region, lower_region, orientation_sign)
        self._boundary_contacts: list[tuple[str, str, int]] = []

    # --- Region management ---

    def add_region(self, name: str, dim: int, **data) -> Region:
        r = Region(name=name, dim=dim, data=data)
        self._regions[name] = r
        return r

    def region(self, name: str) -> Region:
        return self._regions[name]

    def regions(self, dim: Optional[int] = None) -> list[Region]:
        rs = list(self._regions.values())
        if dim is not None:
            rs = [r for r in rs if r.dim == dim]
        return sorted(rs, key=lambda r: r.name)

    def region_names(self, dim: Optional[int] = None) -> list[str]:
        return [r.name for r in self.regions(dim)]

    def max_dim(self) -> int:
        if not self._regions:
            return -1
        return max(r.dim for r in self._regions.values())

    # --- Relations ---

    def add_adjacency(self, a: str, b: str):
        """Declare that regions a and b are adjacent (symmetric)."""
        self._adjacency.add((a, b))
        self._adjacency.add((b, a))

    def add_overlap(self, a: str, b: str):
        """Declare that regions a and b overlap (symmetric)."""
        self._overlap.add((a, b))
        self._overlap.add((b, a))

    def add_boundary_contact(self, higher: str, lower: str, sign: int):
        """
        Declare that `lower` is a boundary constituent of `higher`
        with orientation sign (+1 or -1).

        This is the raw incidence data from which ∂_W is built.
        The sign encodes how the lower region is oriented relative
        to the higher region's induced orientation.
        """
        assert sign in (+1, -1), "Orientation sign must be +1 or -1"
        rh = self._regions[higher]
        rl = self._regions[lower]
        assert rh.dim == rl.dim + 1, (
            f"Boundary contact requires codimension 1: "
            f"{higher}(dim={rh.dim}) -> {lower}(dim={rl.dim})"
        )
        self._boundary_contacts.append((higher, lower, sign))
        self.add_adjacency(higher, lower)

    def adjacent(self, a: str, b: str) -> bool:
        return (a, b) in self._adjacency

    def overlaps(self, a: str, b: str) -> bool:
        return (a, b) in self._overlap

    def boundary_contacts_of(self, region_name: str) -> list[tuple[str, int]]:
        """Return [(lower_region, sign)] for all boundary contacts of a region."""
        return [
            (lower, sign)
            for (higher, lower, sign) in self._boundary_contacts
            if higher == region_name
        ]

    def coboundary_contacts_of(self, region_name: str) -> list[tuple[str, int]]:
        """Return [(higher_region, sign)] for regions that this region bounds."""
        return [
            (higher, sign)
            for (higher, lower, sign) in self._boundary_contacts
            if lower == region_name
        ]

    # --- Adjacency-derived boundary detection ---

    def adjacency_neighbors(self, name: str, dim: Optional[int] = None) -> list[str]:
        """All regions adjacent to `name`, optionally filtered by dimension."""
        neighbors = []
        for (a, b) in self._adjacency:
            if a == name:
                if dim is None or self._regions[b].dim == dim:
                    neighbors.append(b)
        return sorted(set(neighbors))

    # --- Summary ---

    def summary(self) -> str:
        lines = [f"RegionalSystem: {self.name}"]
        for d in range(self.max_dim() + 1):
            rs = self.regions(dim=d)
            lines.append(f"  dim {d}: {len(rs)} regions — {[r.name for r in rs]}")
        lines.append(f"  adjacency pairs: {len(self._adjacency) // 2}")
        lines.append(f"  boundary contacts: {len(self._boundary_contacts)}")
        return "\n".join(lines)

    def __repr__(self):
        return self.summary()
