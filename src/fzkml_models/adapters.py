"""Fixed-factor algebra, delivered rounding and heterogeneous message policies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction as Q

from .algebra import Matrix, add, digest, ensure, matrix, multiply, norm2, rne, scale, transpose


@dataclass(frozen=True)
class FixedFactor:
    a: Matrix
    version: str
    initialization: str
    coefficient_bound: Q
    dense_bound: Q
    quantum: Q

    @property
    def id(self) -> str:
        return digest(self.__dict__)

    def validate(self) -> None:
        matrix(self.a)
        ensure(
            all(type(x) is Q for x in [self.coefficient_bound, self.dense_bound, self.quantum]),
            "exact-policy-bounds",
        )
        ensure(bool(self.version) and bool(self.initialization), "basis-version-and-initialization")
        ensure(
            self.coefficient_bound > 0 and self.dense_bound > 0 and self.quantum > 0,
            "adapter-bounds",
        )


def delivered(policy: FixedFactor, b: Matrix) -> Matrix:
    policy.validate()
    matrix(b)
    ensure(norm2(b) <= policy.coefficient_bound**2, "coefficient-clip-bound")
    dense = multiply(b, policy.a)
    result = matrix([[policy.quantum * rne(x / policy.quantum) for x in row] for row in dense])
    ensure(norm2(result) <= policy.dense_bound**2, "delivered-dense-hard-bound")
    return result


def fixed_aggregate(
    policy: FixedFactor,
    coefficients: tuple[Matrix, ...],
    weights: tuple[Q, ...],
    policy_ids: tuple[str, ...],
) -> tuple[Matrix, Matrix]:
    ensure(
        0 < len(coefficients) <= 8 and len(coefficients) == len(weights) == len(policy_ids),
        "adapter-cohort",
    )
    ensure(all(w >= 0 for w in weights) and sum(weights, Q(0)) == 1, "normalized-public-weights")
    ensure(all(p == policy.id for p in policy_ids), "factor-or-version-mismatch")
    # Exact coefficient-space state. Per-client dense rounding is a different
    # declared computation and is never substituted for this identity.
    total = scale(coefficients[0], weights[0])
    products = scale(multiply(coefficients[0], policy.a), weights[0])
    for b, w in zip(coefficients[1:], weights[1:], strict=True):
        total = add(total, scale(b, w))
        products = add(products, scale(multiply(b, policy.a), w))
    for b in coefficients:
        delivered(policy, b)
    ensure(multiply(total, policy.a) == products, "fixed-factor-distributivity")
    return total, products


def gram_squared(b: Matrix, a: Matrix) -> Q:
    bt_b, a_at = multiply(transpose(b), b), multiply(a, transpose(a))
    ensure(len(bt_b) == len(a_at), "gram-shape")
    return sum((bt_b[i][j] * a_at[j][i] for i in range(len(bt_b)) for j in range(len(bt_b))), Q(0))


def delivery_sensitivity_squared(policy: FixedFactor, max_weight: Q) -> Q:
    policy.validate()
    ensure(0 <= max_weight <= 1, "public-weight-bound")
    # Fixed accepted set and public weights; replacement adjacency. This bound
    # applies to the ACTUAL rounded, hard-bounded dense message above.
    return (2 * max_weight * policy.dense_bound) ** 2


def rank_one_approximation(a: Matrix) -> tuple[list[list[float]], float]:
    """Explicit floating-point 2x2 rank-one SVD approximation, never exact."""
    ensure(len(a) == len(a[0]) == 2, "tiny-svd-only")
    columns = transpose(a)
    x = float(sum(v * v for v in columns[0]))
    z = float(sum(v * v for v in columns[1]))
    y = float(sum(v * w for v, w in zip(columns[0], columns[1], strict=True)))
    theta = math.atan2(2 * y, x - z) / 2
    v = [math.cos(theta), math.sin(theta)]
    av = [sum(float(row[j]) * v[j] for j in range(2)) for row in a]
    approx = [[av[i] * v[j] for j in range(2)] for i in range(2)]
    error2 = sum((float(a[i][j]) - approx[i][j]) ** 2 for i in range(2) for j in range(2))
    return approx, error2


@dataclass(frozen=True)
class ComponentMessage:
    client: str
    values: tuple[Q | None, ...]
    kind: str
    initialization: str
    hidden_state: str | None


def heterogeneous(
    messages: tuple[ComponentMessage, ...],
    eligibility: tuple[tuple[bool, ...], ...],
    weights: tuple[Q, ...],
    initial: tuple[Q, ...],
    initialization: str,
    expected_hidden_states: tuple[str | None, ...],
    privacy_unit: str,
    whole_client_bound: Q | None = None,
) -> tuple[Q, ...]:
    ensure(
        0 < len(messages) <= 8
        and len(messages) == len(eligibility) == len(weights) == len(expected_hidden_states),
        "heterogeneous-cohort",
    )
    ensure(len({m.client for m in messages}) == len(messages), "duplicate-client")
    ensure(all(type(w) is Q and w > 0 for w in weights), "eligibility-positive-weights")
    ensure(all(type(x) is Q for x in initial), "exact-initial-state")
    ensure(privacy_unit in {"record", "client"}, "declared-privacy-unit")
    kinds = {m.kind for m in messages}
    ensure(len(kinds) == 1 and kinds <= {"full-state", "initialization-delta"}, "mixed-state-delta")
    ensure(all(m.initialization == initialization for m in messages), "wrong-initialization")
    ensure(1 <= len(initial) <= 8, "component-bound")
    for m, mask, hidden in zip(messages, eligibility, expected_hidden_states, strict=True):
        ensure(len(m.values) == len(mask) == len(initial), "component-shape")
        ensure(
            all(
                type(active) is bool and (value is not None) == active
                for value, active in zip(m.values, mask, strict=True)
            ),
            "eligibility-mask-binding",
        )
        ensure(m.hidden_state == hidden, "hidden-state-binding")
        ensure(all(x is None or type(x) is Q for x in m.values), "exact-component-values")
        ensure(
            hidden is None or (privacy_unit == "client" and whole_client_bound is not None),
            "hidden-state-record-sensitivity-unsupported",
        )
        if whole_client_bound is not None:
            ensure(
                type(whole_client_bound) is Q and whole_client_bound > 0, "whole-client-clip-policy"
            )
            ensure(
                sum((x * x for x in m.values if x is not None), Q(0)) <= whole_client_bound**2,
                "whole-client-delivered-bound",
            )
    output = []
    for j in range(len(initial)):
        denominator = sum(
            (w for w, mask in zip(weights, eligibility, strict=True) if mask[j]), Q(0)
        )
        ensure(denominator > 0, "empty-component-cohort")
        numerator = Q(0)
        for m, w in zip(messages, weights, strict=True):
            value = m.values[j]
            if value is not None:
                numerator += w * value
        value = numerator / denominator
        output.append(value + (initial[j] if messages[0].kind == "initialization-delta" else 0))
    return tuple(output)


def heterogeneous_sensitivity_squared(
    eligibility: tuple[tuple[bool, ...], ...], weights: tuple[Q, ...], bound: Q
) -> Q:
    """Fixed public masks/weights and whole-client clipped vectors; replacement."""
    ensure(0 < len(eligibility) == len(weights) <= 8 and bound > 0, "sensitivity-cohort")
    ensure(all(type(w) is Q and w > 0 for w in weights), "sensitivity-weights")
    width = len(eligibility[0])
    ensure(0 < width <= 8 and all(len(row) == width for row in eligibility), "sensitivity-mask")
    maximum = Q(0)
    for column in range(width):
        mass = sum((w for w, row in zip(weights, eligibility, strict=True) if row[column]), Q(0))
        ensure(mass > 0, "empty-sensitive-component")
        maximum = max(
            maximum, *(w / mass for w, row in zip(weights, eligibility, strict=True) if row[column])
        )
    return (2 * maximum * bound) ** 2


def hidden_state_counterexample(records: int, clip: Q) -> dict[str, Q]:
    ensure(type(records) is int and 2 <= records <= 1000 and clip > 0, "hidden-state-fixture")
    # A single changed record flips persistent state used by EVERY gradient.
    before, after = [-clip] * records, [clip] * records
    return {
        "actual_change": abs(sum(after, Q(0)) / records - sum(before, Q(0)) / records),
        "invalid_one_gradient_bound": 2 * clip / records,
        "whole_client_replacement_bound": 2 * clip,
    }


def evaluate_frozen_layer(
    base: Matrix, b: Matrix, a: Matrix, examples: Matrix, targets: Matrix
) -> dict[str, Q | int]:
    """Execute every frozen-backbone multiplication as well as the adapter.

    This is tiny synthetic inference/quality evaluation, not a training trace.
    Operation counts come from the executed loops, not parameter-count ratios.
    """
    ensure(len(examples) == len(targets), "evaluation-records")
    counts = {"backbone_multiplications": 0, "adapter_multiplications": 0}

    def matvec(weights: Matrix, vector: tuple[Q, ...], role: str) -> tuple[Q, ...]:
        ensure(len(weights[0]) == len(vector), "inference-shape")
        result = []
        for row in weights:
            value = Q(0)
            for coefficient, item in zip(row, vector, strict=True):
                value += coefficient * item
                counts[role] += 1
            result.append(value)
        return tuple(result)

    error = Q(0)
    for x, y in zip(examples, targets, strict=True):
        backbone = matvec(base, x, "backbone_multiplications")
        correction = matvec(b, matvec(a, x, "adapter_multiplications"), "adapter_multiplications")
        ensure(len(backbone) == len(correction) == len(y), "evaluation-target-shape")
        error += sum(
            ((p + q - target) ** 2 for p, q, target in zip(backbone, correction, y, strict=True)),
            Q(0),
        )
    return {
        **counts,
        "mean_squared_vector_error": error / len(examples),
        "backbone_parameters": len(base) * len(base[0]),
        "trainable_parameters": len(b) * len(b[0]),
        "evaluated_examples": len(examples),
    }
