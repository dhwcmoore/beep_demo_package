"""
examples.py — Non-classical regional systems for testing.

These examples are deliberately constructed to NOT be simplicial complexes
or CW complexes. They test whether the invariant engine detects structure
that classical cellular homology cannot see.

Each example returns a RegionalSystem with explicit boundary contacts.
"""

from regions import RegionalSystem


def example_triangle_classical() -> RegionalSystem:
    """
    Classical triangle (simplicial): a 2-region bounded by three 1-regions
    (edges), each bounded by two 0-regions (vertices).

    This SHOULD reproduce classical simplicial homology:
      H_0 = Z, H_1 = 0, H_2 = 0   (contractible)

    This is the control case.
    """
    s = RegionalSystem("triangle_classical")

    # 0-dim: vertices
    s.add_region("v0", 0)
    s.add_region("v1", 0)
    s.add_region("v2", 0)

    # 1-dim: edges (oriented: e01 goes from v0 to v1, etc.)
    s.add_region("e01", 1)
    s.add_region("e12", 1)
    s.add_region("e02", 1)

    # 2-dim: face
    s.add_region("F", 2)

    # Edge boundaries: ∂(e_ij) = v_j - v_i
    s.add_boundary_contact("e01", "v1", +1)
    s.add_boundary_contact("e01", "v0", -1)
    s.add_boundary_contact("e12", "v2", +1)
    s.add_boundary_contact("e12", "v1", -1)
    s.add_boundary_contact("e02", "v2", +1)
    s.add_boundary_contact("e02", "v0", -1)

    # Face boundary: ∂(F) = e01 + e12 - e02
    s.add_boundary_contact("F", "e01", +1)
    s.add_boundary_contact("F", "e12", +1)
    s.add_boundary_contact("F", "e02", -1)

    return s


def example_loop_no_fill() -> RegionalSystem:
    """
    Three 1-regions forming a closed loop with no 2-region filling.

    This is the boundary of a triangle without the face.
    Should detect H_1 = Z (one independent cycle).
    """
    s = RegionalSystem("loop_no_fill")

    s.add_region("v0", 0)
    s.add_region("v1", 0)
    s.add_region("v2", 0)

    s.add_region("e01", 1)
    s.add_region("e12", 1)
    s.add_region("e02", 1)

    s.add_boundary_contact("e01", "v1", +1)
    s.add_boundary_contact("e01", "v0", -1)
    s.add_boundary_contact("e12", "v2", +1)
    s.add_boundary_contact("e12", "v1", -1)
    s.add_boundary_contact("e02", "v2", +1)
    s.add_boundary_contact("e02", "v0", -1)

    return s


def example_triple_junction() -> RegionalSystem:
    """
    NON-CLASSICAL: Three 2-regions meeting at a single shared 1-region.

    Imagine three rooms sharing a single wall segment. This cannot be
    a simplicial complex because in a simplicial complex, a 1-simplex
    is shared by at most two 2-simplices.

    Structure:
      - Three 2-regions: A, B, C
      - Four 1-regions: the shared wall "w", plus outer edges
      - Vertices connecting them

    This tests whether the engine handles non-manifold junctions.
    """
    s = RegionalSystem("triple_junction")

    # 0-dim: vertices
    s.add_region("p", 0)   # junction point top
    s.add_region("q", 0)   # junction point bottom
    s.add_region("a0", 0)  # outer vertex of A
    s.add_region("b0", 0)  # outer vertex of B
    s.add_region("c0", 0)  # outer vertex of C

    # 1-dim: shared wall and outer edges
    s.add_region("w", 1)    # shared wall between all three
    s.add_region("eA1", 1)  # edge of A from p to a0
    s.add_region("eA2", 1)  # edge of A from a0 to q
    s.add_region("eB1", 1)  # edge of B from p to b0
    s.add_region("eB2", 1)  # edge of B from b0 to q
    s.add_region("eC1", 1)  # edge of C from p to c0
    s.add_region("eC2", 1)  # edge of C from c0 to q

    # 2-dim: three rooms
    s.add_region("A", 2)
    s.add_region("B", 2)
    s.add_region("C", 2)

    # Wall boundary: w goes from p to q
    s.add_boundary_contact("w", "q", +1)
    s.add_boundary_contact("w", "p", -1)

    # Outer edges
    s.add_boundary_contact("eA1", "a0", +1)
    s.add_boundary_contact("eA1", "p", -1)
    s.add_boundary_contact("eA2", "q", +1)
    s.add_boundary_contact("eA2", "a0", -1)

    s.add_boundary_contact("eB1", "b0", +1)
    s.add_boundary_contact("eB1", "p", -1)
    s.add_boundary_contact("eB2", "q", +1)
    s.add_boundary_contact("eB2", "b0", -1)

    s.add_boundary_contact("eC1", "c0", +1)
    s.add_boundary_contact("eC1", "p", -1)
    s.add_boundary_contact("eC2", "q", +1)
    s.add_boundary_contact("eC2", "c0", -1)

    # Room boundaries: each room is bounded by the shared wall + two outer edges
    # A: ∂A = w + eA2 - eA1  (going around: p->q via w, q->a0 via eA2^{-1}... )
    # Actually: ∂A = eA1 + eA2 - w (oriented so boundary goes p->a0->q then q->p via -w)
    # Let's be careful: boundary of A traverses eA1 (p->a0), eA2 (a0->q), -w (q->p)
    s.add_boundary_contact("A", "eA1", +1)
    s.add_boundary_contact("A", "eA2", +1)
    s.add_boundary_contact("A", "w", -1)

    # B: boundary traverses eB1 (p->b0), eB2 (b0->q), -w (q->p)
    s.add_boundary_contact("B", "eB1", +1)
    s.add_boundary_contact("B", "eB2", +1)
    s.add_boundary_contact("B", "w", -1)

    # C: boundary traverses eC1 (p->c0), eC2 (c0->q), -w (q->p)
    s.add_boundary_contact("C", "eC1", +1)
    s.add_boundary_contact("C", "eC2", +1)
    s.add_boundary_contact("C", "w", -1)

    return s


