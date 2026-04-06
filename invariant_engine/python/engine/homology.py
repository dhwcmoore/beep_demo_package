"""
homology.py — Homology computation over Z via Smith normal form.

Given a chain complex (C_k, ∂_k), computes:
    H_k = ker(∂_k) / im(∂_{k+1})

This requires integer linear algebra (Smith normal form) to detect
both free and torsion parts of homology groups.

The Smith normal form of an integer matrix M is:
    M = U * D * V
where U, V are unimodular (det ±1) and D is diagonal with
d_1 | d_2 | ... | d_r (divisibility chain).
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from chain_complex import ChainComplex


def smith_normal_form(M: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute the Smith normal form of an integer matrix M.

    Returns (U, D, V) where D = U @ M @ V,
    U (m×m) and V (n×n) are unimodular (det = ±1),
    D is diagonal with d_1 | d_2 | … | d_r (stored as a full m×n matrix).

    Note on convention: D = U @ M @ V, NOT M = U @ D @ V.
    Row operations accumulate on the left in U; column operations accumulate
    on the right in V.  Callers that need the kernel basis of M should use V
    (the columns of the right matrix span the column space in the transformed
    basis).

    Uses the classical Euclidean algorithm with row/column operations.
    Works for small-to-medium matrices typical of regional systems.
    """
    M = np.array(M, dtype=int)
    m, n = M.shape

    D = M.copy()
    U = np.eye(m, dtype=int)
    V = np.eye(n, dtype=int)

    def swap_rows(A, i, j):
        A[[i, j]] = A[[j, i]]

    def swap_cols(A, i, j):
        A[:, [i, j]] = A[:, [j, i]]

    def add_row_multiple(A, target, source, mult):
        A[target] += mult * A[source]

    def add_col_multiple(A, target, source, mult):
        A[:, target] += mult * A[:, source]

    pivot = 0
    size = min(m, n)

    for pivot in range(size):
        # Find a nonzero entry in the submatrix D[pivot:, pivot:]
        submat = D[pivot:, pivot:]
        if np.all(submat == 0):
            break

        # Find the entry with smallest absolute value
        nonzero = np.argwhere(submat != 0)
        abs_vals = np.abs(submat[nonzero[:, 0], nonzero[:, 1]])
        min_idx = nonzero[np.argmin(abs_vals)]
        pi, pj = min_idx[0] + pivot, min_idx[1] + pivot

        # Move pivot to (pivot, pivot)
        if pi != pivot:
            swap_rows(D, pivot, pi)
            swap_rows(U, pivot, pi)
        if pj != pivot:
            swap_cols(D, pivot, pj)
            swap_cols(V, pivot, pj)

        # Make pivot positive
        if D[pivot, pivot] < 0:
            D[pivot] *= -1
            U[pivot] *= -1

        # Eliminate in column and row, re-running if divisibility fix is needed.
        #
        # Bug fix A — GCD step: when D[i,pivot] is nonzero after subtraction,
        #   the floor-quotient of the remainder (< pivot) divided by the pivot
        #   is 0, so the entry is left unchanged while changed=True → infinite
        #   loop.  Fix: swap the remainder into the pivot position so the
        #   smaller value becomes the new pivot (Euclidean GCD step).
        #
        # Bug fix B — divisibility: after the while loop exits, a divisibility
        #   fix adds a row back into the pivot row, but the while loop has
        #   already terminated.  Fix: re-run the while loop after any fix.
        #
        # Termination guarantee:
        #   Each needs_reprocess restart strictly reduces |D[pivot,pivot]|
        #   (proof: the divisibility fix introduces an entry not divisible by
        #   D[pivot,pivot]; the GCD step in the next inner-loop pass replaces
        #   D[pivot,pivot] with gcd(D[pivot,pivot], that entry) < D[pivot,pivot]).
        #   The descent invariant is asserted below; a hard iter-guard provides
        #   a safety net against any future regression.

        # Bound: pivot can decrease at most abs(D[pivot,pivot]) times before
        # reaching 1, so that is the max number of reprocess cycles.
        _init_pivot_abs = int(abs(D[pivot, pivot])) if D[pivot, pivot] != 0 else 1
        _max_reprocess = _init_pivot_abs + 1
        _reprocess_count = 0
        _prev_pivot_abs = None   # checked at top of each iteration (skip first)

        # Inner loop guard: in each pass, either a nonzero becomes 0 or the
        # pivot shrinks.  The total number of changes is bounded by the number
        # of nonzeros times the initial pivot magnitude, so m*n*_init_pivot_abs
        # is a very conservative safe ceiling.
        _max_inner = (m + 1) * (n + 1) * _init_pivot_abs + (m + n + 1)

        needs_reprocess = True
        while needs_reprocess:
            # Descent invariant: each restart must have reduced the pivot.
            _cur_pivot_abs = int(abs(D[pivot, pivot]))
            if _prev_pivot_abs is not None and _cur_pivot_abs >= _prev_pivot_abs:
                raise RuntimeError(
                    f"SNF: pivot did not decrease at pivot={pivot}: "
                    f"was {_prev_pivot_abs}, now {_cur_pivot_abs}. "
                    "Bug in elimination or divisibility fix."
                )
            _prev_pivot_abs = _cur_pivot_abs

            _reprocess_count += 1
            if _reprocess_count > _max_reprocess:
                raise RuntimeError(
                    f"SNF: needs_reprocess exceeded {_max_reprocess} iterations "
                    f"at pivot={pivot} (D[pivot,pivot]={D[pivot,pivot]}). "
                    "Termination invariant violated."
                )

            changed = True
            _inner_count = 0
            while changed:
                changed = False
                _inner_count += 1
                if _inner_count > _max_inner:
                    raise RuntimeError(
                        f"SNF: inner elimination loop exceeded {_max_inner} "
                        f"iterations at pivot={pivot}. Bug in GCD step."
                    )

                # Eliminate column entries below pivot
                for i in range(pivot + 1, m):
                    if D[i, pivot] != 0:
                        if D[pivot, pivot] == 0:
                            swap_rows(D, pivot, i)
                            swap_rows(U, pivot, i)
                            changed = True
                            continue
                        q = D[i, pivot] // D[pivot, pivot]
                        add_row_multiple(D, i, pivot, -q)
                        add_row_multiple(U, i, pivot, -q)
                        if D[i, pivot] != 0:
                            # GCD step: remainder is smaller; put it at pivot
                            swap_rows(D, pivot, i)
                            swap_rows(U, pivot, i)
                            changed = True

                # Eliminate row entries right of pivot
                for j in range(pivot + 1, n):
                    if D[pivot, j] != 0:
                        if D[pivot, pivot] == 0:
                            swap_cols(D, pivot, j)
                            swap_cols(V, pivot, j)
                            changed = True
                            continue
                        q = D[pivot, j] // D[pivot, pivot]
                        add_col_multiple(D, j, pivot, -q)
                        add_col_multiple(V, j, pivot, -q)
                        if D[pivot, j] != 0:
                            # GCD step: remainder is smaller; put it at pivot
                            swap_cols(D, pivot, j)
                            swap_cols(V, pivot, j)
                            changed = True

            # Check divisibility: D[pivot,pivot] should divide all entries
            # in the remaining submatrix. If not, add a row to fix and
            # re-run the elimination loop.
            needs_reprocess = False
            if pivot + 1 < min(m, n) and D[pivot, pivot] != 0:
                submat_rest = D[pivot + 1:, pivot + 1:]
                remainder = submat_rest % D[pivot, pivot]
                if np.any(remainder != 0):
                    bad = np.argwhere(remainder != 0)[0]
                    bi = bad[0] + pivot + 1
                    add_row_multiple(D, pivot, bi, 1)
                    add_row_multiple(U, pivot, bi, 1)
                    needs_reprocess = True

    return U, D, V


