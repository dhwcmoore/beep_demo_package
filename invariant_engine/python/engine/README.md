# Regional Calculus Invariant Engine

A computational prototype for extracting topological invariants from
point-free regional systems via the Whiteheadian boundary operator.

## What this is

A working Python implementation of Whiteheadian mereotopology that computes
integer-valued homological invariants (Betti numbers, torsion, Euler
characteristic, fullness gap, closure defect) from spatial descriptions in
which the boundary relation is declared directly, not inferred from a
pre-existing triangulation.

The central idea: a *regional system* is a graded set of named regions with
explicitly declared boundary contacts. From those declarations the engine
builds integer boundary matrices, assembles a chain complex over Z, and runs
Smith normal form to extract homology. No simplicial, CW, or manifold
structure is assumed.

## What it computes

### Classical closed surfaces

| Example | H₀ | H₁ | H₂ | Torsion |
|---|---|---|---|---|
| Torus | Z | Z² | Z | none |
| Projective plane | Z | 0 | 0 | Z/2Z in H₁ |
| Klein bottle | Z | Z | 0 | Z/2Z in H₁ |
| Genus-2 surface | Z | Z⁴ | Z | none |

All match the known values from classical algebraic topology.

### Surfaces with boundary and lower-dimensional examples

| Example | H₀ | H₁ | H₂ | Notes |
|---|---|---|---|---|
| Triangle (disk) | Z | 0 | 0 | contractible |
| Loop without fill | Z | Z | — | one independent cycle |
| Möbius strip | Z | Z | 0 | non-orientable, boundary present |

### Three-dimensional examples

All 3D examples use `dim=3` regions. The engine handles arbitrary dimension
via the same pipeline with no special-casing.

| Example | H₀ | H₁ | H₂ | H₃ | χ | Valid |
|---|---|---|---|---|---|---|
| `solid_torus` | Z | Z² | 0 | 0 | −1 | yes |
| `ball_3` (D³, proper) | Z | 0 | 0 | 0 | 1 | **yes** |
| `solid_ball` (D³, telescoping) | Z | 0 | 0 | 0 | 1 | **no** |
| `sphere_3d` (S³) | Z | 0 | 0 | Z | 0 | **no** |
| `solid_book` | Z | 0 | 0 | Z² | −1 | **no** |
| `lens_3_1` (L(3,1)) | Z | Z/3Z | 0 | Z | 0 | yes |

**Valid** means the chain complex satisfies ∂∘∂ = 0. Invalid complexes are
flagged with `is_valid=False` but still produce correct homology via the
kernel-restriction method (see Known limitations). `ball_3` and `solid_ball`
compute identical homology but differ in validity — they are the primary
contrast pair for this property.

**`solid_torus`** — torus regional system plus one 3-cell V with ∂V = F.
Kills H₂; H₁ = Z² survives because neither loop is filled by a 2-cell.

**`ball_3`** — the minimal valid CW decomposition of D³. The boundary of D³
is S²; the minimal CW for S² is a single 0-cell v and a single 2-cell F with
no 1-dim boundary contacts (∂F = 0, the constant attaching map). Adding V
with ∂V = F gives ∂₂∘∂₃ = 0 × [[1]] = 0 vacuously (no 1-cells means ∂₂ is
an empty matrix). Result: H = (Z,0,0,0), χ=1. Both χ formulas agree.

**`solid_ball`** — the same D³ declared as a telescoping chain
v ← e ← F ← V (∂F=e, ∂V=F). The chain condition fails (∂₂∘∂₃ = [[1]] ≠ 0)
because F is a disk whose boundary is e, not a sphere. The kernel-restriction
method still returns H = (Z,0,0,0), χ=1 — identical to ball_3. The
generator-count formula gives χ=0, diverging from the Betti formula because
the complex is invalid. This pair demonstrates the robustness of
kernel-restriction: it recovers the correct answer even when ∂∘∂ ≠ 0.

**`sphere_3d`** — same spine as solid_ball plus two volumes V1 (∂V1=+F) and
V2 (∂V2=−F). Also invalid (∂₂∘∂₃ = [[1,−1]] ≠ 0). The cycle V1+V2 is in
ker(∂₃) and unfilled, giving H₃=Z. Result: H = (Z,0,0,Z), χ=0.

**`solid_book`** — non-manifold junction: three volumes V1, V2, V3 all
bounding the same spine F (∂₃ = [[1,1,1]]). Also invalid. rank(∂₃)=1,
nullity=2, so two independent 3-cycles (V1−V2) and (V2−V3) survive.
Result: H = (Z,0,0,Z²), χ=−1. Structural redundancy is 0.5 — the
non-manifold junction creates measurable generator overhead.

**`lens_3_1`** — the first valid 3D example with torsion. Face F is attached
to loop a with winding number 3 (∂F = 3a), implemented via three accumulated
`add_boundary_contact` calls. Volume V has no contacts (∂V = 0). The chain
condition holds: ∂₁∘∂₂ = 0 and ∂₂∘∂₃ = [[3]]×[[0]] = 0. SNF of [[3]]
yields invariant factor 3 directly. Result: H = (Z, Z/3Z, 0, Z), χ=0.