def example_thick_boundary() -> RegionalSystem:
    """
    NON-CLASSICAL: A region whose boundary is itself a region with
    nonzero "thickness" — not a lower-dimensional face.

    In classical topology, boundaries are codimension-1 submanifolds.
    Here we model a situation where the boundary region B has its own
    internal structure (sub-boundaries), creating a layered system.

    Structure:
      - 2-region "interior"
      - 1-region "membrane" (the thick boundary)
      - 1-region "exterior_edge"
      - 0-regions at junctions

    The membrane itself has boundary (0-dim endpoints), giving a
    two-level boundary structure.
    """
    s = RegionalSystem("thick_boundary")

    # 0-dim
    s.add_region("p0", 0)
    s.add_region("p1", 0)
    s.add_region("p2", 0)
    s.add_region("p3", 0)

    # 1-dim: membrane edges and exterior edges
    s.add_region("m01", 1)  # membrane segment p0->p1
    s.add_region("m12", 1)  # membrane segment p1->p2
    s.add_region("m23", 1)  # membrane segment p2->p3
    s.add_region("m30", 1)  # membrane segment p3->p0
    s.add_region("ext", 1)  # exterior edge p0->p2 (diagonal)

    # 2-dim: interior region and exterior region
    s.add_region("interior", 2)
    s.add_region("exterior", 2)

    # Membrane segment boundaries
    s.add_boundary_contact("m01", "p1", +1)
    s.add_boundary_contact("m01", "p0", -1)
    s.add_boundary_contact("m12", "p2", +1)
    s.add_boundary_contact("m12", "p1", -1)
    s.add_boundary_contact("m23", "p3", +1)
    s.add_boundary_contact("m23", "p2", -1)
    s.add_boundary_contact("m30", "p0", +1)
    s.add_boundary_contact("m30", "p3", -1)

    # Exterior edge
    s.add_boundary_contact("ext", "p2", +1)
    s.add_boundary_contact("ext", "p0", -1)

    # Interior bounded by full membrane loop: m01 + m12 + m23 + m30
    s.add_boundary_contact("interior", "m01", +1)
    s.add_boundary_contact("interior", "m12", +1)
    s.add_boundary_contact("interior", "m23", +1)
    s.add_boundary_contact("interior", "m30", +1)

    # Exterior region bounded by partial membrane + diagonal
    # Goes: p0->p1->p2 via membrane, then p2->p0 via ext
    s.add_boundary_contact("exterior", "m01", -1)
    s.add_boundary_contact("exterior", "m12", -1)
    s.add_boundary_contact("exterior", "ext", +1)

    return s


def example_overlapping_regions() -> RegionalSystem:
    """
    NON-CLASSICAL: Two 2-regions that overlap in interior content.

    X (quadrilateral a-b-c-d) and Y (triangle b-e-c) share the edge bc
    as a common boundary component: bc appears in ∂X with +1 and in ∂Y
    with -1.  The non-classical aspect is not in the incidence structure
    (bc bounding two faces is classically allowed) but in the declared
    overlap relation X overlaps Y, which is recorded in _overlap and used
    by the overlap nerve semantic layer.

    Incidence chain complex semantics:
      X and Y are two disks glued along the arc bc.  That is contractible.
      H₀ = Z, H₁ = 0, H₂ = 0.

    Overlap nerve semantics:
      The nerve has one edge {X–Y} (no triple overlap), which is contractible.
      H₀ = Z, H₁ = 0, H₂ = 0.

    Both semantics agree: the union of two overlapping simply-connected
    regions with contractible intersection is simply connected.

    Note on the earlier "shared" 1-cell (now removed):
      A previous version added a parallel arc "shared" from b to c alongside
      bc.  Because shared was not in ∂X or ∂Y, the cycle [shared − bc]
      survived in H₁, giving a spurious Z.  Interior overlap cannot be
      correctly modeled by adding a parallel arc; the overlap relation is
      the right carrier for that information.
    """
    s = RegionalSystem("overlapping_regions")

    # 0-dim
    s.add_region("a", 0)
    s.add_region("b", 0)
    s.add_region("c", 0)
    s.add_region("d", 0)
    s.add_region("e", 0)

    # 1-dim: edges (no "shared" arc — that was the semantic mistake)
    s.add_region("ab", 1)  # a→b
    s.add_region("bc", 1)  # b→c  (shared boundary between X and Y)
    s.add_region("cd", 1)  # c→d
    s.add_region("da", 1)  # d→a
    s.add_region("be", 1)  # b→e
    s.add_region("ec", 1)  # e→c

    # 2-dim
    s.add_region("X", 2)  # quadrilateral  a-b-c-d
    s.add_region("Y", 2)  # triangle       b-e-c

    # Edge boundaries
    s.add_boundary_contact("ab", "b", +1)
    s.add_boundary_contact("ab", "a", -1)
    s.add_boundary_contact("bc", "c", +1)
    s.add_boundary_contact("bc", "b", -1)
    s.add_boundary_contact("cd", "d", +1)
    s.add_boundary_contact("cd", "c", -1)
    s.add_boundary_contact("da", "a", +1)
    s.add_boundary_contact("da", "d", -1)
    s.add_boundary_contact("be", "e", +1)
    s.add_boundary_contact("be", "b", -1)
    s.add_boundary_contact("ec", "c", +1)
    s.add_boundary_contact("ec", "e", -1)

    # X: ∂X = ab + bc + cd + da  (quadrilateral, counterclockwise)
    s.add_boundary_contact("X", "ab", +1)
    s.add_boundary_contact("X", "bc", +1)
    s.add_boundary_contact("X", "cd", +1)
    s.add_boundary_contact("X", "da", +1)

    # Y: ∂Y = be + ec − bc  (triangle b→e→c, with bc traversed backwards)
    # bc appears in ∂X (+1) and ∂Y (−1): the shared boundary arc.
    s.add_boundary_contact("Y", "be", +1)
    s.add_boundary_contact("Y", "ec", +1)
    s.add_boundary_contact("Y", "bc", -1)

    # Semantic overlap: X and Y share interior content.
    # This is the carrier for the overlap nerve computation.
    s.add_overlap("X", "Y")

    return s


