"""Exact finite references. No physical erasure, private computation or payment system."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from fractions import Fraction as F
from typing import Any


def require(condition: object, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Row:
    identity: str
    x: tuple[F, F]
    y: F


Matrix = tuple[tuple[F, F], tuple[F, F]]
Vector = tuple[F, F]


def statistics(rows: tuple[Row, ...], regularizer: F) -> tuple[Matrix, Vector]:
    require(
        regularizer > 0 and len(rows) <= 1024 and len({r.identity for r in rows}) == len(rows),
        "ridge-domain-or-duplicate-record",
    )
    a = regularizer + sum((r.x[0] ** 2 for r in rows), F(0))
    b = sum((r.x[0] * r.x[1] for r in rows), F(0))
    c = regularizer + sum((r.x[1] ** 2 for r in rows), F(0))
    rhs = (sum((r.x[0] * r.y for r in rows), F(0)), sum((r.x[1] * r.y for r in rows), F(0)))
    return ((a, b), (b, c)), rhs


def solve(matrix: Matrix, rhs: Vector) -> Vector:
    (a, b), (c, d) = matrix
    determinant = a * d - b * c
    require(b == c and a > 0 and determinant > 0, "positive-definite-system-required")
    return ((d * rhs[0] - b * rhs[1]) / determinant, (a * rhs[1] - c * rhs[0]) / determinant)


def residual(matrix: Matrix, rhs: Vector, candidate: Vector) -> Vector:
    return tuple(
        sum((a * b for a, b in zip(row, candidate, strict=True)), F(0)) - target
        for row, target in zip(matrix, rhs, strict=True)
    )  # type: ignore[return-value]


def squared_norm(value: Vector) -> F:
    return sum((v * v for v in value), F(0))


def removal(
    rows: tuple[Row, ...], remove_ids: set[str], authorized_ids: set[str], regularizer: F
) -> dict[str, Any]:
    require(
        remove_ids <= authorized_ids <= {row.identity for row in rows}, "unauthorized-retained-set"
    )
    matrix, rhs = statistics(rows, regularizer)
    old = solve(matrix, rhs)
    removed = tuple(row for row in rows if row.identity in remove_ids)
    retained = tuple(row for row in rows if row.identity not in remove_ids)
    # Fixed sum-objective regularizer: subtract data statistics, never lambda itself.
    downdated: Matrix = tuple(
        tuple(matrix[i][j] - sum((r.x[i] * r.x[j] for r in removed), F(0)) for j in range(2))
        for i in range(2)
    )  # type: ignore[assignment]
    target: Vector = tuple(rhs[i] - sum((r.x[i] * r.y for r in removed), F(0)) for i in range(2))  # type: ignore[assignment]
    recomputed = statistics(retained, regularizer)
    require((downdated, target) == recomputed, "downdate-recompute-mismatch")
    new = solve(downdated, target)
    old_residual = residual(downdated, target, old)
    return {
        "old": old,
        "new": new,
        "matrix": downdated,
        "rhs": target,
        "retained": tuple(r.identity for r in retained),
        "parameter_change_squared": squared_norm((new[0] - old[0], new[1] - old[1])),
        "old_candidate_residual_bound_squared": squared_norm(old_residual) / regularizer**2,
        "new_residual_squared": squared_norm(residual(downdated, target, new)),
        "dataset_commitment": digest(
            [(r.identity, [str(v) for v in r.x], str(r.y)) for r in retained]
        ),
    }


def check_lifecycle(record: dict[str, Any], trusted: dict[str, Any]) -> None:
    require(
        record["claim_scope"] == "current-model-and-known-inventory-only",
        "full-erasure-unsupported",
    )
    require(
        record["parent_model"] == trusted["parent_model"]
        and record["parent_model"] != record["new_model"]
        and record["new_model"] == trusted["expected_retained_model"],
        "old-or-unbound-model",
    )
    require(
        set(record["known_artifacts"])
        == set(record["artifact_actions"])
        == set(trusted["known_artifacts"]),
        "omitted-known-artifact",
    )
    allowed = {"removed", "quarantined-not-erased", "retained-declared", "uncontrolled"}
    require(set(record["artifact_actions"].values()) <= allowed, "unknown-lifecycle-action")
    require(
        record["prior_releases"] == record["retained_release_history"] == trusted["prior_releases"]
        and F(record["privacy_spent_after"]) >= F(trusted["privacy_spent_before"]) >= 0,
        "disclosure-history-or-accounting-refund",
    )
    require(
        record["unobserved_copy_status"] == "unknown"
        and record["certificate_kind"] == "transparent-reference-not-cryptographic-proof",
        "unobserved-copy-or-proof-overclaim",
    )


def coalitions(players: tuple[str, ...]) -> list[frozenset[str]]:
    require(1 <= len(players) <= 4 and len(set(players)) == len(players), "bounded-player-set")
    return [
        frozenset(c) for n in range(len(players) + 1) for c in itertools.combinations(players, n)
    ]


def shapley(players: tuple[str, ...], utility: dict[frozenset[str], F]) -> dict[str, F]:
    require(set(utility) == set(coalitions(players)), "incomplete-coalition-table")
    n = len(players)
    result = {}
    for player in players:
        result[player] = sum(
            (
                F(math.factorial(len(s)) * math.factorial(n - len(s) - 1), math.factorial(n))
                * (utility[s | {player}] - value)
                for s, value in utility.items()
                if player not in s
            ),
            F(0),
        )
    require(
        sum(result.values(), F(0)) == utility[frozenset(players)] - utility[frozenset()],
        "allocation-efficiency",
    )
    return result


def surrogate_bound(
    players: tuple[str, ...],
    original: dict[frozenset[str], F],
    surrogate: dict[frozenset[str], F],
    eta: F,
) -> dict[str, F]:
    require(
        eta >= 0 and set(original) == set(surrogate) == set(coalitions(players)),
        "uniform-coalition-premise",
    )
    require(
        all(abs(original[s] - surrogate[s]) <= eta for s in original),
        "uniform-error-bound-not-established",
    )
    a, b = shapley(players, original), shapley(players, surrogate)
    errors = {p: abs(a[p] - b[p]) for p in players}
    require(all(error <= 2 * eta for error in errors.values()), "surrogate-bound-failed")
    return errors


def valuation_examples() -> dict[str, Any]:
    players = ("A", "B", "C")
    # Input table inspected in historical MS20261124 section59.2; outputs computed here.
    table = {
        frozenset(k): F(v)
        for k, v in {
            "": "0",
            "A": "3/5",
            "B": "2/5",
            "C": "1/10",
            "AB": "4/5",
            "AC": "7/10",
            "BC": "7/10",
            "ABC": "9/10",
        }.items()
    }
    eta = F(1, 100)
    surrogate = {s: value + (eta if "A" in s else -eta if s else 0) for s, value in table.items()}
    errors = surrogate_bound(players, table, surrogate, eta)
    # Historical section59.6 interchangeable-resource game; not an enrollment system.
    base_players, cloned = ("A", "B"), ("A1", "A2", "B")
    base = shapley(base_players, {s: F(bool(s)) for s in coalitions(base_players)})
    replicated = shapley(cloned, {s: F(bool(s)) for s in coalitions(cloned)})
    return {
        "allocation": {p: str(v) for p, v in shapley(players, table).items()},
        "uniform_eta": str(eta),
        "allocation_error_bound": str(2 * eta),
        "observed_reference_errors": {p: str(v) for p, v in errors.items()},
        "original_entity_allocation": str(base["A"]),
        "cloned_entity_allocation": str(replicated["A1"] + replicated["A2"]),
        "payment_observer_counterexample": (
            "For a singleton additive utility s, its payout equals s; "
            "visible payout reveals that utility."
        ),
        "payments_executed": 0,
        "economic_fairness": "not-established",
    }
