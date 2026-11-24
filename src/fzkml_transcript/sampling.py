"""Exact finite inclusion-law expectations; no inferred DP amplification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from .algebra import Scalar, Vector, exact

Law = Mapping[frozenset[str], Fraction]


def validate_law(clients: Sequence[str], law: Law) -> None:
    if not clients or len(set(clients)) != len(clients) or not law:
        raise ValueError("nonempty unique clients and inclusion law required")
    if any(not subset <= set(clients) or exact(p) <= 0 for subset, p in law.items()):
        raise ValueError("invalid final inclusion event")
    if sum(law.values()) != 1:
        raise ValueError("inclusion probabilities must sum to one")


def inclusion_probabilities(clients: Sequence[str], law: Law) -> dict[str, Fraction]:
    validate_law(clients, law)
    return {c: sum((p for subset, p in law.items() if c in subset), Fraction(0)) for c in clients}


def weighted_moments(
    vectors: Mapping[str, Sequence[Scalar]],
    weights: Mapping[str, Scalar],
    law: Law,
    *,
    declared_probabilities: Mapping[str, Scalar] | None = None,
) -> tuple[Vector, Fraction]:
    clients = list(vectors)
    probabilities = inclusion_probabilities(clients, law)
    if set(weights) != set(clients) or sum(exact(w) for w in weights.values()) != 1:
        raise ValueError("fixed target weights summing to one required")
    if any(exact(w) < 0 for w in weights.values()):
        raise ValueError("nonnegative target weights required")
    d = len(vectors[clients[0]])
    if d == 0 or any(len(g) != d for g in vectors.values()):
        raise ValueError("fixed nonempty vector dimensions required")
    if declared_probabilities is not None:
        if set(declared_probabilities) != set(clients):
            raise ValueError("declared inclusion clients differ")
        probabilities = {c: exact(p) for c, p in declared_probabilities.items()}
    for c in clients:
        if not 0 <= probabilities[c] <= 1 or (exact(weights[c]) > 0 and probabilities[c] == 0):
            raise ValueError("positive final inclusion probability required for target weight")
    outcomes: list[tuple[Fraction, Vector]] = []
    for subset, probability in law.items():
        estimate = tuple(
            sum(
                (
                    exact(weights[c]) * exact(vectors[c][j]) / probabilities[c]
                    for c in subset
                    if exact(weights[c]) > 0
                ),
                Fraction(0),
            )
            for j in range(d)
        )
        outcomes.append((probability, estimate))
    mean = tuple(sum((p * g[j] for p, g in outcomes), Fraction(0)) for j in range(d))
    variance = sum(
        (p * sum((g[j] - mean[j]) ** 2 for j in range(d)) for p, g in outcomes), Fraction(0)
    )
    return mean, variance


def dependent_variance(
    vectors: Mapping[str, Sequence[Scalar]], weights: Mapping[str, Scalar], law: Law
) -> Fraction:
    # Validate all weights, dimensions and positivity through the enumerated estimator.
    weighted_moments(vectors, weights, law)
    clients = list(vectors)
    marginal = inclusion_probabilities(clients, law)
    total = Fraction(0)
    for i in clients:
        for j in clients:
            if exact(weights[i]) == 0 or exact(weights[j]) == 0:
                continue
            joint = sum((p for subset, p in law.items() if {i, j} <= subset), Fraction(0))
            dot = sum(
                (exact(a) * exact(b) for a, b in zip(vectors[i], vectors[j], strict=True)),
                Fraction(0),
            )
            total += (
                exact(weights[i])
                * exact(weights[j])
                * (joint - marginal[i] * marginal[j])
                * dot
                / (marginal[i] * marginal[j])
            )
    return total


@dataclass(frozen=True)
class PopulationTrace:
    invited: frozenset[str]
    selected: frozenset[str]
    completed: frozenset[str]
    accepted: frozenset[str]
    released: frozenset[str]
    resource_class: Mapping[str, str]

    def summary(self) -> dict[str, dict[str, int]]:
        stages = (self.invited, self.selected, self.completed, self.accepted, self.released)
        if any(not later <= earlier for earlier, later in zip(stages, stages[1:], strict=False)):
            raise ValueError("population stages are not nested")
        if set(self.resource_class) != set(self.invited):
            raise ValueError("resource class coverage differs from invited population")
        result = {}
        for name, stage in zip(
            ("invited", "selected", "completed", "accepted", "released"), stages, strict=True
        ):
            result[name] = {
                resource: sum(self.resource_class[c] == resource for c in stage)
                for resource in sorted(set(self.resource_class.values()))
            }
        return result


def amplification_status(*, fixed_cohort: bool, theorem_reference: str | None = None) -> str:
    if not fixed_cohort:
        raise ValueError("subsampling requires a separate sampler/observer/adjacency theorem")
    if theorem_reference is not None:
        raise ValueError("fixed-cohort reference applies no amplification")
    return "no-amplification"