def example_torus_regional() -> RegionalSystem:
    """
    A torus built from regional data (not simplicial).

    The minimal cell structure of a torus uses one 0-cell, two 1-cells,
    and one 2-cell with ∂F = a + b - a - b = 0.

    Expected: H_0 = Z, H_1 = Z^2, H_2 = Z
    """
    s = RegionalSystem("torus_regional")

    # Single vertex
    s.add_region("v", 0)

    # Two loops (both start and end at v)
    s.add_region("a", 1)
    s.add_region("b", 1)

    # Single face
    s.add_region("F", 2)

    # Loop boundaries: each loop starts and ends at v, so ∂ = v - v = 0
    s.add_boundary_contact("a", "v", +1)
    s.add_boundary_contact("a", "v", -1)
    s.add_boundary_contact("b", "v", +1)
    s.add_boundary_contact("b", "v", -1)

    # Face boundary: ∂F = a + b - a - b = 0
    # Standard: ∂F = a + b + a^{-1} + b^{-1}
    # In chain complex terms with abelian group: ∂F = a - a + b - b = 0
    s.add_boundary_contact("F", "a", +1)
    s.add_boundary_contact("F", "a", -1)
    s.add_boundary_contact("F", "b", +1)
    s.add_boundary_contact("F", "b", -1)

    return s


def example_pinched_regions() -> RegionalSystem:
    """
    NON-CLASSICAL: Three regions sharing a "pinch point."

    A single 0-region (the pinch) is the boundary contact for
    multiple 1-regions in a way that creates a non-manifold point.

    Think of three roads meeting at a roundabout where the roundabout
    is a single 0-dimensional point, not a region itself.
    """
    s = RegionalSystem("pinched_regions")

    # The pinch point
    s.add_region("O", 0)
    # Outer vertices
    s.add_region("a", 0)
    s.add_region("b", 0)
    s.add_region("c", 0)

    # Roads: three 1-regions from outer to pinch
    s.add_region("rA", 1)  # a -> O
    s.add_region("rB", 1)  # b -> O
    s.add_region("rC", 1)  # c -> O

    s.add_boundary_contact("rA", "O", +1)
    s.add_boundary_contact("rA", "a", -1)
    s.add_boundary_contact("rB", "O", +1)
    s.add_boundary_contact("rB", "b", -1)
    s.add_boundary_contact("rC", "O", +1)
    s.add_boundary_contact("rC", "c", -1)

    return s


def example_mobius_strip() -> RegionalSystem:
    """
    Möbius strip from rectangle identification.

    Take [0,1]×[0,1] and identify the left and right edges with a flip:
    (0,t) ~ (1,1-t). This is the standard Möbius construction.

    After identification the vertex classes are:
      v0 = {(0,0), (1,1)}   ("diagonal" corners)
      v1 = {(0,1), (1,0)}   ("anti-diagonal" corners)

    Three edges remain:
      btm  : bottom edge, v0 → v1  (unidentified)
      top  : top edge,    v1 → v0  (unidentified)
      side : v0 → v1  (left edge = right edge reversed, the twisted pair)

    Tracing the rectangle boundary counterclockwise gives:
      ∂F = btm − top − 2·side
    The coefficient −2 on side encodes the double traversal of the
    identified edge (once as the right side, once as the left side
    reversed). This is the algebraic footprint of the Möbius twist.

    Verification: ∂₁(∂₂(F)) = (v1−v0) − (v0−v1) − 2(v1−v0) = 0. ✓

    Expected homology (Möbius strip ≃ S¹):
      H₀ = Z   (connected)
      H₁ = Z   (generator = core circle = top + side)
      H₂ = 0   (non-orientable surface with boundary, no 2-cycles)
      Euler characteristic: V − E + F = 2 − 3 + 1 = 0

    The boundary circle (btm + top) represents 2 × [generator] in H₁,
    reflecting that the single boundary component wraps the core circle
    twice — the characteristic signature of the Möbius strip.
    """
    s = RegionalSystem("mobius_strip")

    # 0-dim: two vertex classes from the corner identification
    s.add_region("v0", 0)
    s.add_region("v1", 0)

    # 1-dim: three edges
    s.add_region("btm", 1)   # bottom: v0 → v1 (free boundary)
    s.add_region("side", 1)  # twisted side: v0 → v1 (left = right reversed)
    s.add_region("top", 1)   # top: v1 → v0 (free boundary)

    # 2-dim: the rectangular face
    s.add_region("F", 2)

    # Edge boundaries
    s.add_boundary_contact("btm", "v1", +1)
    s.add_boundary_contact("btm", "v0", -1)

    s.add_boundary_contact("top", "v0", +1)
    s.add_boundary_contact("top", "v1", -1)

    s.add_boundary_contact("side", "v1", +1)
    s.add_boundary_contact("side", "v0", -1)

    # Face boundary: ∂F = btm − top − 2·side
    # Coefficient −2 on side is achieved by calling twice with sign=−1;
    # the matrix builder accumulates via +=, matching the torus convention.
    s.add_boundary_contact("F", "btm", +1)
    s.add_boundary_contact("F", "top", -1)
    s.add_boundary_contact("F", "side", -1)  # first pass of twisted side
    s.add_boundary_contact("F", "side", -1)  # second pass (reversed) → net −2

    return s


