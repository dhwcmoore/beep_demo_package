"""
examples_infrastructure.py — Compute cluster topology models.

A 4-node compute cluster connected in a ring topology, modelling a common
data-centre configuration: four server nodes with inter-node links forming
a ring for low-latency, fault-tolerant intra-cluster communication.

The structural invariant is identical to the chiplet ring (examples_hardware.py)
because the mathematics of connectivity is domain-agnostic. The Betti numbers
encode properties of the graph, not properties of the hardware label.

  b₀ = number of connected components   (1 = all nodes reachable)
  b₁ = number of independent cycles     (1 = ring routing path valid)

When a link fails:
  b₁ drops to 0  → ring path destroyed; reroute traffic, flag link for repair
When two links fail at the bridge positions:
  b₀ rises to 2  → cluster partitioned; some nodes unreachable; halt cross-island workloads

Each builder returns a RegionalSystem with:
  0-dim regions: server nodes
  1-dim regions: inter-node links (oriented: source → destination)
"""

from regions import RegionalSystem


def example_cluster_nominal() -> RegionalSystem:
    """
    Healthy 4-node compute cluster with full ring connectivity.

    Topology: s0 — s1 — s2 — s3 — s0  (ring)

    All four nodes are reachable and the ring routing path is intact.

    Invariants:
      b₀ = 1   (fully connected — all nodes reachable)
      b₁ = 1   (one ring cycle — ring routing valid)
      χ  = 0   (V − E = 4 − 4 = 0)

    This is the nominal certified state. Any deviation from b=[1,1]
    triggers a monitor advisory.
    """
    s = RegionalSystem("cluster_nominal")

    # 0-dim: four server nodes
    s.add_region("s0", 0)
    s.add_region("s1", 0)
    s.add_region("s2", 0)
    s.add_region("s3", 0)

    # 1-dim: four inter-node links forming the ring
    s.add_region("l01", 1)  # s0 → s1
    s.add_region("l12", 1)  # s1 → s2
    s.add_region("l23", 1)  # s2 → s3
    s.add_region("l30", 1)  # s3 → s0

    # Boundary contacts: ∂(lij) = sj − si  (oriented edge)
    s.add_boundary_contact("l01", "s1", +1)
    s.add_boundary_contact("l01", "s0", -1)

    s.add_boundary_contact("l12", "s2", +1)
    s.add_boundary_contact("l12", "s1", -1)

    s.add_boundary_contact("l23", "s3", +1)
    s.add_boundary_contact("l23", "s2", -1)

    s.add_boundary_contact("l30", "s0", +1)
    s.add_boundary_contact("l30", "s3", -1)

    return s


def example_cluster_link_fault() -> RegionalSystem:
    """
    4-node cluster with link l23 (s2→s3) failed.

    Topology: s0 — s1 — s2   s3 — s0  (ring broken, still connected)

    All four nodes remain reachable via the three surviving links,
    but the ring cycle is destroyed: b₁ drops from 1 to 0.

    Invariants:
      b₀ = 1   (still connected — path s0→s1→s2 and s0→s3 exist)
      b₁ = 0   (ring cycle eliminated — ring routing invalid)
      χ  = 1   (V − E = 4 − 3 = 1)

    Monitor advisory: CLUSTER_RING_VIOLATED
      Action: switch to fallback mesh routing; flag l23 for replacement;
      revalidate routing tables.

    b₁ changing 1→0 is the algebraic certificate that the ring routing
    assumption has been violated. No higher-level health check is required —
    the invariant IS the check.
    """
    s = RegionalSystem("cluster_link_fault")

    # 0-dim: four server nodes (unchanged)
    s.add_region("s0", 0)
    s.add_region("s1", 0)
    s.add_region("s2", 0)
    s.add_region("s3", 0)

    # 1-dim: three remaining links — l23 has failed
    s.add_region("l01", 1)
    s.add_region("l12", 1)
    # l23 intentionally absent: link between s2 and s3 is down
    s.add_region("l30", 1)

    s.add_boundary_contact("l01", "s1", +1)
    s.add_boundary_contact("l01", "s0", -1)

    s.add_boundary_contact("l12", "s2", +1)
    s.add_boundary_contact("l12", "s1", -1)

    s.add_boundary_contact("l30", "s0", +1)
    s.add_boundary_contact("l30", "s3", -1)

    return s


def example_cluster_partition() -> RegionalSystem:
    """
    4-node cluster with links l12 and l30 both failed (catastrophic partition).

    Topology: s0 — s1     s2 — s3  (two isolated islands)

    The cluster has split into two disconnected islands:
      Island A: {s0, s1}  connected by l01
      Island B: {s2, s3}  connected by l23

    Nodes in island A cannot communicate with island B at all.

    Invariants:
      b₀ = 2   (two disconnected components — catastrophic partition)
      b₁ = 0   (no cycles — ring destroyed)
      χ  = 2   (V − E = 4 − 2 = 2)

    Monitor advisory: CONNECTIVITY_PARTITION (CRITICAL)
      Action: isolate partition; halt cross-island workloads; trigger failover.

    b₀ > 1 means some nodes are topologically unreachable. No routing
    reconfiguration can fix this — the physical path does not exist.
    """
    s = RegionalSystem("cluster_partition")

    # 0-dim: four server nodes (unchanged)
    s.add_region("s0", 0)
    s.add_region("s1", 0)
    s.add_region("s2", 0)
    s.add_region("s3", 0)

    # 1-dim: two surviving links — l12 and l30 have both failed
    s.add_region("l01", 1)  # island A internal link
    s.add_region("l23", 1)  # island B internal link
    # l12 (s1→s2) and l30 (s3→s0): both failed — bridges between islands gone

    s.add_boundary_contact("l01", "s1", +1)
    s.add_boundary_contact("l01", "s0", -1)

    s.add_boundary_contact("l23", "s3", +1)
    s.add_boundary_contact("l23", "s2", -1)

    return s
