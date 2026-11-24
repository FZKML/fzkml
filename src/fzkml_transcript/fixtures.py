"""Regenerate original analytic reference data, never scientific run records."""

from __future__ import annotations

import argparse
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from .algebra import (
    conditional_covariance,
    matrix,
    scalar_cube_maximum,
    squared_separation,
    trace_gram,
)
from .entropy import half_normal_delta_floor
from .sampling import PopulationTrace, dependent_variance, weighted_moments

ROOT = Path(__file__).resolve().parents[2]


def analytic_fixtures() -> dict[str, Any]:
    precision = matrix([[F(8, 5) * int(i == j) - F(1, 2) for j in range(3)] for i in range(3)])
    gram = matrix([[1 if i == j else F(-1, 2) for j in range(3)] for i in range(3)])
    vectors = {"a": [1], "b": [-1]}
    weights = {"a": F(1, 2), "b": F(1, 2)}
    law = {frozenset({"a"}): F(9, 10), frozenset({"a", "b"}): F(1, 10)}
    mean, variance = weighted_moments(vectors, weights, law)
    wrong_mean, _ = weighted_moments(vectors, weights, law, declared_probabilities={"a": 1, "b": 1})
    independent = {
        frozenset(): F(1, 4),
        frozenset({"a"}): F(1, 4),
        frozenset({"b"}): F(1, 4),
        frozenset({"a", "b"}): F(1, 4),
    }
    exclusive = {frozenset({"a"}): F(1, 2), frozenset({"b"}): F(1, 2)}
    together = {frozenset(): F(1, 2), frozenset({"a", "b"}): F(1, 2)}
    trace = PopulationTrace(
        frozenset({"a", "b", "c", "d"}),
        frozenset({"a", "b", "c", "d"}),
        frozenset({"a", "b", "c"}),
        frozenset({"a", "b"}),
        frozenset({"a", "b"}),
        {"a": "fast", "b": "fast", "c": "slow", "d": "slow"},
    )
    return {
        "fixture_version": "transcript-analytic-1",
        "assurance": (
            "Analytic/synthetic conformance fixtures only; "
            "no finite sampler or deployed DP guarantee."
        ),
        "numeric_policy": (
            "Exact rational arithmetic, except the named erf approximation "
            "rounded to 12 decimals (absolute tolerance 1e-12)."
        ),
        "scalar_vector_example": {
            "scalar_maximum": str(scalar_cube_maximum(precision)),
            "vector_maximum": str(trace_gram(precision, gram)),
            "scope": (
                "Full three-round C=1 row-norm-bounded class; "
                "fixed data-independent continuous Gaussian precision."
            ),
        },
        "singular_covariance": {
            "outside_support": squared_separation(matrix([[1, 1], [1, 1]]), [1, 0]) is None,
            "supported_squared_cost": str(squared_separation(matrix([[1, 1], [1, 1]]), [1, 1])),
        },
        "conditioned_variance": str(
            conditional_covariance(matrix([[2, 1], [1, 1]]), [0], [1])[0][0]
        ),
        "half_normal_retry": {
            "delta_over_sigma": "1/10",
            "necessary_delta_floor_approx": format(half_normal_delta_floor(0.1), ".12f"),
            "expected_attempts": "2",
            "scope": (
                "Ideal Gaussian sign-visible rejection, "
                "not post-processing of one common public output."
            ),
        },
        "completion_filter": {
            "weighted_mean": str(mean[0]),
            "weighted_variance": str(variance),
            "invitation_probability_substitution_mean": str(wrong_mean[0]),
            "observed_unweighted_mean": "9/10",
        },
        "equal_marginal_variances": {
            "independent": str(dependent_variance(vectors, weights, independent)),
            "exclusive": str(dependent_variance(vectors, weights, exclusive)),
            "together": str(dependent_variance(vectors, weights, together)),
        },
        "resource_population_stages": trace.summary(),
        "amplification": "none; completion fractions are not amplification probabilities",
    }


def serialized_fixtures() -> bytes:
    return (
        json.dumps(analytic_fixtures(), indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    path = args.output or ROOT / "assets/public/transcript-analytic-v1.json"
    if args.check:
        if path.read_bytes() != serialized_fixtures():
            raise SystemExit("analytic fixture drift")
        print("analytic reference fixture matches; no deployed privacy claim")
    elif args.output:
        path.write_bytes(serialized_fixtures())
    else:
        parser.error("choose --check or an explicit --output")


if __name__ == "__main__":
    main()