def example_projective_plane() -> RegionalSystem:
    """
    Real projective plane RP² via Möbius strip + capping disk.

    Construction: RP² = Möbius strip ∪_∂ D²

    The boundary of the Möbius strip is a single circle that wraps
    the core twice. Gluing a disk (F_cap) along that circle closes
    the surface into RP².

    Regions — same skeleton as the Möbius strip, plus one face:
      0-dim: v0, v1  (vertex classes from the rectangle identification)
      1-dim: btm (v0→v1), side (v0→v1, twisted), top (v1→v0)
      2-dim: F_mob (the Möbius face), F_cap (the capping disk)

    Boundary maps:
      ∂(btm)  = v1 − v0
      ∂(top)  = v0 − v1
      ∂(side) = v1 − v0
      ∂(F_mob) = btm − top − 2·side   (Möbius twist, coefficient −2)
      ∂(F_cap) = btm + top            (caps the boundary circle)

    Verification:
      ∂₁(∂₂(F_mob)) = (v1−v0) − (v0−v1) − 2(v1−v0) = 0 ✓
      ∂₁(∂₂(F_cap)) = (v1−v0) + (v0−v1) = 0 ✓

    Expected homology over Z:
      H₀ = Z        (connected)
      H₁ = Z/2      (pure torsion — the hallmark of RP²)
      H₂ = 0        (non-orientable closed surface, no Z-fundamental class)
      Euler characteristic: V − E + F = 2 − 3 + 2 = 1
      Betti numbers: [1, 0, 0]   (torsion is invisible to free rank)

    The torsion Z/2 lives in the SNF of ∂₂: its diagonal contains the
    factor 2, arising because F_mob contributes −2·side while F_cap
    contributes 0·side. The 1-cycle (side + top) is killed by 2, not 1.

    Note on exactness: because β₁ = 0 (the torsion class has no free
    part), the closure defect exactness at dim 1 will read 1.000 —
    the torsion is invisible to that metric. The Z/2 is detectable
    only via the torsion field in the homology report.
    """
    s = RegionalSystem("projective_plane")

    # 0-dim
    s.add_region("v0", 0)
    s.add_region("v1", 0)

    # 1-dim
    s.add_region("btm", 1)   # v0 → v1  (free boundary edge)
    s.add_region("side", 1)  # v0 → v1  (twisted side, Möbius identification)
    s.add_region("top", 1)   # v1 → v0  (free boundary edge)

    # 2-dim
    s.add_region("F_cap", 2)  # capping disk glued to Möbius boundary
    s.add_region("F_mob", 2)  # Möbius face

    # Edge boundaries
    s.add_boundary_contact("btm", "v1", +1)
    s.add_boundary_contact("btm", "v0", -1)

    s.add_boundary_contact("top", "v0", +1)
    s.add_boundary_contact("top", "v1", -1)

    s.add_boundary_contact("side", "v1", +1)
    s.add_boundary_contact("side", "v0", -1)

    # F_mob: Möbius face — ∂F_mob = btm − top − 2·side
    s.add_boundary_contact("F_mob", "btm", +1)
    s.add_boundary_contact("F_mob", "top", -1)
    s.add_boundary_contact("F_mob", "side", -1)  # first pass
    s.add_boundary_contact("F_mob", "side", -1)  # second pass → net −2

    # F_cap: capping disk — ∂F_cap = btm + top  (the Möbius boundary circle)
    s.add_boundary_contact("F_cap", "btm", +1)
    s.add_boundary_contact("F_cap", "top", +1)

    return s


def example_klein_bottle() -> RegionalSystem:
    """
    Klein bottle via minimal CW structure.

    Polygon word: abab⁻¹ (identify opposite sides of a square: one pair
    in the same direction, one pair in opposite directions).

    Vertex count: all four corners of the square get identified → 1 vertex v.
    Edge count:   two edges a (horizontal loop) and b (vertical loop).
    Face count:   one face F.

    Euler characteristic: V − E + F = 1 − 2 + 1 = 0. ✓

    NOTE on cell counts: a 1v, 2e, 2F structure gives χ = 1 (= RP², not
    Klein bottle). To reach χ = 0 with only 2 edge-classes you need exactly
    1 face. The second face is unnecessary and changes the topology.

    Boundary maps:
      ∂(a) = v − v = 0   (a is a loop)
      ∂(b) = v − v = 0   (b is a loop)
      ∂(F) = 2a          (word abab⁻¹ abelianizes: a+b+a−b = 2a)

    The coefficient +2 on a is achieved by two add_boundary_contact(+1) calls.
    The edge b never appears in ∂(F), reflecting that the b-identification is
    orientation-reversing and cancels in the abelian group.

    Verification: ∂₁(∂₂(F)) = ∂₁(2a) = 2·0 = 0. ✓

    Expected homology over Z:
      H₀ = Z           (connected)
      H₁ = Z ⊕ Z/2     (free part from b; torsion from the 2a boundary)
      H₂ = 0           (non-orientable closed surface)
      Euler characteristic: 0
      Betti numbers: [1, 1, 0]

    SNF of ∂₂ = [[2],[0]] gives diagonal [2], revealing the torsion factor.
    Rank(∂₂) = 1, so im(∂₂) kills the a-direction, leaving b free and a/2a = Z/2.

    Exactness at dim 1:
      nullity(∂₁) = 2, β₁ = 1, exactness = 1 − 1/2 = 0.500.
      This drop from 1.000 (as in RP²) signals that one free cycle survives
      unfilled — the b-loop is genuinely non-bounding.

    Fullness gap:
      F is adjacent to a (via boundary) but NOT to b (b never appears in ∂F).
      Possible adjacencies: 2×1 + 1×2 = 4. Realised: 3. Saturation: 0.750.
      Compare torus (1.000): the Klein bottle's twist around b disconnects F
      from b in the regional adjacency graph.
    """
    s = RegionalSystem("klein_bottle")

    # 0-dim: single vertex (all four square corners identified)
    s.add_region("v", 0)

    # 1-dim: two loops
    s.add_region("a", 1)  # horizontal — appears twice in word, same direction
    s.add_region("b", 1)  # vertical — appears once forward, once backward (cancels)

    # 2-dim: single face
    s.add_region("F", 2)

    # Loop boundaries: ∂(a) = v − v = 0, ∂(b) = v − v = 0
    s.add_boundary_contact("a", "v", +1)
    s.add_boundary_contact("a", "v", -1)
    s.add_boundary_contact("b", "v", +1)
    s.add_boundary_contact("b", "v", -1)

    # Face boundary: ∂(F) = 2a
    # Word abab⁻¹ abelianizes to a + b + a − b = 2a.
    # Two +1 calls accumulate to net coefficient +2 on a; b gets 0.
    s.add_boundary_contact("F", "a", +1)
    s.add_boundary_contact("F", "a", +1)  # second pass → net +2

    return s