### Non-classical structures

These have no standard CW counterpart and are processed without error:

| Example | H (incidence) | Notes |
|---|---|---|
| `triple_junction` | (Z, 0, 0) | three 2-cells sharing one boundary edge |
| `thick_boundary` | (Z, 0, 0) | 2-cell bounded by a 2-dimensional region |
| `overlapping_regions` | (Z, 0, 0) | incidence homology; nerve gives (Z, 0) |
| `pinched_regions` | (Z, 0) | non-manifold point shared by three 1-cells |

`triple_junction` — the shared wall is a genuine mereotopological feature
with no simplicial analogue. The incidence complex is contractible.

`thick_boundary` — tests the framework on non-thin structures. The chain
complex is invalid (∂∘∂ ≠ 0) because the boundary of the thick boundary is
not codimension-1.

`overlapping_regions` — two 2-cells declared to overlap via `add_overlap`.
The incidence chain complex is built from boundary contacts only and gives
H = (Z, 0, 0). The overlap nerve (Čech nerve of the overlap relation) gives
a separate signature H = (Z, 0).

### Scheme comparison

The same underlying territory can be described at different resolutions or
with different adjacency predicates. The engine computes invariants under
each scheme and reports which features persist (structural) and which vary
(scheme-dependent artifacts of abstraction). Two comparisons are included:
a regional refinement example and the thick-boundary example under two
adjacency interpretations.

### Overlap nerve

When overlap data is present (`add_overlap`), the engine additionally builds
and reports the Čech nerve chain complex — the simplicial complex whose
k-simplices are (k+1)-tuples of mutually overlapping regions. This gives a
second, independent topological signature alongside the incidence homology.

## What it does not do

- **It is not a general-purpose topology library.** It is a prototype scoped
  to small, hand-declared regional systems (tens of regions, not thousands).

- **Well-formedness is the caller's responsibility.** The engine will run on
  any declared boundary structure, including ones that are geometrically
  inconsistent. The `is_valid` flag (∂∘∂ = 0) reports algebraic thinness,
  but it does not verify that the declared system corresponds to any
  realisable geometric space.

- **The `_overlap` relation carries no interface witness.** It records that
  two regions overlap but not *where* (no shared boundary arc). The incidence
  chain complex is built solely from `add_boundary_contact` declarations;
  `add_overlap` only feeds the nerve computation. An overlap with no
  corresponding boundary contacts does not affect the incidence homology.

- **The Smith normal form implementation is custom, not production-grade.**
  It includes termination guards (hard iteration caps) and a descent
  invariant assertion (pivot magnitude strictly decreases on each
  needs-reprocess restart), but is not a replacement for `sympy`, `flint`,
  or `sage`. It is correct and has been verified on all matrices this
  codebase produces.

- **No persistent homology, no filtered complexes, no cohomology, no
  coefficients other than Z.** Those are outside the current scope.

- **Scheme invariants are relative, not absolute.** A feature that vanishes
  under one abstraction scheme might reappear under another. The engine
  reports this comparison; it does not resolve it.

- **The overlap nerve is truncated at dimension 2 (triangles).** Higher
  cliques are not computed. This is a deliberate scope decision.

## Architecture

```
regions.py          RegionalSystem — declare regions, contacts, overlaps
boundary.py         Extract integer boundary matrix ∂_k from contacts;
                    signs accumulated via += for winding numbers > 1
chain_complex.py    Assemble chain complex; build_overlap_nerve from _overlap
homology.py         smith_normal_form; invert_unimodular; compute_homology
                    (kernel-restriction method for torsion)
schemes.py          Abstraction schemes — vary resolution/adjacency over
                    fixed territory; compare invariants across schemes
invariants.py       Fullness gap, closure defect, structural redundancy,
                    overlap nerve diagnostic
examples.py         Classical and non-classical topology examples
examples_hardware.py UCIe chiplet ring: nominal + fault models
main.py             Entry point: runs all examples, scheme comparisons,
                    and four correctness test suites
```

## Pipeline

```
RegionalSystem
    │  add_region(name, dim)
    │  add_boundary_contact(region, neighbor, sign)   ← signs accumulate
    │  add_overlap(a, b)
    ▼
boundary.py: ∂_k matrices (integer, shape n_{k-1} × n_k)
    repeated contacts sum: add_boundary_contact(F, a, +1) × 3  →  ∂F = 3a
    ▼
chain_complex.py: ChainComplex over Z  [+ overlap nerve if _overlap set]
    ▼
homology.py: H_k = ker(∂_k) / im(∂_{k+1})  via SNF
    Convention: D = U @ M @ V  (SNF on left and right)
    Torsion: kernel-restriction method — change basis via V_k⁻¹,
             restrict ∂_{k+1} to the nullity block, SNF that block
    ▼
invariants.py: Betti numbers, torsion, fullness gap, closure defect,
               structural redundancy, nerve homology
```

