"""Weighted frozen-feature ridge statistics and exact residual certificates.

Feature authenticity/extraction and protected vector aggregation are external
assumptions. Numerical certificates here are distinct from Groth16 proofs.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Q

from .algebra import Matrix, add, digest, ensure, identity, matrix, multiply, norm2, scale, solve


@dataclass(frozen=True)
class Statistics:
    s: Matrix
    t: Matrix
    q: Q
    records: tuple[str, ...]
    mass: Q
    feature_version: str
    preprocessing: str
    dataset_digest: str

    @property
    def id(self) -> str:
        return digest(self.__dict__)


def validate_statistics(stats: Statistics) -> None:
    s, t = matrix(stats.s), matrix(stats.t)
    ensure(
        len(s) == len(s[0]) == len(t) and s == tuple(zip(*s, strict=True)),
        "symmetric-statistic-shape",
    )
    ensure(
        type(stats.q) is Q and stats.q >= 0 and type(stats.mass) is Q and stats.mass > 0,
        "statistic-mass-and-constant",
    )
    ensure(
        0 < len(stats.records) <= 64 and len(set(stats.records)) == len(stats.records),
        "retained-records",
    )
    # Exact PSD check by Schur complements, including singular PSD matrices.
    remainder = [list(row) for row in s]
    for i in range(len(s)):
        pivot = remainder[i][i]
        ensure(pivot >= 0, "statistic-not-positive-semidefinite")
        if pivot == 0:
            ensure(
                all(remainder[i][j] == 0 for j in range(i + 1, len(s))), "zero-pivot-off-diagonal"
            )
        else:
            for j in range(i + 1, len(s)):
                for k in range(i + 1, len(s)):
                    remainder[j][k] -= remainder[j][i] * remainder[i][k] / pivot


def statistics(
    features: Matrix,
    labels: Matrix,
    weights: tuple[Q, ...],
    record_ids: tuple[str, ...],
    feature_version: str = "synthetic-identity-2-v1",
    preprocessing: str = "exact-rational-v1",
) -> Statistics:
    z, y = matrix(features), matrix(labels)
    ensure(len(z) == len(y) == len(weights) == len(record_ids), "statistic-shape")
    ensure(len(set(record_ids)) == len(record_ids) and all(record_ids), "record-identity")
    ensure(all(type(w) is Q and 0 < w <= 8 for w in weights), "positive-bounded-weights")
    ensure(bool(feature_version) and bool(preprocessing), "feature-lineage")
    wz = matrix([[weights[i] * v for v in row] for i, row in enumerate(z)])
    wy = matrix([[weights[i] * v for v in row] for i, row in enumerate(y)])
    from .algebra import transpose

    return Statistics(
        multiply(transpose(z), wz),
        multiply(transpose(z), wy),
        sum((weights[i] * sum((v * v for v in row), Q(0)) for i, row in enumerate(y)), Q(0)),
        record_ids,
        sum(weights, Q(0)),
        feature_version,
        preprocessing,
        digest({"z": z, "y": y, "weights": weights, "records": record_ids}),
    )


def combine(parts: tuple[Statistics, ...]) -> Statistics:
    ensure(0 < len(parts) <= 8, "cohort-bound")
    for part in parts:
        validate_statistics(part)
    first = parts[0]
    ids = tuple(r for p in parts for r in p.records)
    ensure(len(set(ids)) == len(ids), "duplicate-retained-record")
    ensure(
        all(
            (p.feature_version, p.preprocessing) == (first.feature_version, first.preprocessing)
            for p in parts
        ),
        "feature-preprocessor-mismatch",
    )
    s, t = first.s, first.t
    for p in parts[1:]:
        s, t = add(s, p.s), add(t, p.t)
    return Statistics(
        s,
        t,
        sum((p.q for p in parts), Q(0)),
        ids,
        sum((p.mass for p in parts), Q(0)),
        first.feature_version,
        first.preprocessing,
        digest([p.dataset_digest for p in parts]),
    )


def system(stats: Statistics, regularization: Q, objective: str = "sum") -> tuple[Matrix, Matrix]:
    validate_statistics(stats)
    ensure(type(regularization) is Q and regularization > 0, "regularization-positive")
    ensure(objective in {"sum", "weighted-mean"}, "objective-policy")
    multiplier = Q(1) if objective == "sum" else stats.mass
    return add(stats.s, scale(identity(len(stats.s)), regularization * multiplier)), stats.t


def fit(stats: Statistics, regularization: Q, objective: str = "sum") -> Matrix:
    return solve(*system(stats, regularization, objective))


@dataclass(frozen=True)
class Certificate:
    statistics_id: str
    model_id: str
    regularization: Q
    objective: str
    residual: Matrix
    residual_squared: Q


def certificate(
    stats: Statistics, model: Matrix, regularization: Q, objective: str = "sum"
) -> Certificate:
    a, t = system(stats, regularization, objective)
    residual = add(multiply(a, model), scale(t, Q(-1)))
    return Certificate(
        stats.id, digest(model), regularization, objective, residual, norm2(residual)
    )


def verify(
    stats: Statistics,
    model: Matrix,
    cert: Certificate,
    max_residual_squared: Q,
    expected_statistics_id: str,
    regularization: Q,
    objective: str = "sum",
) -> dict[str, Q]:
    ensure(stats.id == expected_statistics_id, "unauthorized-statistics")
    ensure(cert == certificate(stats, model, regularization, objective), "certificate-binding")
    ensure(
        max_residual_squared >= 0 and cert.residual_squared <= max_residual_squared,
        "residual-hard-bound",
    )
    # The normal equation's strong-convexity lower bound and objective scaling
    # both change under weighted-mean loss.
    mass = Q(1) if objective == "sum" else stats.mass
    mu = regularization * mass
    return {
        "parameter_error_squared_bound": cert.residual_squared / (mu * mu),
        "excess_objective_bound": cert.residual_squared / (2 * mu * mass),
    }


def objective(stats: Statistics, model: Matrix, regularization: Q, policy: str = "sum") -> Q:
    system(stats, regularization, policy)
    from .algebra import transpose

    quadratic = multiply(transpose(model), multiply(stats.s, model))
    cross = multiply(transpose(model), stats.t)
    loss = (
        sum((quadratic[i][i] - 2 * cross[i][i] for i in range(len(quadratic))), Q(0)) + stats.q
    ) / 2
    return loss / (Q(1) if policy == "sum" else stats.mass) + regularization * norm2(model) / 2


def perturbation_bound(
    stats: Statistics,
    model: Matrix,
    regularization: Q,
    curvature_error: Matrix,
    target_error: Matrix,
) -> Q:
    """Candidate-based error upper bound, including arbitrary symmetric noise.

    This deterministic conditional calculation supplies no DP noise mechanism.
    Frobenius bounds the curvature operator norm; a residual for the changed
    system is never silently treated as a certificate for the clean system.
    """
    from .algebra import sqrt_upper, transpose

    ensure(curvature_error == transpose(curvature_error), "symmetric-curvature-error")
    a, t = system(stats, regularization)
    noisy_residual = add(
        multiply(add(a, curvature_error), model), scale(add(t, target_error), Q(-1))
    )
    return (
        sqrt_upper(norm2(noisy_residual))
        + sqrt_upper(norm2(curvature_error)) * sqrt_upper(norm2(model))
        + sqrt_upper(norm2(target_error))
    ) / regularization


def statistic_scalars(d: int, c: int, absolute_objective: bool = False) -> int:
    ensure(
        type(d) is int and type(c) is int and 1 <= d <= 1_000_000 and 1 <= c <= 1_000_000,
        "analytic-dimension-bound",
    )
    return d * (d + 1) // 2 + d * c + int(absolute_objective)


def crossover(d: int, c: int) -> Q:
    return Q(statistic_scalars(d, c), d * c)


def record_sensitivity_squared(feature_bound: Q, label_bound: Q, replacement: bool) -> Q:
    ensure(feature_bound >= 0 and label_bound >= 0, "sensitivity-bounds")
    # Full vectorization metric; packed triangular coordinates require their
    # matching metric/noise calibration. No Gaussian/DP mechanism is implied.
    return (4 if replacement else 1) * (feature_bound**4 + feature_bound**2 * label_bound**2)