def example_genus2_surface() -> RegionalSystem:
    """
    Genus-2 surface (double torus) T² # T² via the "Glued Pair" construction.

    Construction: two punctured tori sewn along their boundary circles
    via a shared neck edge c.

    Each punctured torus contributes:
      - Two free loops: (a1, b1) for the first torus, (a2, b2) for the second
      - One face whose boundary IS the neck circle c

    The neck edge c is oriented so that ∂F1 = +c and ∂F2 = −c, making
    the combined surface F1 + F2 closed: ∂(F1+F2) = c − c = 0.

    Alternative — Octagon model (1v, 4e, 1F):
      ∂F = a1+b1−a1−b1+a2+b2−a2−b2 = 0 (same homology, χ=−2).
      Gives saturation 1.000 and redundancy 0.000 — like the torus.
      But hides the seam: the Glued Pair makes the connected-sum structure
      visible in the adjacency graph, which is more aligned with the
      point-free regional philosophy.

    Regions:
      0-dim: v  (single vertex, all loops based here)
      1-dim: a1, a2, b1, b2 (torus loops), c (neck seam)
      2-dim: F1 (first torus face, ∂F1 = c)
             F2 (second torus face, ∂F2 = −c)

    Euler characteristic: V − E + F = 1 − 5 + 2 = −2. ✓

    Boundary maps:
      ∂(a1) = ∂(b1) = ∂(a2) = ∂(b2) = ∂(c) = v − v = 0  (all loops)
      ∂(F1) = c
      ∂(F2) = −c

    Verification: ∂₁ = 0, so ∂₁ ∘ ∂₂ = 0 trivially. ✓

    Expected homology:
      H₀ = Z     (connected)
      H₁ = Z⁴    (four independent loops: a1, b1, a2, b2)
      H₂ = Z     (fundamental class = F1 + F2; closed orientable surface)
      Euler characteristic: χ = 1 − 4 + 1 = −2
      Betti numbers: [1, 4, 1]

    The neck edge c is killed in H₁: im(∂₂) spans the c-direction, so
    [c] = 0. The fundamental class F1 + F2 generates ker(∂₂) = Z = H₂.

    Key diagnostics (contrast with torus):
      Saturation: 7/15 ≈ 0.467
        The four loops a1,b1,a2,b2 have NO face adjacency — they don't
        appear in ∂F1 or ∂F2. Only c touches the faces, creating a large
        adjacency gap. (Torus: saturation 1.000.)
      Structural Redundancy: (8−6)/8 = 0.250
        The seam machinery (c and F2) contributes 2 generators beyond the
        Betti count. (Torus: 0.000. Octagon model: also 0.000.)
    """
    s = RegionalSystem("genus2_surface")

    # 0-dim: single vertex
    s.add_region("v", 0)

    # 1-dim: four torus loops plus neck seam
    s.add_region("a1", 1)   # first torus horizontal loop
    s.add_region("a2", 1)   # second torus horizontal loop
    s.add_region("b1", 1)   # first torus vertical loop
    s.add_region("b2", 1)   # second torus vertical loop
    s.add_region("c", 1)    # neck circle (shared seam)

    # 2-dim: one face per punctured torus
    s.add_region("F1", 2)   # first torus face — ∂F1 = c
    s.add_region("F2", 2)   # second torus face — ∂F2 = −c

    # All edges are loops: ∂(e) = v − v = 0
    for e in ("a1", "a2", "b1", "b2", "c"):
        s.add_boundary_contact(e, "v", +1)
        s.add_boundary_contact(e, "v", -1)

    # Face boundaries: glued along the neck with opposite orientations
    s.add_boundary_contact("F1", "c", +1)   # F1 bounded by +c
    s.add_boundary_contact("F2", "c", -1)   # F2 bounded by −c → F1+F2 is closed

    return s


# ---------------------------------------------------------------------------
# Falsification test helpers (not in ALL_EXAMPLES — used by main.py directly)
# ---------------------------------------------------------------------------

