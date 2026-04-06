"""
examples_hardware.py — Concrete hardware topology models.

These examples map real hardware interconnect structures onto the regional
system framework, showing how structural invariant violations translate
into monitor alerts.

Target: UCIe (Universal Chiplet Interconnect Express) ring topology,
as used in multi-chiplet SoCs (AMD MI300X, Intel Sapphire Rapids style).

The key insight: a ring NoC has a topological signature b₁ = 1 (one
independent cycle). Routing algorithms that exploit ring symmetry depend
on this. When a link fails, b₁ drops to 0 — the ring is broken and the
routing algorithm must be reconfigured. When two links fail, b₀ rises
above 1 — the network has partitioned and some chiplets cannot
communicate at all.

Each example returns a RegionalSystem with:
  0-dim regions: chiplet nodes
  1-dim regions: UCIe die-to-die links (oriented: source → destination)
"""

from regions import RegionalSystem


def example_chiplet_ring_nominal() -> RegionalSystem:
    """
    Healthy 4-chiplet ring NoC with full UCIe link connectivity.

    Topology: c0 — c1 — c2 — c3 — c0  (ring)

    Each link is a oriented UCIe D2D (die-to-die) connection.
    The ring has one independent cycle, giving b₁ = 1.

    Invariants:
      b₀ = 1   (fully connected — all chiplets reachable)
      b₁ = 1   (one ring cycle — ring routing algorithm valid)
      χ  = 0   (V − E = 4 − 4 = 0)

    This is the nominal certified state. Any deviation from b=[1,1]
    triggers a monitor advisory.
    """
    s = RegionalSystem("chiplet_ring_nominal")

    # 0-dim: four chiplet dies
    s.add_region("c0", 0)
    s.add_region("c1", 0)
    s.add_region("c2", 0)
    s.add_region("c3", 0)

    # 1-dim: four UCIe links forming the ring
    s.add_region("l01", 1)  # c0 → c1
    s.add_region("l12", 1)  # c1 → c2
    s.add_region("l23", 1)  # c2 → c3
    s.add_region("l30", 1)  # c3 → c0

    # Boundary contacts: ∂(lij) = cj − ci  (oriented edge)
    s.add_boundary_contact("l01", "c1", +1)
    s.add_boundary_contact("l01", "c0", -1)

    s.add_boundary_contact("l12", "c2", +1)
    s.add_boundary_contact("l12", "c1", -1)

    s.add_boundary_contact("l23", "c3", +1)
    s.add_boundary_contact("l23", "c2", -1)

    s.add_boundary_contact("l30", "c0", +1)
    s.add_boundary_contact("l30", "c3", -1)

    return s


def example_chiplet_ring_link_fault() -> RegionalSystem:
    """
    4-chiplet ring with UCIe link l23 failed (ESD damage / manufacturing defect).

    Topology: c0 — c1 — c2   c3 — c0  (broken ring, but still connected)

    The four chiplets remain reachable via the remaining three links,
    but the ring cycle is destroyed: b₁ drops from 1 to 0.

    Invariants:
      b₀ = 1   (still connected — path c0→c1→c2 and c0→c3 exist)
      b₁ = 0   (ring cycle eliminated — ring routing invalid)
      χ  = 1   (V − E = 4 − 3 = 1)

    Monitor advisory: RING_TOPOLOGY_VIOLATED
      Action: switch NoC to fallback mesh routing, flag l23 for replacement.

    Note: b₁ changing 1→0 is the algebraic certificate that the routing
    algorithm's topological assumption has been violated. No higher-level
    health check is required — the invariant IS the check.
    """
    s = RegionalSystem("chiplet_ring_link_fault")

    # 0-dim: four chiplet dies (unchanged)
    s.add_region("c0", 0)
    s.add_region("c1", 0)
    s.add_region("c2", 0)
    s.add_region("c3", 0)

    # 1-dim: three remaining links — l23 has failed and is absent
    s.add_region("l01", 1)
    s.add_region("l12", 1)
    # l23 intentionally absent: UCIe link between c2 and c3 is down
    s.add_region("l30", 1)

    s.add_boundary_contact("l01", "c1", +1)
    s.add_boundary_contact("l01", "c0", -1)

    s.add_boundary_contact("l12", "c2", +1)
    s.add_boundary_contact("l12", "c1", -1)

    s.add_boundary_contact("l30", "c0", +1)
    s.add_boundary_contact("l30", "c3", -1)

    return s


def example_chiplet_ring_partition() -> RegionalSystem:
    """
    4-chiplet ring with links l12 and l30 both failed (catastrophic partition).

    Topology: c0 — c1     c2 — c3  (two isolated clusters)

    The network has split into two disconnected components:
      Cluster A: {c0, c1}  connected by l01
      Cluster B: {c2, c3}  connected by l23

    Chiplets in cluster A cannot communicate with cluster B at all.

    Invariants:
      b₀ = 2   (two disconnected components — catastrophic partition)
      b₁ = 0   (no cycles — no ring)
      χ  = 2   (V − E = 4 − 2 = 2)

    Monitor advisory: CONNECTIVITY_PARTITION (CRITICAL)
      Action: isolate partition, reroute inter-cluster traffic via
      backup fabric or off-chip switch, halt cross-cluster workloads.

    This is the worst-case violation: b₀ > 1 means some compute units
    are topologically unreachable. No routing algorithm can fix this —
    the physical path does not exist.
    """
    s = RegionalSystem("chiplet_ring_partition")

    # 0-dim: four chiplet dies (unchanged)
    s.add_region("c0", 0)
    s.add_region("c1", 0)
    s.add_region("c2", 0)
    s.add_region("c3", 0)

    # 1-dim: two surviving links — l12 and l30 have both failed
    s.add_region("l01", 1)  # cluster A internal link
    s.add_region("l23", 1)  # cluster B internal link
    # l12 (c1→c2) and l30 (c3→c0): both failed — bridges between clusters gone

    s.add_boundary_contact("l01", "c1", +1)
    s.add_boundary_contact("l01", "c0", -1)

    s.add_boundary_contact("l23", "c3", +1)
    s.add_boundary_contact("l23", "c2", -1)

    return s
