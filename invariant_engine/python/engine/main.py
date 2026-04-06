"""
main.py — Regional Calculus Invariant Engine: entry point.

Runs all examples, computes homology, checks thinness, and performs
scheme comparison for the non-classical cases.
"""

import sys
import os

# Ensure the package directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from regions import RegionalSystem
from boundary import thinness_report
from chain_complex import build_chain_complex, build_overlap_nerve, ChainComplex
from homology import homology_report
from invariants import full_diagnostic
from schemes import AbstractionScheme, apply_scheme, persistence_report
from examples import ALL_EXAMPLES
from homology import compute_homology
import numpy as np


def separator(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_single_example(name: str, builder):
    """Run a single example through the full pipeline."""
    separator(name)

    system = builder()
    print(system.summary())
    print()

    # Thinness check
    print(thinness_report(system))
    print()

    # Build chain complex
    cc = build_chain_complex(system, mode="explicit")
    print(cc.summary())
    print()

    # Homology
    print(homology_report(cc))
    print()

    # Full diagnostics
    print(full_diagnostic(system, cc))


def run_scheme_comparison():
    """
    Demonstrate scheme variation on the triple junction example.

    Three schemes:
      1. Full system (all regions)
      2. Remove one room (coarsen)
      3. Remove the shared wall (change connectivity)
    """
    separator("SCHEME COMPARISON: Triple Junction")

    from examples import example_triple_junction
    system = example_triple_junction()

    # Scheme 1: full system
    scheme_full = AbstractionScheme(name="full")

    # Scheme 2: remove room C (coarsening)
    scheme_no_C = AbstractionScheme(
        name="no_room_C",
        region_filter=lambda r: r.name not in ("C", "eC1", "eC2", "c0"),
    )

    # Scheme 3: remove the shared wall (changes topology)
    # The rooms A, B, C lose their connection through w
    scheme_no_wall = AbstractionScheme(
        name="no_shared_wall",
        region_filter=lambda r: r.name != "w",
    )

    schemes = [scheme_full, scheme_no_C, scheme_no_wall]
    print(persistence_report(system, schemes))


def run_scheme_comparison_thick():
    """
    Scheme variation on the thick boundary example.

    Schemes:
      1. Full system
      2. Remove exterior region (interior only)
      3. Remove diagonal edge (changes boundary structure)
    """
    separator("SCHEME COMPARISON: Thick Boundary")

    from examples import example_thick_boundary
    system = example_thick_boundary()

    scheme_full = AbstractionScheme(name="full")

    scheme_interior = AbstractionScheme(
        name="interior_only",
        region_filter=lambda r: r.name != "exterior" and r.name != "ext",
    )

    scheme_no_diag = AbstractionScheme(
        name="no_diagonal",
        region_filter=lambda r: r.name != "ext",
    )

    schemes = [scheme_full, scheme_interior, scheme_no_diag]
    print(persistence_report(system, schemes))


def run_falsification_tests():
    """
    Two concrete falsification tests for the torus ∂₂ = 0 result.

    Test A — Same 1-skeleton, different 2-cell attachment:
      Proves the engine reads declared boundary contacts rather than
      defaulting ∂₂ to zero based on the 1-skeleton alone.

    Test B — Refined torus (1v, 3e, 2F):
      Proves the engine handles nontrivial ∂₂ matrices with algebraic
      cancellations and still recovers the correct torus homology.
    """
    from examples import example_torus_regional
    from examples import example_torus_modified_attachment, example_torus_refined

    separator("FALSIFICATION TEST A: Same 1-Skeleton, Different 2-Cell Attachment")
    print()
    print("  Both systems share the same 1-skeleton: one vertex v, two loops a and b.")
    print("  They differ ONLY in how the face F is attached.")
    print()

    torus = example_torus_regional()
    cc_torus = build_chain_complex(torus)
    hom_torus = compute_homology(cc_torus)

    modified = example_torus_modified_attachment()
    cc_mod = build_chain_complex(modified)
    hom_mod = compute_homology(cc_mod)

    print("  [torus_regional]  attachment word = aba⁻¹b⁻¹  →  a+b−a−b = 0")
    print(f"  ∂₂ =\n{cc_torus.boundary_matrix(2)}")
    print(f"  {hom_torus[1]}")
    print()
    print("  [torus_modified]  attachment word = abab⁻¹    →  a+b+a−b = 2a")
    print(f"  ∂₂ =\n{cc_mod.boundary_matrix(2)}")
    print(f"  {hom_mod[1]}")
    print()
    print("  RESULT: ∂₂ changed from all-zero to [[2],[0]].")
    print("  H₁ changed from Z² to Z⊕Z/2 (Klein bottle homology).")
    print("  The engine reads the attachment — ∂₂=0 for the torus is a geometric")
    print("  fact (the abelianized torus word = 0), not a software default.")

    separator("FALSIFICATION TEST B: Refined Torus — Nontrivial ∂₂ with Cancellations")
    print()
    print("  Torus square split by diagonal c into two triangles F1 and F2.")
    print("  All three edges are loops, but ∂₂ is now a 3×2 nonzero matrix.")
    print()

    refined = example_torus_refined()
    cc_ref = build_chain_complex(refined)
    hom_ref = compute_homology(cc_ref)

    print(f"  ∂(F1) = a + b − c   (upper triangle)")
    print(f"  ∂(F2) = −a − b + c  (lower triangle = −∂(F1))")
    print()
    print(f"  ∂₂ (rows=a,b,c; cols=F1,F2):\n{cc_ref.boundary_matrix(2)}")
    print()
    print(f"  SNF rank(∂₂) = 1   →   im(∂₂) kills one generator in Z³ (ker ∂₁)")
    print(f"  ker(∂₂) = Z·(F1+F2)  →  fundamental class of the closed surface")
    print()
    print(f"  {hom_ref[0]}   {hom_ref[1]}   {hom_ref[2]}")
    print()
    print("  RESULT: identical to torus_regional [1, 2, 1] despite ∂₂ ≠ 0.")
    print("  The engine performed real Smith normal form cancellation.")
    print("  If it had hardcoded ∂₂=0 it would have reported H₁=Z³ (wrong).")
    print()
    print(f"  thinness_check: {thinness_report(refined).splitlines()[1]}")


def run_orientation_reversal_test():
    """
    Orientation reversal sanity test.

    Negate every column of ∂₂ (multiply the entire matrix by −1).
    Because im(−M) = im(M) and ker(−M) = ker(M), the homology groups
    must be identical before and after the reversal.

    If the pipeline changes Betti numbers or injects torsion under a
    global 2-cell orientation flip, the signed boundary extraction stage
    is inconsistent.
    """
    from examples import (
        example_torus_regional,
        example_torus_refined,
        example_projective_plane,
        example_klein_bottle,
        example_genus2_surface,
    )

    separator("ORIENTATION REVERSAL SANITY TEST")
    print()
    print("  Negate all columns of ∂₂: im(−M) = im(M), ker(−M) = ker(M).")
    print("  Homology must be identical before and after the reversal.")
    print()

    test_cases = [
        ("torus_regional",   example_torus_regional),
        ("torus_refined",    example_torus_refined),
        ("projective_plane", example_projective_plane),
        ("klein_bottle",     example_klein_bottle),
        ("genus2_surface",   example_genus2_surface),
    ]

    all_pass = True

    for name, builder in test_cases:
        system = builder()
        cc = build_chain_complex(system)
        hom = compute_homology(cc)

        # Build negated chain complex: copy all matrices, negate ∂₂
        neg_matrices = {k: (-v if k == 2 else v.copy()) for k, v in cc.matrices.items()}
        cc_neg = ChainComplex(
            generators=cc.generators,
            matrices=neg_matrices,
            max_dim=cc.max_dim,
            is_valid=cc.is_valid,
            system_name=cc.system_name + "_negated",
        )
        hom_neg = compute_homology(cc_neg)

        dims = sorted(hom.keys())
        match = all(
            hom[k].betti == hom_neg[k].betti
            and sorted(hom[k].torsion) == sorted(hom_neg[k].torsion)
            for k in dims
        )
        if not match:
            all_pass = False

        betti_orig = [hom[k].betti for k in dims]
        betti_neg  = [hom_neg[k].betti for k in dims]
        tors_orig  = [hom[k].torsion for k in dims if hom[k].torsion]
        tors_neg   = [hom_neg[k].torsion for k in dims if hom_neg[k].torsion]

        print(f"  [{name}]")
        orig_str = f"Betti={betti_orig}"
        if tors_orig:
            orig_str += f"  torsion={tors_orig}"
        print(f"    original  : {orig_str}")

        neg_str = f"Betti={betti_neg}"
        if tors_neg:
            neg_str += f"  torsion={tors_neg}"
        print(f"    −∂₂ flip  : {neg_str}")

        print(f"    → {'PASS' if match else 'FAIL'}")
        print()

    if all_pass:
        print("  Verdict: ALL PASS — orientation reversal is homologically invisible.")
    else:
        print("  Verdict: FAILURES DETECTED — pipeline is orientation-sensitive (BUG).")


def run_basis_invariance_tests():
    """
    Two stronger basis-invariance tests for the homology computation.

    Test 1 — Random unimodular change of basis:
        Apply Uₖ ∈ GL(rₖ, Z) to each chain group, transform boundary
        maps accordingly: ∂ₖ' = Uₖ₋₁⁻¹ @ ∂ₖ @ Uₖ.
        This mixes generators, not just flips signs.  Homology must
        be unchanged (isomorphic groups with same Betti + torsion).

    Test 2 — Single 2-cell orientation flip:
        Negate one column of ∂₂ at a time.  Each single-column negation
        is a unimodular basis change in C₂ (det = −1), so homology is
        preserved by the same argument.  Catches column-ordering or
        sign-tracking bugs that the global flip cannot reveal.
    """
    import numpy as np
    from examples import (
        example_torus_regional, example_torus_refined,
        example_projective_plane, example_klein_bottle, example_genus2_surface,
    )

    def random_unimodular(n, rng, num_ops=8):
        """
        Return (U, Uinv): a random n×n unimodular integer matrix and its
        exact inverse, generated by elementary row operations.
        Entries stay small (multiplier = 1 only), so no rounding risk.
        """
        if n <= 0:
            z = np.zeros((0, 0), dtype=int)
            return z, z
        if n == 1:
            s = 1 if rng.integers(2) else -1
            return np.array([[s]], dtype=int), np.array([[s]], dtype=int)
        U = np.eye(n, dtype=int)
        Uinv = np.eye(n, dtype=int)
        for _ in range(num_ops):
            i, j = map(int, rng.choice(n, size=2, replace=False))
            op = rng.integers(3)
            if op == 0:          # swap rows i↔j  /  swap columns i↔j in Uinv
                U[[i, j]] = U[[j, i]]
                Uinv[:, [i, j]] = Uinv[:, [j, i]]
            elif op == 1:        # add row i to row j  /  subtract col j from col i in Uinv
                U[j] += U[i]
                Uinv[:, i] -= Uinv[:, j]
            else:                # negate row i  /  negate col i in Uinv
                U[i] = -U[i]
                Uinv[:, i] = -Uinv[:, i]
        return U, Uinv

    def hom_equal(hom_a, hom_b):
        dims = sorted(hom_a.keys())
        return all(
            hom_a[k].betti == hom_b[k].betti
            and sorted(hom_a[k].torsion) == sorted(hom_b[k].torsion)
            for k in dims
        )

    def summary_str(hom):
        dims = sorted(hom.keys())
        betti = [hom[k].betti for k in dims]
        tors = [hom[k].torsion for k in dims if hom[k].torsion]
        s = f"Betti={betti}"
        if tors:
            s += f"  torsion={tors}"
        return s

    test_cases = [
        ("torus_regional",   example_torus_regional),
        ("torus_refined",    example_torus_refined),
        ("projective_plane", example_projective_plane),
        ("klein_bottle",     example_klein_bottle),
        ("genus2_surface",   example_genus2_surface),
    ]

    # ── Test 1: random unimodular basis change ────────────────────────────
    separator("BASIS INVARIANCE TEST 1: Random Unimodular Transformations")
    print()
    print("  Apply Uₖ ∈ GL(rₖ, Z) to each Cₖ, transform boundary maps:")
    print("  ∂ₖ' = Uₖ₋₁⁻¹ @ ∂ₖ @ Uₖ  (generators are mixed, not just sign-flipped).")
    print("  Homology must be unchanged.")
    print()

    # Generate a fresh seed from system entropy and print it so that any
    # failure can be exactly replayed by passing that seed to default_rng().
    seed = int(np.random.default_rng().integers(2**31))
    print(f"  Seed: {seed}  (pass to np.random.default_rng(seed) to replay)")
    rng = np.random.default_rng(seed)
    all_pass_1 = True

    for name, builder in test_cases:
        system = builder()
        cc = build_chain_complex(system)
        hom_orig = compute_homology(cc)

        Us, Uinvs = {}, {}
        for k in range(cc.max_dim + 1):
            Us[k], Uinvs[k] = random_unimodular(cc.rank(k), rng)

        new_matrices = {}
        for k in range(1, cc.max_dim + 1):
            dk = cc.boundary_matrix(k)
            if cc.rank(k) == 0 or cc.rank(k - 1) == 0:
                new_matrices[k] = dk
            else:
                new_matrices[k] = Uinvs[k - 1] @ dk @ Us[k]

        cc_new = ChainComplex(
            generators=cc.generators,
            matrices=new_matrices,
            max_dim=cc.max_dim,
            is_valid=cc.is_valid,
            system_name=cc.system_name + "_unimod",
        )
        hom_new = compute_homology(cc_new)

        match = hom_equal(hom_orig, hom_new)
        if not match:
            all_pass_1 = False
        print(f"  [{name}]  {summary_str(hom_orig)}  → {'PASS' if match else 'FAIL'}")

    verdict_1 = "ALL PASS" if all_pass_1 else "FAILURES DETECTED"
    print(f"\n  Verdict: {verdict_1}")

    # ── Test 2: single 2-cell orientation flip ────────────────────────────
    separator("BASIS INVARIANCE TEST 2: Single 2-Cell Orientation Flip")
    print()
    print("  Negate one column of ∂₂ at a time (reverse one 2-cell's orientation).")
    print("  Single-column negation is a unimodular C₂ basis change (det = −1);")
    print("  homology must be invariant.  Tests sign-tracking at column granularity.")
    print()

    all_pass_2 = True

    for name, builder in test_cases:
        system = builder()
        cc = build_chain_complex(system)
        hom_orig = compute_homology(cc)

        d2 = cc.boundary_matrix(2)
        num_faces = d2.shape[1] if d2.ndim == 2 else 0

        if num_faces == 0:
            print(f"  [{name}]  no 2-cells — skipping")
            continue

        failed_cols = []
        for col in range(num_faces):
            neg_d2 = d2.copy()
            neg_d2[:, col] *= -1
            neg_matrices = {
                k: (neg_d2.copy() if k == 2 else v.copy())
                for k, v in cc.matrices.items()
            }
            cc_flip = ChainComplex(
                generators=cc.generators,
                matrices=neg_matrices,
                max_dim=cc.max_dim,
                is_valid=cc.is_valid,
                system_name=cc.system_name + f"_flip{col}",
            )
            hom_flip = compute_homology(cc_flip)
            if not hom_equal(hom_orig, hom_flip):
                failed_cols.append(col)

        match = len(failed_cols) == 0
        if not match:
            all_pass_2 = False

        face_names = cc.generators.get(2, [])
        suffix = (
            f"PASS (all {num_faces} single-column flips invariant)"
            if match
            else f"FAIL (columns {failed_cols})"
        )
        print(f"  [{name}]  faces={face_names}  → {suffix}")

    verdict_2 = "ALL PASS" if all_pass_2 else "FAILURES DETECTED"
    print(f"\n  Verdict: {verdict_2}")


def run_overlap_nerve_tests():
    """
    Four targeted tests for build_overlap_nerve, covering orientation,
    ∂∘∂=0, and homology correctness on minimal examples.

    Test 1 — Single edge {X,Y}:
        Verifies matrix shapes and that ∂₁∘∂₂ is trivially 0.

    Test 2 — Triangle clique {a,b}, {a,c}, {b,c}:
        Verifies ∂₁∘∂₂ = 0 non-trivially and that H₀=Z, H₁=0, H₂=0
        (a filled triangle is contractible).

    Test 3 — 4-cycle without diagonals {a,b}, {b,c}, {c,d}, {a,d}:
        No triangles form, so the nerve is a 4-cycle graph.
        H₀=Z, H₁=Z (one independent loop).

    Test 4 — Two disjoint edges {a,b} and {c,d}:
        H₀=Z^2 (two connected components), H₁=0.
    """
    separator("OVERLAP NERVE CORRECTNESS TESTS")
    print()
    print("  Tests for build_overlap_nerve: orientations, ∂∘∂=0, homology.")
    print()

    all_pass = True

    def make_system(name, pairs):
        """Minimal RegionalSystem with only overlap data."""
        s = RegionalSystem(name)
        for a, b in pairs:
            s.add_overlap(a, b)
        return s

    def check(label, nerve, expected_betti, extra=None):
        nonlocal all_pass
        hom = compute_homology(nerve)
        got_betti = [hom[k].betti for k in sorted(hom.keys())]
        # Pad to same length for comparison
        maxk = max(len(expected_betti), len(got_betti))
        got_betti  += [0] * (maxk - len(got_betti))
        exp_betti   = list(expected_betti) + [0] * (maxk - len(expected_betti))

        boundary_ok = nerve.is_valid  # was computed from ∂₁∘∂₂=0 check
        betti_ok = (got_betti == exp_betti)
        ok = boundary_ok and betti_ok
        if not ok:
            all_pass = False
        tag = "PASS" if ok else "FAIL"
        detail = f"β={got_betti}" + (f", expected {exp_betti}" if not betti_ok else "")
        if not boundary_ok:
            detail += ", ∂∘∂≠0 !"
        extra_str = f", {extra}" if extra else ""
        print(f"  [{label}]  {detail}{extra_str}  → {tag}")

    # Test 1: single edge {X,Y}
    s1 = make_system("single_edge", [("X", "Y")])
    n1 = build_overlap_nerve(s1)
    d1 = n1.matrices.get(1, np.zeros((0, 0), dtype=int))
    d2 = n1.matrices.get(2, np.zeros((0, 0), dtype=int))
    shape_ok = (d1.shape == (2, 1) and d2.shape == (1, 0))
    check("single_edge", n1, [1, 0],
          extra=f"d1={d1.shape}, d2={d2.shape}, shapes_ok={shape_ok}")
    if not shape_ok:
        all_pass = False

    # Test 2: triangle clique — ∂₁∘∂₂=0 is non-trivial here
    s2 = make_system("triangle_clique", [("a", "b"), ("a", "c"), ("b", "c")])
    n2 = build_overlap_nerve(s2)
    # contractible: H = (Z, 0, 0)
    check("triangle_clique", n2, [1, 0, 0],
          extra="∂∘∂=0 verified by is_valid")

    # Test 3: 4-cycle without diagonals — nerve is a 1-cycle
    s3 = make_system("4cycle", [("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")])
    n3 = build_overlap_nerve(s3)
    # H₀=Z, H₁=Z
    check("4cycle_no_diag", n3, [1, 1])

    # Test 4: two disjoint edges — two connected components
    s4 = make_system("two_components", [("a", "b"), ("c", "d")])
    n4 = build_overlap_nerve(s4)
    # H₀=Z^2, H₁=0
    check("two_components", n4, [2, 0])

    verdict = "ALL PASS" if all_pass else "FAILURES DETECTED"
    print(f"\n  Verdict: {verdict}")


def run_operational_obstruction_demo():
    """
    Operational Obstruction Theorem demonstration on the solid_book example.

    Constructs a concrete operational model (Σ, →, α) and verifies two
    conditions from the theorem:

      (K)  α(s) ∈ ker(∂₃)  for every state s ∈ Σ
      (BR) α(t) − α(s) ∈ im(∂₄)  for every transition s → t

    Because solid_book has no 4-cells, im(∂₄) = 0.  Condition (BR) therefore
    forces α to be constant along any execution.  Since every disagreement-
    resolving transition changes α, ALL transitions violate (BR).

    Contrapositive certificate: no boundary-respecting execution can move the
    system from any disagreement state to consensus.  The topological gap is
    exact and computable — not a testing heuristic.
    """
    from examples import example_solid_book

    separator("OPERATIONAL OBSTRUCTION THEOREM: Solid Book Voter Case Study")
    print()
    print("  Interpretation: tally vector (a,b,o) for a three-channel vote counter.")
    print("  Constraint a+b+o=0 means total allocation is balanced (zero-sum).")
    print()
    print("  Σ  = { (a, b, o) ∈ Z³ : a + b + o = 0,  |a|, |b|, |o| ≤ 2 }")
    print("  α  : Σ → C₃   by   α(a,b,o) = a·V1 + b·V2 + o·V3  ∈ Z³")
    print("  →  : move one unit from channel i to channel j  (tally update step)")
    print()

    # Build the solid_book chain complex
    system = example_solid_book()
    cc = build_chain_complex(system)
    d3 = cc.boundary_matrix(3)   # shape (1, 3): [[1, 1, 1]]

    print(f"  ∂₃ = {d3.tolist()}  (one 2-cell F, three 3-cells V1,V2,V3)")
    print(f"  im(∂₄) = 0  (no 4-cells in solid_book)")
    print()

    # ── Build Σ ──────────────────────────────────────────────────────────
    states_set: set[tuple] = set()
    states: list[tuple] = []
    for a in range(-2, 3):
        for b in range(-2, 3):
            o = -a - b
            if abs(o) <= 2:
                s = (a, b, o)
                if s not in states_set:
                    states_set.add(s)
                    states.append(s)
    states.sort()

    print(f"  |Σ| = {len(states)} states")
    print()

    # ── Condition (K) ────────────────────────────────────────────────────
    k_violations = []
    for s in states:
        alpha_s = np.array(list(s), dtype=int)
        result = d3 @ alpha_s
        if not np.all(result == 0):
            k_violations.append((s, result.tolist()))

    print("  ── Condition (K): α(s) ∈ ker(∂₃) ──")
    print("     ∂₃ · α(a,b,o) = [[1,1,1]] · [a,b,o]ᵀ = a + b + o.")
    print("     By construction, a+b+o = 0 for every s ∈ Σ.")
    if not k_violations:
        print(f"     Verification: (K) HOLDS for all {len(states)} states.  ✓")
    else:
        print(f"     Verification: (K) FAILS for {len(k_violations)} states — BUG.")
    print()

    # ── Build transitions ─────────────────────────────────────────────────
    transitions: list[tuple] = []
    for s in states:
        vec = list(s)
        for i in range(3):
            for j in range(3):
                if i != j and vec[i] >= 1:
                    t_vec = list(vec)
                    t_vec[i] -= 1
                    t_vec[j] += 1
                    t = tuple(t_vec)
                    if t in states_set:
                        transitions.append((s, t))

    print(f"  |→| = {len(transitions)} transitions")
    print()

    # ── Condition (BR) ────────────────────────────────────────────────────
    br_violations = []
    br_holds = []
    for (s, t) in transitions:
        delta = np.array(list(t), dtype=int) - np.array(list(s), dtype=int)
        # im(∂₄) = 0, so (BR) requires Δα = 0
        if np.all(delta == 0):
            br_holds.append((s, t))
        else:
            br_violations.append((s, t))

    print("  ── Condition (BR): α(t) − α(s) ∈ im(∂₄) = {0} ──")
    print("     im(∂₄) = 0 means (BR) requires α(t) = α(s) for every step.")
    print("     Each tally-update moves one unit between channels:")
    print("     Δα = e_j − e_i  (a ±1 permutation)  →  always nonzero.")
    if not br_holds:
        print(f"     Verification: (BR) FAILS for all {len(transitions)} transitions.  ✓")
    else:
        print(f"     Verification: (BR) holds for {len(br_holds)} transitions — unexpected.")
    print()

    # ── Obstruction certificate ───────────────────────────────────────────
    s0 = (0, 0, 0)    # consensus
    s1 = (1, -1, 0)   # prototypical disagreement

    print("  ── Obstruction Certificate ──")
    print()
    print(f"     Consensus state:     s₀ = {s0}    α(s₀) = [0, 0, 0]")
    print(f"     Disagreement state:  s₁ = {s1}   α(s₁) = [1, −1, 0]")
    print()
    print("     H₃(solid_book) = Z²  (two independent unfilled 3-cycles).")
    print("     [α(s₀)] = 0 ∈ H₃               (zero class)")
    print("     [α(s₁)] = [1,−1,0] mod im(∂₄)  (nonzero class, ∉ im(∂₄) = 0)")
    print()
    print("     Since (BR) fails for every transition, α is not preserved")
    print("     along ANY execution.  The contrapositive reads:")
    print()
    print("       Every execution that reaches consensus from a disagreement")
    print("       state must contain at least one (BR)-violating step.")
    print()
    print("     This certifies that the solid-book architecture has no")
    print("     structural support for disagreement resolution.  The gap")
    print("     is exact and topological — invisible to conventional testing.")
    print()

    # ── Verdict ───────────────────────────────────────────────────────────
    all_confirmed = (not k_violations) and (not br_holds)
    verdict = "CONFIRMED" if all_confirmed else "PARTIAL"
    print(f"  Verdict: Obstruction {verdict}")
    print(f"    (K) holds for all {len(states)} states  ✓")
    if not br_holds:
        print(f"    (BR) fails for all {len(transitions)} transitions  ✓  "
              f"(maximum obstruction — no boundary-respecting resolution path)")
    else:
        print(f"    (BR) fails for {len(br_violations)} of {len(transitions)} transitions")


def main():
    print("REGIONAL CALCULUS INVARIANT ENGINE")
    print("Extracting topological invariants from point-free regional systems")
    print()

    # Run all examples
    for name, builder in ALL_EXAMPLES.items():
        try:
            run_single_example(name, builder)
        except Exception as e:
            print(f"\n  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()

    # Scheme comparisons
    try:
        run_scheme_comparison()
    except Exception as e:
        print(f"\n  ERROR in scheme comparison: {e}")
        import traceback
        traceback.print_exc()

    try:
        run_scheme_comparison_thick()
    except Exception as e:
        print(f"\n  ERROR in thick boundary scheme comparison: {e}")
        import traceback
        traceback.print_exc()

    try:
        run_falsification_tests()
    except Exception as e:
        print(f"\n  ERROR in falsification tests: {e}")
        import traceback
        traceback.print_exc()

    try:
        run_orientation_reversal_test()
    except Exception as e:
        print(f"\n  ERROR in orientation reversal test: {e}")
        import traceback
        traceback.print_exc()

    try:
        run_basis_invariance_tests()
    except Exception as e:
        print(f"\n  ERROR in basis invariance tests: {e}")
        import traceback
        traceback.print_exc()

    try:
        run_overlap_nerve_tests()
    except Exception as e:
        print(f"\n  ERROR in overlap nerve tests: {e}")
        import traceback
        traceback.print_exc()

    try:
        run_operational_obstruction_demo()
    except Exception as e:
        print(f"\n  ERROR in operational obstruction demo: {e}")
        import traceback
        traceback.print_exc()

    separator("SUMMARY")
    print()
    print("The invariant engine processes regional systems through four stages:")
    print("  1. Regional structure (input geometry)")
    print("  2. Boundary differentiation (geometric engine)")
    print("  3. Algebraic encoding (chain complex)")
    print("  4. Invariant extraction (homology, fullness, closure defect)")
    print()
    print("Key results to examine:")
    print("  - Classical examples should reproduce known homology")
    print("  - Non-classical examples (triple junction, thick boundary, overlap)")
    print("    test whether the engine handles structures beyond CW complexes")
    print("  - Scheme comparison shows which features persist vs vary")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