def example_torus_modified_attachment() -> RegionalSystem:
    """
    TEST A: Same 1-skeleton as torus_regional, different 2-cell attachment.

    The 1-skeleton is identical: one vertex v, two loops a and b.
    The difference is the face boundary word:

      torus_regional   uses aba⁻¹b⁻¹  →  abelianizes to  a+b−a−b = 0
      THIS example     uses abab⁻¹    →  abelianizes to  a+b+a−b = 2a ≠ 0

    Changing only the ∂F declaration changes ∂₂ from [[0],[0]] to [[2],[0]],
    and changes the homology from H₁=Z² (torus) to H₁=Z⊕Z/2 (Klein bottle).

    This proves the engine reads the declared boundary contacts, not just the
    1-skeleton. A system that defaulted ∂₂ to zero would be unable to produce
    this result from the same set of regions.
    """
    s = RegionalSystem("torus_modified_attachment")

    s.add_region("v", 0)
    s.add_region("a", 1)
    s.add_region("b", 1)
    s.add_region("F", 2)

    s.add_boundary_contact("a", "v", +1)
    s.add_boundary_contact("a", "v", -1)
    s.add_boundary_contact("b", "v", +1)
    s.add_boundary_contact("b", "v", -1)

    # DIFFERENT from torus: ∂F = 2a (Klein bottle word abab⁻¹ = a+b+a−b = 2a)
    s.add_boundary_contact("F", "a", +1)
    s.add_boundary_contact("F", "a", +1)  # second +1 → net coefficient +2

    return s


def example_torus_refined() -> RegionalSystem:
    """
    TEST B: Refined torus — nontrivial ∂₂ matrices with algebraic cancellation.

    Construction: split the torus square (word aba⁻¹b⁻¹) with a diagonal c,
    yielding two triangular faces F1 and F2.

    All three edges (a, b, c) are loops at the single vertex v (after the
    standard torus corner-identification all four corners collapse to one point).

    Boundary maps:
      ∂(a) = ∂(b) = ∂(c) = 0   (loops)
      ∂(F1) = a + b − c         (upper triangle: traverses a, b, then −c)
      ∂(F2) = −a − b + c        (lower triangle: traverses c, −b, −a... = −(a+b−c))

    ∂₂ matrix (rows = a, b, c; cols = F1, F2):
      [[ 1  −1]
       [ 1  −1]
       [−1  +1]]

    This is NOT the zero matrix. Each face has a genuine nonzero boundary.
    The cancellation that gives H₂ = Z happens algebraically via the SNF:
      rank(∂₂) = 1, ker(∂₂) = Z·(F1+F2) → H₂ = Z ✓
      im(∂₂) kills one generator in ker(∂₁) = Z³ → H₁ = Z² ✓

    Verification: ∂₁ ∘ ∂₂ = 0 (trivially, since ∂₁ = 0). ✓

    The result is the same as torus_regional — same Betti numbers [1, 2, 1]
    and χ = 0 — proving that the torus result is topologically robust, not
    an artifact of the one-vertex encoding.
    """
    s = RegionalSystem("torus_refined")

    s.add_region("v", 0)

    # Three edges — all loops after the torus corner identification
    s.add_region("a", 1)   # horizontal loop
    s.add_region("b", 1)   # vertical loop
    s.add_region("c", 1)   # diagonal loop (added by the refinement)

    # Two triangular faces from the split square
    s.add_region("F1", 2)  # upper triangle
    s.add_region("F2", 2)  # lower triangle

    for e in ("a", "b", "c"):
        s.add_boundary_contact(e, "v", +1)
        s.add_boundary_contact(e, "v", -1)

    # F1: ∂(F1) = a + b − c
    s.add_boundary_contact("F1", "a", +1)
    s.add_boundary_contact("F1", "b", +1)
    s.add_boundary_contact("F1", "c", -1)

    # F2: ∂(F2) = −a − b + c  (= −∂(F1), so F1+F2 is closed)
    s.add_boundary_contact("F2", "a", -1)
    s.add_boundary_contact("F2", "b", -1)
    s.add_boundary_contact("F2", "c", +1)

    return s


def example_solid_torus() -> RegionalSystem:
    """
    A solid torus (D² × S¹) built as the torus with its fundamental class filled.

    Start from torus_regional: one 0-cell v, two 1-cells a and b (loops),
    one 2-cell F with ∂F = 0 (the torus attaching map aba⁻¹b⁻¹ abelianizes
    to a - a + b - b = 0).

    Add a single 3-cell V with ∂V = F.  This kills the torus fundamental
    class [F] in H₂ while leaving the 1-skeleton untouched.

    Chain complex:
      C₃ = Z (V)  →  C₂ = Z (F)  →  C₁ = Z² (a,b)  →  C₀ = Z (v)
      ∂₃ = [[1]]        ∂₂ = [[0],[0]]       ∂₁ = [[0,0]]

    Homology:
      H₀ = Z                (one connected component)
      H₁ = Z²               (both loops a and b survive — no 2-cell fills either)
      H₂ = ker(∂₂)/im(∂₃) = Z/Z = 0  (V fills F)
      H₃ = ker(∂₃) = 0     (∂₃ is injective)

    Euler characteristic: χ = 1 − 2 + 1 − 1 = −1

    Note: H₁ = Z² rather than Z because neither loop is filled by a 2-cell.
    The solid torus in the classical sense has H₁ = Z (the meridian is filled
    by a disk); here no disk for b is declared, so both generators survive.
    This is the correct output of the declared regional system.
    """
    s = RegionalSystem("solid_torus")

    # 0-dim: single vertex (both loops based here)
    s.add_region("v", 0)

    # 1-dim: two loops
    s.add_region("a", 1)
    s.add_region("b", 1)

    # Loop boundaries: start and end at v, so ∂a = ∂b = v − v = 0
    s.add_boundary_contact("a", "v", +1)
    s.add_boundary_contact("a", "v", -1)
    s.add_boundary_contact("b", "v", +1)
    s.add_boundary_contact("b", "v", -1)

    # 2-dim: torus face with ∂F = 0 (aba⁻¹b⁻¹ → a − a + b − b = 0)
    s.add_region("F", 2)
    s.add_boundary_contact("F", "a", +1)
    s.add_boundary_contact("F", "a", -1)
    s.add_boundary_contact("F", "b", +1)
    s.add_boundary_contact("F", "b", -1)

    # 3-dim: volume cell whose boundary is F
    s.add_region("V", 3)
    s.add_boundary_contact("V", "F", +1)

    return s