def diagonal_entries(D: np.ndarray) -> list[int]:
    """Extract diagonal entries from a (possibly non-square) matrix."""
    r = min(D.shape)
    return [int(D[i, i]) for i in range(r)]


@dataclass
class HomologyGroup:
    """
    Represents H_k as a finitely generated abelian group.

    H_k ≅ Z^{betti} ⊕ Z/t_1 ⊕ Z/t_2 ⊕ ...

    Attributes:
        dim: the dimension k
        betti: rank of the free part
        torsion: list of torsion coefficients (each > 1)
        generators_label: names of the generating regions (for interpretation)
    """
    dim: int
    betti: int
    torsion: list[int]
    generators_label: list[str]

    def is_trivial(self) -> bool:
        return self.betti == 0 and len(self.torsion) == 0

    def __repr__(self):
        parts = []
        if self.betti > 0:
            parts.append(f"Z^{self.betti}" if self.betti > 1 else "Z")
        for t in self.torsion:
            parts.append(f"Z/{t}")
        if not parts:
            return f"H_{self.dim} = 0"
        return f"H_{self.dim} = {' ⊕ '.join(parts)}"


def invert_unimodular(V: np.ndarray) -> np.ndarray:
    """
    Compute the integer inverse of a unimodular matrix V (det = ±1).

    Uses rational Gaussian elimination via fractions.Fraction for exact
    integer arithmetic.  Safe and correct for the small matrices produced
    by smith_normal_form; not intended for large matrices.

    Raises ValueError if V is singular or produces a non-integer inverse
    (which would mean V was not actually unimodular).
    """
    from fractions import Fraction

    n = V.shape[0]
    if n == 0:
        return np.zeros((0, 0), dtype=int)

    # Augmented system [V | I] → [I | V^{-1}]
    A = [[Fraction(int(V[i, j])) for j in range(n)] for i in range(n)]
    B = [[Fraction(1 if i == j else 0) for j in range(n)] for i in range(n)]

    for col in range(n):
        # Find a nonzero pivot in column col at or below the diagonal
        piv = next((r for r in range(col, n) if A[r][col] != 0), None)
        if piv is None:
            raise ValueError(f"invert_unimodular: matrix is singular (column {col})")
        if piv != col:
            A[col], A[piv] = A[piv], A[col]
            B[col], B[piv] = B[piv], B[col]

        # Scale pivot row so the diagonal entry becomes 1
        p = A[col][col]
        A[col] = [x / p for x in A[col]]
        B[col] = [x / p for x in B[col]]

        # Eliminate all other rows
        for r in range(n):
            if r == col:
                continue
            factor = A[r][col]
            if factor != 0:
                A[r] = [A[r][c] - factor * A[col][c] for c in range(n)]
                B[r] = [B[r][c] - factor * B[col][c] for c in range(n)]

    # Convert back to integers (must be exact for unimodular matrices)
    result = np.zeros((n, n), dtype=int)
    for i in range(n):
        for j in range(n):
            f = B[i][j]
            if f.denominator != 1:
                raise ValueError(
                    f"invert_unimodular: non-integer entry at ({i},{j}) = {f}. "
                    "V is not unimodular."
                )
            result[i, j] = int(f.numerator)
    return result


