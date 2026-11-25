"""Small exact rational Gaussian geometry; no floating eigenvalue thresholds."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import product

Scalar = int | Fraction
Matrix = tuple[tuple[Fraction, ...], ...]
Vector = tuple[Fraction, ...]


def exact(value: Scalar) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError("exact integer or Fraction required")
    return Fraction(value)


def matrix(rows: Sequence[Sequence[Scalar]]) -> Matrix:
    if not rows or not rows[0] or len(rows) > 32 or len(rows[0]) > 32:
        raise ValueError("nonempty matrix with dimensions at most 32 required")
    if any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("ragged matrix")
    return tuple(tuple(exact(x) for x in row) for row in rows)


def transpose(a: Matrix) -> Matrix:
    return tuple(zip(*a, strict=True))


def multiply(a: Matrix, b: Matrix) -> Matrix:
    if len(a[0]) != len(b):
        raise ValueError("matrix dimension mismatch")
    return tuple(
        tuple(
            sum((x * y for x, y in zip(row, col, strict=True)), Fraction(0)) for col in transpose(b)
        )
        for row in a
    )


def symmetric(a: Matrix) -> None:
    if len(a) != len(a[0]) or a != transpose(a):
        raise ValueError("symmetric square matrix required")


def positive_semidefinite(a: Matrix) -> bool:
    symmetric(a)
    work = [list(row) for row in a]
    for k in range(len(a)):
        pivot = work[k][k]
        if pivot < 0:
            return False
        if pivot == 0:
            if any(work[k][j] != 0 for j in range(k + 1, len(a))):
                return False
            continue
        for i in range(k + 1, len(a)):
            for j in range(k + 1, len(a)):
                work[i][j] -= work[i][k] * work[k][j] / pivot
    return True


def solve(a: Matrix, b: Sequence[Scalar]) -> Vector | None:
    if len(a) != len(a[0]) or len(b) != len(a):
        raise ValueError("square system required")
    n = len(a)
    work = [list(row) + [exact(value)] for row, value in zip(a, b, strict=True)]
    pivots: list[tuple[int, int]] = []
    r = 0
    for col in range(n):
        pivot = next((i for i in range(r, n) if work[i][col]), None)
        if pivot is None:
            continue
        work[r], work[pivot] = work[pivot], work[r]
        divisor = work[r][col]
        work[r] = [v / divisor for v in work[r]]
        for i in range(n):
            if i != r:
                factor = work[i][col]
                work[i] = [x - factor * y for x, y in zip(work[i], work[r], strict=True)]
        pivots.append((r, col))
        r += 1
    if any(not any(row[:n]) and row[n] for row in work):
        return None
    result = [Fraction(0)] * n
    for row, col in pivots:
        result[col] = work[row][n]
    return tuple(result)


def squared_separation(covariance: Matrix, shift: Sequence[Scalar]) -> Fraction | None:
    """None means disjoint affine supports, not zero privacy cost."""
    if not positive_semidefinite(covariance):
        raise ValueError("covariance is not positive semidefinite")
    solution = solve(covariance, shift)
    if solution is None:
        return None
    # For PSD A and d in Range(A), every solution has d^T x = d^T A^dagger d.
    return sum((exact(d) * x for d, x in zip(shift, solution, strict=True)), Fraction(0))


def gaussian_rdp(covariance: Matrix, shift: Sequence[Scalar], alpha: Scalar) -> Fraction | None:
    order = exact(alpha)
    if order <= 1:
        raise ValueError("Renyi order must exceed one")
    q = squared_separation(covariance, shift)
    return None if q is None else order * q / 2


def inverse(a: Matrix) -> Matrix:
    n = len(a)
    columns = []
    for i in range(n):
        rhs = [Fraction(int(j == i)) for j in range(n)]
        result = solve(a, rhs)
        if result is None:
            raise ValueError("invertible covariance block required")
        columns.append(result)
    return transpose(tuple(columns))


def conditional_covariance(
    joint: Matrix, unknown: Sequence[int], observed: Sequence[int]
) -> Matrix:
    if not positive_semidefinite(joint):
        raise ValueError("invalid joint covariance")
    ids = list(unknown) + list(observed)
    if (
        not unknown
        or not observed
        or len(set(ids)) != len(ids)
        or any(type(i) is not int or not 0 <= i < len(joint) for i in ids)
    ):
        raise ValueError("disjoint nonempty covariance index sets required")
    uu = matrix([[joint[i][j] for j in unknown] for i in unknown])
    uv = matrix([[joint[i][j] for j in observed] for i in unknown])
    vv = matrix([[joint[i][j] for j in observed] for i in observed])
    correction = multiply(multiply(uv, inverse(vv)), transpose(uv))
    return matrix([[uu[i][j] - correction[i][j] for j in range(len(uu))] for i in range(len(uu))])


def residual_covariance(
    loadings: Mapping[str, Matrix],
    survivors: frozenset[str],
    revealed: frozenset[str],
    *,
    independent: bool,
) -> Matrix:
    if not independent or not loadings:
        raise ValueError("explicit independent-noise model required")
    if not (survivors | revealed) <= loadings.keys():
        raise ValueError("unknown noise contributor")
    n = len(next(iter(loadings.values())))
    total = [[Fraction(0) for _ in range(n)] for _ in range(n)]
    for name, loading in loadings.items():
        if len(loading) != n:
            raise ValueError("inconsistent noise dimensions")
        if name in survivors - revealed:
            contribution = multiply(loading, transpose(loading))
            for i in range(n):
                for j in range(n):
                    total[i][j] += contribution[i][j]
    return matrix(total)


def check_patterns(
    covariances: Mapping[str, Matrix],
    permitted: frozenset[str],
    shifts: Sequence[Sequence[Scalar]],
    bound: Scalar,
) -> dict[str, Fraction]:
    if not permitted or set(covariances) != permitted or not shifts or exact(bound) < 0:
        raise ValueError("complete explicit finite pattern and shift sets required")
    costs = {}
    for pattern in sorted(permitted):
        values = [squared_separation(covariances[pattern], d) for d in shifts]
        if any(v is None for v in values):
            raise ValueError("sensitive shift outside residual support")
        finite = [v for v in values if v is not None]
        worst = max(finite)
        if worst > exact(bound):
            raise ValueError("permitted-pattern privacy geometry exceeds bound")
        costs[pattern] = worst
    return costs


def scalar_cube_maximum(precision: Matrix, bound: Scalar = 1) -> Fraction:
    if not positive_semidefinite(precision) or len(precision) > 12 or exact(bound) < 0:
        raise ValueError("small PSD precision and nonnegative bound required")
    c = exact(bound)
    return max(
        sum(
            (precision[i][j] * s[i] * s[j] for i in range(len(s)) for j in range(len(s))),
            Fraction(0),
        )
        for s in product((-c, c), repeat=len(precision))
    )


def trace_gram(precision: Matrix, gram: Matrix) -> Fraction:
    if (
        len(precision) != len(gram)
        or not positive_semidefinite(precision)
        or not positive_semidefinite(gram)
    ):
        raise ValueError("compatible PSD precision and Gram matrices required")
    return sum(
        (precision[i][j] * gram[j][i] for i in range(len(gram)) for j in range(len(gram))),
        Fraction(0),
    )