def example_solid_ball() -> RegionalSystem:
    """
    A solid ball (D³) declared as a telescoping regional system.

    Construction: one vertex v, one loop edge e (∂e = 0), one disk face F
    with ∂F = e (fills the loop), one volume V with ∂V = F (fills the disk).

    This chain complex is algebraically invalid: ∂₂∘∂₃(V) = ∂₂(F) = e ≠ 0,
    so the thinness check fails.  The chain complex does not satisfy ∂∘∂ = 0
    because F is a disk (its boundary is e, a non-trivial 1-cycle), not a
    sphere (which would have ∂F = 0).  A 3-cell whose boundary is a disk, not
    a sphere, violates the chain condition.

    Despite the invalidity, the kernel-restriction method in compute_homology
    extracts the correct contractible homology:

      H₀ = Z, H₁ = 0, H₂ = 0, H₃ = 0

    Betti: [1, 0, 0, 0]
    Euler characteristic (from Betti): χ = 1

    Note on χ: the generator-count formula 1−1+1−1 = 0 and the Betti formula
    1−0+0−0 = 1 disagree here because the chain complex is invalid.  The
    Betti-based χ = 1 is correct for D³ (contractible, same as a point).
    is_valid will be False on output.
    """
    s = RegionalSystem("solid_ball")

    s.add_region("v", 0)

    # Loop edge: both endpoints at v, so ∂e = v − v = 0
    s.add_region("e", 1)
    s.add_boundary_contact("e", "v", +1)
    s.add_boundary_contact("e", "v", -1)

    # Disk face: ∂F = e  (fills the loop; makes the chain complex invalid)
    s.add_region("F", 2)
    s.add_boundary_contact("F", "e", +1)

    # Volume: ∂V = F
    s.add_region("V", 3)
    s.add_boundary_contact("V", "F", +1)

    return s


def example_ball_3() -> RegionalSystem:
    """
    A valid 3-ball (D³) using the minimal CW decomposition of its boundary.

    The boundary of D³ is S².  The minimal CW structure for S² uses a single
    0-cell v and a single 2-cell F attached via a constant map — meaning F
    has no 1-dimensional boundary contacts: ∂F = 0.  Adding a 3-cell V with
    ∂V = F then gives a valid chain complex because:

        ∂₂∘∂₃(V) = ∂₂(F) = 0  ✓

    No 1-cells are declared.  The boundary matrix ∂₂ is a 0×1 empty matrix
    (zero rows because n₁=0), and ∂₁ is a 1×0 empty matrix.  The composition
    ∂₁∘∂₂ and ∂₂∘∂₃ are both vacuously zero.

    This contrasts with solid_ball, which uses the telescoping construction
    (∂F=e, ∂V=F) and is invalid.  Both compute the same homology via
    kernel-restriction, but here the chain condition genuinely holds and the
    two χ formulas agree:

        χ(Betti) = 1−0+0−0 = 1
        χ(generators) = 1−0+1−1 = 1  ← both equal 1

    Homology: H₀ = Z, H₁ = 0, H₂ = 0, H₃ = 0
    Betti: [1, 0, 0, 0]   χ = 1   is_valid = True
    """
    s = RegionalSystem("ball_3")

    s.add_region("v", 0)

    # 2-cell with no boundary contacts: ∂F = 0  (S² in minimal CW form)
    s.add_region("F", 2)

    # Volume fills the S²: ∂V = F
    s.add_region("V", 3)
    s.add_boundary_contact("V", "F", +1)

    return s


def example_sphere_3d() -> RegionalSystem:
    """
    A 3-sphere (S³) declared as two solid balls glued along a shared face.

    Construction: one vertex v, one loop edge e, one face F with ∂F = e,
    two volumes V1 and V2 with ∂V1 = +F and ∂V2 = −F.

    Like solid_ball, this chain complex is algebraically invalid because
    ∂₂∘∂₃ = ∂₂([[+1,−1]]) = [[1,−1]] ≠ 0.  The shared face F is a disk
    (∂F = e ≠ 0), so the chain condition fails.

    The key algebraic fact: V1 + V2 is in ker(∂₃) because
    ∂₃(V1+V2) = F − F = 0.  No 4-cell bounds this cycle, so β₃ = 1 emerges.

    The kernel-restriction method extracts the correct homology:

      H₀ = Z, H₁ = 0, H₂ = 0, H₃ = Z

    Betti: [1, 0, 0, 1]
    Euler characteristic (from Betti): χ = 0  (correct for any odd-dimensional
    closed manifold; the generator-count formula gives −1, which is wrong here
    because the complex is invalid).
    is_valid will be False on output.
    """
    s = RegionalSystem("sphere_3d")

    s.add_region("v", 0)

    # Loop edge
    s.add_region("e", 1)
    s.add_boundary_contact("e", "v", +1)
    s.add_boundary_contact("e", "v", -1)

    # Shared face: ∂F = e
    s.add_region("F", 2)
    s.add_boundary_contact("F", "e", +1)

    # First volume: ∂V1 = +F
    s.add_region("V1", 3)
    s.add_boundary_contact("V1", "F", +1)

    # Second volume: ∂V2 = −F  (opposite orientation)
    # V1 + V2 is a 3-cycle: ∂₃(V1+V2) = F − F = 0
    s.add_region("V2", 3)
    s.add_boundary_contact("V2", "F", -1)

    return s


