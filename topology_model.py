"""
topology_model.py — VeriStrain Scotford
Physical and functional topology graphs with typed edges and operational regions.

Two graphs are maintained:
  - Physical graph: what is installed in the plant
  - Functional graph: what is currently usable / active

Comparing them surfaces the operationally important gap:
  "Redundancy exists physically, but is functionally lost."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Iterator, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------

class EdgeType(str, Enum):
    MATERIAL_FLOW       = "material_flow"
    PRESSURE_TRANSFER   = "pressure_transfer"
    THERMAL_DEPENDENCY  = "thermal_dependency"
    CONTROL_DEPENDENCY  = "control_dependency"
    MEASUREMENT_DEPENDENCY = "measurement_dependency"
    REDUNDANCY_RELATION = "redundancy_relation"
    RELIEF_PATH         = "relief_path"
    SHUTDOWN_DEPENDENCY = "shutdown_dependency"


class EdgeState(str, Enum):
    ACTIVE      = "active"
    INACTIVE    = "inactive"
    DEGRADED    = "degraded"
    UNKNOWN     = "unknown"


# ---------------------------------------------------------------------------
# Edge and region data objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlantEdge:
    """
    A directed edge between two plant components.
    `source` → `target` with a semantic type and current state.
    """
    source:    str
    target:    str
    edge_type: EdgeType
    state:     EdgeState = EdgeState.ACTIVE
    stream_id: Optional[str] = None
    notes:     Optional[str] = None

    def key(self) -> Tuple[str, str, str]:
        return (self.source, self.target, self.edge_type.value)


@dataclass
class PlantRegion:
    """
    A named operational region grouping components under a shared concern:
    unit, containment, thermal, high-pressure, monitoring, shutdown, etc.
    """
    region_id:           str
    region_type:         str         # "unit" | "containment" | "thermal" | "high_pressure" | "monitoring" | "shutdown"
    member_components:   Set[str]    = field(default_factory=set)
    boundary_components: Set[str]    = field(default_factory=set)  # components at the edge
    required_sensors:    List[str]   = field(default_factory=list)
    safety_criticality:  str         = "low_consequence"
    notes:               Optional[str] = None

    def contains(self, component_id: str) -> bool:
        return component_id in self.member_components

    def is_boundary(self, component_id: str) -> bool:
        return component_id in self.boundary_components


# ---------------------------------------------------------------------------
# Graph primitives
# ---------------------------------------------------------------------------

class ComponentGraph:
    """
    A directed graph of plant components connected by typed edges.
    Used for both physical and functional topology.
    """

    def __init__(self, label: str):
        self.label = label
        self._nodes: Set[str] = set()
        self._edges: List[PlantEdge] = []

    def add_node(self, component_id: str) -> None:
        self._nodes.add(component_id)

    def add_edge(self, edge: PlantEdge) -> None:
        self._nodes.add(edge.source)
        self._nodes.add(edge.target)
        self._edges.append(edge)

    @property
    def nodes(self) -> FrozenSet[str]:
        return frozenset(self._nodes)

    @property
    def edges(self) -> List[PlantEdge]:
        return list(self._edges)

    def edges_of_type(self, edge_type: EdgeType) -> List[PlantEdge]:
        return [e for e in self._edges if e.edge_type == edge_type]

    def active_edges(self) -> List[PlantEdge]:
        return [e for e in self._edges if e.state == EdgeState.ACTIVE]

    def neighbours(self, node: str) -> List[str]:
        return [e.target for e in self._edges if e.source == node]

    def predecessors(self, node: str) -> List[str]:
        return [e.source for e in self._edges if e.target == node]

    def connected_components(self, active_only: bool = True) -> List[FrozenSet[str]]:
        """
        Undirected connected component decomposition.
        If active_only, only follow edges with EdgeState.ACTIVE.
        """
        edges = self.active_edges() if active_only else self._edges
        adj: Dict[str, Set[str]] = {n: set() for n in self._nodes}
        for e in edges:
            adj.setdefault(e.source, set()).add(e.target)
            adj.setdefault(e.target, set()).add(e.source)

        visited: Set[str] = set()
        components: List[FrozenSet[str]] = []
        for start in self._nodes:
            if start in visited:
                continue
            stack = [start]
            component: Set[str] = set()
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)
                stack.extend(adj.get(node, set()) - visited)
            components.append(frozenset(component))
        return components

    def has_cycle(self, active_only: bool = True) -> bool:
        """Detect whether the graph contains at least one directed cycle."""
        edges = self.active_edges() if active_only else self._edges
        adj: Dict[str, List[str]] = {n: [] for n in self._nodes}
        for e in edges:
            adj.setdefault(e.source, []).append(e.target)

        WHITE, GRAY, BLACK = 0, 1, 2
        colour: Dict[str, int] = {n: WHITE for n in self._nodes}

        def dfs(v: str) -> bool:
            colour[v] = GRAY
            for w in adj.get(v, []):
                if colour.get(w, WHITE) == GRAY:
                    return True
                if colour.get(w, WHITE) == WHITE and dfs(w):
                    return True
            colour[v] = BLACK
            return False

        return any(dfs(n) for n in self._nodes if colour.get(n, WHITE) == WHITE)

    def reachable_from(self, source: str, active_only: bool = True) -> Set[str]:
        """All nodes reachable from `source` by directed path."""
        edges = self.active_edges() if active_only else self._edges
        adj: Dict[str, List[str]] = {}
        for e in edges:
            adj.setdefault(e.source, []).append(e.target)

        visited: Set[str] = set()
        stack = [source]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            stack.extend(adj.get(node, []))
        return visited - {source}

    def b0(self, active_only: bool = True) -> int:
        """Number of connected components (Betti-0)."""
        return len(self.connected_components(active_only))

    def b1(self, active_only: bool = True) -> int:
        """
        Number of independent cycles (Betti-1).
        For a directed graph treated as undirected: b1 = |E| - |V| + b0.
        """
        edges = self.active_edges() if active_only else self._edges
        E = len(edges)
        V = len(self._nodes)
        B0 = self.b0(active_only)
        val = E - V + B0
        return max(val, 0)


# ---------------------------------------------------------------------------
# Dual-graph topology model
# ---------------------------------------------------------------------------

@dataclass
class TopologyComparison:
    """Result of comparing physical vs functional topology."""
    physical_b0: int
    physical_b1: int
    functional_b0: int
    functional_b1: int

    # Edge losses
    lost_material_paths:      List[PlantEdge] = field(default_factory=list)
    lost_control_dependencies: List[PlantEdge] = field(default_factory=list)
    lost_measurement_links:   List[PlantEdge] = field(default_factory=list)
    lost_redundancy_relations: List[PlantEdge] = field(default_factory=list)
    lost_relief_paths:        List[PlantEdge] = field(default_factory=list)

    # Region anomalies
    disconnected_regions:     List[str] = field(default_factory=list)
    unobservable_regions:     List[str] = field(default_factory=list)

    @property
    def redundancy_physically_present(self) -> bool:
        return self.physical_b1 > 0

    @property
    def redundancy_functionally_available(self) -> bool:
        return self.functional_b1 > 0

    @property
    def redundancy_lost(self) -> bool:
        return self.redundancy_physically_present and not self.redundancy_functionally_available

    @property
    def partition_emerged(self) -> bool:
        return self.functional_b0 > self.physical_b0

    @property
    def cycle_lost(self) -> bool:
        return self.functional_b1 < self.physical_b1

    def summary(self) -> str:
        parts = []
        if self.redundancy_lost:
            parts.append("physical redundancy present but functional redundancy lost")
        if self.partition_emerged:
            parts.append("plant partitioned in functional graph but not physical graph")
        if self.lost_material_paths:
            parts.append(
                f"{len(self.lost_material_paths)} material flow path(s) inactive"
            )
        if self.lost_control_dependencies:
            parts.append(
                f"{len(self.lost_control_dependencies)} control dependency link(s) lost"
            )
        if self.lost_relief_paths:
            parts.append(
                f"{len(self.lost_relief_paths)} relief path(s) inactive"
            )
        return "; ".join(parts) if parts else "physical and functional topology consistent"


class PlantTopologyModel:
    """
    Maintains both the physical and functional plant graphs, plus
    the set of named operational regions.

    The functional graph is built from the physical graph by removing
    edges that are inactive (valve closed, pump failed, etc.).
    """

    def __init__(self):
        self.physical:  ComponentGraph = ComponentGraph("physical")
        self.functional: ComponentGraph = ComponentGraph("functional")
        self.regions:   List[PlantRegion] = []

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def declare_component(self, component_id: str) -> None:
        self.physical.add_node(component_id)
        self.functional.add_node(component_id)

    def add_physical_edge(self, edge: PlantEdge) -> None:
        self.physical.add_edge(edge)

    def activate_edge(self, edge: PlantEdge) -> None:
        """Add an edge to both physical and functional graphs (it is active)."""
        active_edge = PlantEdge(
            source=edge.source,
            target=edge.target,
            edge_type=edge.edge_type,
            state=EdgeState.ACTIVE,
            stream_id=edge.stream_id,
            notes=edge.notes,
        )
        self.physical.add_edge(active_edge)
        self.functional.add_edge(active_edge)

    def deactivate_edge(self, edge: PlantEdge) -> None:
        """
        Record an edge as physically present but functionally inactive.
        It appears in the physical graph (as INACTIVE) but not in functional.
        """
        inactive_edge = PlantEdge(
            source=edge.source,
            target=edge.target,
            edge_type=edge.edge_type,
            state=EdgeState.INACTIVE,
            stream_id=edge.stream_id,
            notes=edge.notes,
        )
        self.physical.add_edge(inactive_edge)
        # functional graph does not receive this edge

    def add_region(self, region: PlantRegion) -> None:
        self.regions.append(region)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(self) -> TopologyComparison:
        """Compute the difference between physical and functional topology."""
        # Inactive edges in physical are missing from functional
        inactive = [e for e in self.physical.edges if e.state != EdgeState.ACTIVE]

        def of_type(edges: List[PlantEdge], et: EdgeType) -> List[PlantEdge]:
            return [e for e in edges if e.edge_type == et]

        # Unobservable regions: no active measurement edges from any member
        active_targets = {e.target for e in self.functional.active_edges()
                          if e.edge_type == EdgeType.MEASUREMENT_DEPENDENCY}
        unobservable_regions = [
            r.region_id
            for r in self.regions
            if r.member_components and
               r.member_components.isdisjoint(active_targets)
        ]

        # Disconnected regions: region members not all in the same functional component
        functional_components = self.functional.connected_components(active_only=True)
        def component_of(node: str) -> Optional[FrozenSet[str]]:
            for comp in functional_components:
                if node in comp:
                    return comp
            return None

        disconnected_regions = []
        for r in self.regions:
            members = list(r.member_components)
            if len(members) < 2:
                continue
            first_comp = component_of(members[0])
            if any(component_of(m) != first_comp for m in members[1:]):
                disconnected_regions.append(r.region_id)

        return TopologyComparison(
            physical_b0  = self.physical.b0(active_only=False),
            physical_b1  = self.physical.b1(active_only=False),
            functional_b0 = self.functional.b0(active_only=True),
            functional_b1 = self.functional.b1(active_only=True),
            lost_material_paths       = of_type(inactive, EdgeType.MATERIAL_FLOW),
            lost_control_dependencies = of_type(inactive, EdgeType.CONTROL_DEPENDENCY),
            lost_measurement_links    = of_type(inactive, EdgeType.MEASUREMENT_DEPENDENCY),
            lost_redundancy_relations = of_type(inactive, EdgeType.REDUNDANCY_RELATION),
            lost_relief_paths         = of_type(inactive, EdgeType.RELIEF_PATH),
            disconnected_regions  = disconnected_regions,
            unobservable_regions  = unobservable_regions,
        )

    # ------------------------------------------------------------------
    # Region queries
    # ------------------------------------------------------------------

    def region_for(self, component_id: str) -> Optional[PlantRegion]:
        for r in self.regions:
            if r.contains(component_id):
                return r
        return None

    def regions_of_type(self, region_type: str) -> List[PlantRegion]:
        return [r for r in self.regions if r.region_type == region_type]

    def critical_regions(self) -> List[PlantRegion]:
        return [
            r for r in self.regions
            if r.safety_criticality in ("high_consequence", "safety_critical")
        ]