def compute_homology(cc: ChainComplex) -> dict[int, HomologyGroup]:
    """
    Compute homology groups H_k for all k in the chain complex.

    Uses Smith normal form to compute ker(∂_k) / im(∂_{k+1}).

    Algorithm for each k:
      1. Compute SNF of ∂_k: D_k = U_k @ ∂_k @ V_k.
         rank_dk = number of nonzero diagonal entries.
         nullity_dk = n_k - rank_dk.

      2. Change basis on C_k using V_k.
         In coordinates y = V_k^{-1} @ x, the kernel of ∂_k is exactly
         the subspace where the first rank_dk coordinates are zero.

      3. Express ∂_{k+1} in the new basis: A_full = V_k^{-1} @ ∂_{k+1}.
         The first rank_dk rows of A_full must be zero in a valid complex
         (im(∂_{k+1}) ⊆ ker(∂_k)).

      4. The induced map into ker(∂_k) is A = A_full[rank_dk:, :],
         a matrix of shape (nullity_dk × n_{k+1}).

      5. Compute SNF of A.
         betti = nullity_dk - rank(A)  (free rank of H_k)
         torsion = diagonal entries of SNF(A) that are > 1

    This correctly computes the invariant factors of the quotient
    ker(∂_k) / im(∂_{k+1}), not those of ∂_{k+1} in the ambient C_k.
    """
    results = {}

    for k in range(cc.max_dim + 1):
        generators = cc.generators.get(k, [])
        nk = len(generators)

        if nk == 0:
            results[k] = HomologyGroup(dim=k, betti=0, torsion=[], generators_label=[])
            continue

        # ∂_k : C_k → C_{k-1},  shape (n_{k-1}, n_k)
        dk = cc.boundary_matrix(k)

        # ∂_{k+1} : C_{k+1} → C_k,  shape (n_k, n_{k+1})
        dk1 = cc.boundary_matrix(k + 1)

        # Step 1: SNF of ∂_k to get rank and the right-basis matrix V_k.
        # Convention: D_k = U_k @ dk @ V_k.
        if dk.size == 0 or np.all(dk == 0):
            rank_dk = 0
            Vk = np.eye(nk, dtype=int)
        else:
            _, Dk_mat, Vk = smith_normal_form(dk)
            diag_dk = diagonal_entries(Dk_mat)
            rank_dk = sum(1 for d in diag_dk if d != 0)

        nullity_dk = nk - rank_dk

        # Step 2–4: express ∂_{k+1} in the V_k basis and restrict to ker(∂_k).
        if dk1.size == 0 or np.all(dk1 == 0):
            # No image from above: H_k ≅ Z^nullity_dk (free, no torsion).
            results[k] = HomologyGroup(
                dim=k,
                betti=nullity_dk,
                torsion=[],
                generators_label=generators,
            )
            continue

        # V_k is unimodular; compute its integer inverse.
        Vkinv = invert_unimodular(Vk)

        # A_full: ∂_{k+1} expressed in the new C_k basis.
        # In a valid chain complex the top rank_dk rows are zero.
        A_full = Vkinv @ dk1  # shape (nk, n_{k+1})
        A = A_full[rank_dk:, :]  # shape (nullity_dk, n_{k+1})

        # Step 5: SNF of the restricted map A.
        if A.size == 0 or np.all(A == 0):
            rank_A = 0
            torsion = []
        else:
            _, DA, _ = smith_normal_form(A)
            diag_A = diagonal_entries(DA)
            nonzero_A = [d for d in diag_A if d != 0]
            rank_A = len(nonzero_A)
            torsion = [abs(d) for d in nonzero_A if abs(d) > 1]

        betti = nullity_dk - rank_A

        results[k] = HomologyGroup(
            dim=k,
            betti=max(0, betti),
            torsion=sorted(torsion),
            generators_label=generators,
        )

    return results


def homology_report(cc: ChainComplex) -> str:
    """Human-readable homology computation."""
    hom = compute_homology(cc)
    lines = [f"Homology of '{cc.system_name}':"]
    lines.append(f"  Chain complex valid: {cc.is_valid}")

    euler = 0
    for k in sorted(hom.keys()):
        h = hom[k]
        lines.append(f"  {h}")
        euler += ((-1) ** k) * h.betti

    lines.append(f"  Euler characteristic: {euler}")
    betti_vec = [hom[k].betti for k in sorted(hom.keys())]
    lines.append(f"  Betti numbers: {betti_vec}")

    torsion_any = any(len(hom[k].torsion) > 0 for k in hom)
    if torsion_any:
        lines.append("  Torsion detected:")
        for k in sorted(hom.keys()):
            if hom[k].torsion:
                lines.append(f"    H_{k} torsion: {hom[k].torsion}")

    return "\n".join(lines)