def example_solid_book() -> RegionalSystem:
    """
    NON-MANIFOLD: Three 3-cells sharing a single 2-cell spine.

    A standard manifold constraint is that every (n-1)-face is shared by
    exactly two n-cells.  Here, three volumes V1, V2, V3 all declare the
    same face F as their boundary.  This violates the manifold property at F
    — F is a junction for three rooms, not two.

    Construction: v (0-dim), e (1-dim loop), F (2-dim, ∂F=e),
    V1/V2/V3 (3-dim, all ∂Vi=+F).

    Chain complex matrices:
      ∂₁ = [[0]]        (e is a loop)
      ∂₂ = [[1]]        (∂F = e)
      ∂₃ = [[1, 1, 1]]  (all three volumes map to the same face)

    Thinness: ∂₂∘∂₃ = [[1]]@[[1,1,1]] = [[1,1,1]] ≠ 0.
    The complex is invalid (is_valid=False) for the same reason as solid_ball
    and sphere_3d: the spine F is a disk (∂F=e≠0), not a sphere.

    Despite the invalidity, kernel-restriction extracts the correct answer.
    rank(∂₃) = 1, nullity(∂₃) = 2.  The two independent 3-cycles are
    V1−V2 and V2−V3.  No 4-cells fill them.

    Homology:
      H₀ = Z, H₁ = 0, H₂ = 0, H₃ = Z²

    Betti: [1, 0, 0, 2]
    Euler characteristic (from Betti): χ = 1−0+0−2 = −1
    """
    s = RegionalSystem("solid_book")

    s.add_region("v", 0)

    s.add_region("e", 1)
    s.add_boundary_contact("e", "v", +1)
    s.add_boundary_contact("e", "v", -1)

    # Spine face: ∂F = e
    s.add_region("F", 2)
    s.add_boundary_contact("F", "e", +1)

    # Three volumes, all bounding the same spine
    for name in ("V1", "V2", "V3"):
        s.add_region(name, 3)
        s.add_boundary_contact(name, "F", +1)

    return s


def example_lens_space_3_1() -> RegionalSystem:
    """
    Lens space L(3,1): a valid closed 3-manifold with H₁ = Z/3Z torsion.

    L(p, q) is a closed orientable 3-manifold.  The minimal CW structure for
    L(p, 1) uses a single loop a, a face F attached with winding number p,
    and a closed volume V.

    Construction:
      v  (0-dim): single vertex
      a  (1-dim): loop at v,  ∂a = 0
      F  (2-dim): face with ∂F = 3a  (triple wrap)
      V  (3-dim): no boundary contacts,  ∂V = 0  (closed fundamental class)

    The triple wrap is implemented via three separate add_boundary_contact
    calls each with sign +1.  boundary.py sums the signs (+=), giving
    the (F, a) entry of ∂₂ a value of 3.

    Chain complex matrices:
      ∂₁ = [[0]]    (a is a loop)
      ∂₂ = [[3]]    (∂F = 3a — winding number 3)
      ∂₃ = [[0]]    (∂V = 0 — V is a closed fundamental class)

    Thinness:
      ∂₁∘∂₂ = [[0]]@[[3]] = [[0]]  HOLDS
      ∂₂∘∂₃ = [[3]]@[[0]] = [[0]]  HOLDS
      is_valid = True — this is a valid chain complex.

    Homology:
      H₀ = Z      (connected)
      H₁ = Z/3Z   (ker([[0]])/im([[3]]) = Z/3Z — torsion from the wrap)
      H₂ = 0      (ker([[3]]) = 0, no non-trivial 2-cycles)
      H₃ = Z      (ker([[0]]) = Z, V is a free 3-cycle)

    Betti: [1, 0, 0, 1]   torsion: H₁ has invariant factor 3
    Euler characteristic: χ = 0  (correct for any odd-dim closed manifold)

    The factor of 3 sits on the SNF diagonal unchanged — [[3]] is already
    diagonal — and is read directly as the torsion invariant factor.
    """
    s = RegionalSystem("lens_3_1")

    s.add_region("v", 0)

    s.add_region("a", 1)
    s.add_boundary_contact("a", "v", +1)
    s.add_boundary_contact("a", "v", -1)

    # Triple-wrapped face: ∂F = 3a
    # Three separate contacts; boundary.py accumulates them to coefficient 3.
    s.add_region("F", 2)
    s.add_boundary_contact("F", "a", +1)
    s.add_boundary_contact("F", "a", +1)
    s.add_boundary_contact("F", "a", +1)

    # Volume with no boundary contacts: ∂V = 0
    s.add_region("V", 3)

    return s


ALL_EXAMPLES = {
    "triangle_classical": example_triangle_classical,
    "loop_no_fill": example_loop_no_fill,
    "triple_junction": example_triple_junction,
    "thick_boundary": example_thick_boundary,
    "overlapping_regions": example_overlapping_regions,
    "torus_regional": example_torus_regional,
    "solid_torus": example_solid_torus,
    "solid_ball": example_solid_ball,
    "ball_3": example_ball_3,
    "sphere_3d": example_sphere_3d,
    "solid_book": example_solid_book,
    "lens_3_1": example_lens_space_3_1,
    "pinched_regions": example_pinched_regions,
    "mobius_strip": example_mobius_strip,
    "projective_plane": example_projective_plane,
    "klein_bottle": example_klein_bottle,
    "genus2_surface": example_genus2_surface,
}