## Correctness test suites

`python3 main.py` runs four suites after the examples:

1. **Falsification tests** — two torus variants with deliberately different
   attachment maps. Proves the engine reads declared boundary contacts rather
   than defaulting ∂₂ to zero, and that SNF correctly cancels the nontrivial
   matrix in the refined torus to recover the same H = (Z, Z², Z).

2. **Orientation reversal** — negate all columns of ∂₂; verify homology is
   unchanged for five examples. Tests that sign tracking in the boundary
   matrices is orientation-invariant (im(−M) = im(M), ker(−M) = ker(M)).

3. **Basis invariance** — apply random unimodular transformations Uₖ ∈
   GL(nₖ, Z) to each chain group and verify Hₖ is unchanged. Also tests
   single-column negations of ∂₂ for granular sign-tracking coverage. Uses a
   randomly drawn, printed seed for reproducibility.

4. **Overlap nerve** — four minimal cases (single edge, triangle clique,
   4-cycle without diagonals, two disjoint edges) with Betti numbers asserted
   exactly, plus explicit ∂₁∘∂₂ = 0 check.

All four suites currently pass.

## Operational obstruction demo

`python3 main.py` also runs a concrete verification of the Operational
Obstruction Theorem on the `solid_book` example. The demo:

- Constructs Σ = { (a, b, o) ∈ Z³ : a+b+o = 0, |a|,|b|,|o| ≤ 2 }
  (19 states — tally vectors for a zero-sum three-channel vote counter).
- Defines α : Σ → C₃ by α(a,b,o) = a·V1 + b·V2 + o·V3.
- Defines transitions (→) as unit moves between channels.
- Verifies **(K)**: ∂₃·α(s) = a+b+o = 0 for all 19 states. HOLDS. ✓
- Verifies **(BR)**: α(t)−α(s) ∈ im(∂₄) = 0 for all 42 transitions.
  FAILS for all 42, because Δα ≠ 0 and im(∂₄) = 0. ✓
- Reports the **obstruction certificate**: [α(s₀)] = 0 ≠ [α(s₁)] in H₃,
  so no boundary-respecting execution path connects disagreement to
  consensus. The gap is topological and computable.

## Hardware and system models

`examples_hardware.py` maps real hardware interconnect structures onto the
regional system framework, demonstrating the violation → monitor pipeline on a
concrete engineering target.

### UCIe Chiplet Ring NoC

A 4-chiplet ring Network-on-Chip (as used in AMD MI300X / Intel Sapphire Rapids
style chiplet SoCs). UCIe die-to-die links are 1-dim regions; chiplet dies are
0-dim regions.

| State | Regions | b=[b₀,b₁] | Meaning |
|---|---|---|---|
| `chiplet_ring_nominal` | 4 dies, 4 links (full ring) | [1, 1] | Connected; ring routing valid |
| `chiplet_ring_link_fault` | 4 dies, 3 links (l23 failed) | [1, 0] | Connected; ring cycle destroyed |
| `chiplet_ring_partition` | 4 dies, 2 links (l12+l30 failed) | [2, 0] | Two isolated clusters |

Monitor advisories generated from the Betti delta:

| Δb₀ | Δb₁ | Code | Severity |
|---|---|---|---|
| > 0 | — | `CONNECTIVITY_PARTITION` | CRITICAL |
| 0 | < 0 | `RING_TOPOLOGY_VIOLATED` | WARNING |
| 0 | > 0 | `UNEXPECTED_CYCLE` | WARNING |

Run the end-to-end demo:

```bash
cd python
python demos/chiplet_monitor_demo.py
```

The demo runs the full pipeline: declare → compute → export payload (with
SHA-256) → compare vs baseline → emit advisories.

## Usage

```bash
python3 main.py
```

Requires Python 3.10+ and numpy. No other dependencies.

## Known limitations

- **Invalid complexes still produce homology.** For systems where ∂∘∂ ≠ 0,
  `compute_homology` runs anyway. The kernel-restriction method computes the
  formal quotient ker(∂_k)/im(∂_{k+1}) via a basis change that does not
  require ∂∘∂ = 0, and in practice returns the topologically correct answer
  for the examples in this codebase. The `is_valid` field on ChainComplex
  flags the violation; the Euler characteristic from Betti numbers and from
  generator counts will disagree when the complex is invalid.

- The SNF divisibility fix adds a row from the remaining submatrix to the
  pivot row rather than using a Bézout-based gcd step. This is correct and
  terminates (descent invariant asserted), but can temporarily inflate
  coefficients. For matrices produced by this codebase this has not caused
  problems.

- `invert_unimodular` uses `fractions.Fraction` Gaussian elimination to
  compute exact integer inverses of unimodular matrices. It raises
  `ValueError` if the matrix is singular or produces non-integer entries,
  which would indicate a bug in the SNF column-collection step.
