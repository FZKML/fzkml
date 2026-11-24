"""Fixed-classifier synthetic evaluation and conditional public-count certificates.

No finite-arithmetic DP sampler is supplied. The certificate analyzes the ideal
Laplace law stated in the manuscript; simulated releases carry no DP guarantee.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal

from fzkml_ci.validate import require


@dataclass(frozen=True)
class Classifier:
    weights: tuple[Fraction, ...]
    threshold: Fraction

    def digest(self) -> str:
        data = tuple(map(str, self.weights)), str(self.threshold)
        return hashlib.sha256(json.dumps(data).encode()).hexdigest()

    def predict(self, features: tuple[Fraction, ...]) -> bool:
        require(bool(features) and len(features) == len(self.weights), "classifier-shape")
        return (
            sum((a * b for a, b in zip(features, self.weights, strict=True)), Fraction(0))
            >= self.threshold
        )


@dataclass(frozen=True)
class SyntheticRecord:
    unit_id: str
    group: Literal[0, 1]
    positive_label: bool
    features: tuple[Fraction, ...]


def counts(
    classifier: Classifier, records: tuple[SyntheticRecord, ...]
) -> tuple[int, int, int, int]:
    require(bool(records) and len(records) <= 20_000, "evaluation-size")
    require(len({r.unit_id for r in records}) == len(records), "evaluation-repeated-unit")
    require(
        all(
            r.unit_id.startswith("synthetic:")
            and r.group in (0, 1)
            and type(r.group) is int
            and type(r.positive_label) is bool
            for r in records
        ),
        "synthetic-evaluation-records-only",
    )
    result = [0, 0, 0, 0]
    for record in records:
        if record.positive_label:
            result[2 * record.group + 1] += 1
            result[2 * record.group] += classifier.predict(record.features)
    return result[0], result[1], result[2], result[3]


class HoldoutLedger:
    """Basic additive epsilon ledger for one observer, privacy unit and holdout version.

    Query IDs are idempotent only for identical cached releases. A new query ID
    spends again, even for the same model. Exceptions after reservation retain cost.
    This in-memory teaching ledger is not a durable concurrent release authority.
    """

    def __init__(
        self,
        observer: str,
        holdout_version: str,
        privacy_unit: str,
        model_digest: str,
        limit: Fraction,
    ) -> None:
        require(
            bool(observer)
            and holdout_version.startswith("synthetic:")
            and privacy_unit == "synthetic-record"
            and limit > 0,
            "holdout-scope",
        )
        self.observer, self.holdout_version, self.privacy_unit = (
            observer,
            holdout_version,
            privacy_unit,
        )
        self.model_digest, self.limit, self.spent = model_digest, limit, Fraction(0)
        self._releases: dict[str, tuple[str, tuple[float, ...] | None]] = {}
        self._holdout_digest: str | None = None

    def release(
        self,
        query_id: str,
        classifier: Classifier,
        records: tuple[SyntheticRecord, ...],
        epsilon: Fraction,
        noise: Callable[[], float],
    ) -> dict[str, Any]:
        require(classifier.digest() == self.model_digest, "classifier-not-frozen")
        require(query_id.startswith("synthetic:") and epsilon > 0, "evaluation-query")
        raw = counts(classifier, records)
        # Bind all contents, including records with Y=0, so holdout substitution fails.
        identity = (
            self.observer,
            self.holdout_version,
            self.privacy_unit,
            classifier.digest(),
            str(epsilon),
            tuple(
                (r.unit_id, r.group, r.positive_label, tuple(map(str, r.features))) for r in records
            ),
        )
        fingerprint = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        holdout_digest = hashlib.sha256(json.dumps(identity[-1]).encode()).hexdigest()
        require(self._holdout_digest in {None, holdout_digest}, "holdout-version-substitution")
        if query_id in self._releases:
            old, released = self._releases[query_id]
            require(
                old == fingerprint and released is not None, "query-substitution-or-failed-release"
            )
        else:
            require(self.spent + epsilon <= self.limit, "evaluation-budget-exhausted")
            self.spent += epsilon
            self._holdout_digest = holdout_digest
            self._releases[query_id] = (fingerprint, None)
            # noise is an externally supplied synthetic additive-noise tape, not a DP sampler.
            released = tuple(float(value) + noise() for value in raw)
            require(all(math.isfinite(x) for x in released), "evaluation-noise-invalid")
            self._releases[query_id] = fingerprint, released
        assert released is not None
        return {
            "status": "synthetic-simulation",
            "assurance": "no-implemented-DP-guarantee",
            "observer": self.observer,
            "holdout_version": self.holdout_version,
            "privacy_unit": self.privacy_unit,
            "model_digest": self.model_digest,
            "released_counts": list(released),
            "epsilon_charge": str(epsilon),
            "cumulative_epsilon_charge": str(self.spent),
            "limitations": [
                "Noise tape does not implement the ideal Laplace law.",
                "Only synthetic records accepted; no production release authority.",
            ],
        }


def private_gap_certificate(
    noisy_denominators: tuple[float, float],
    noisy_gap: float,
    *,
    epsilon: float,
    alpha: float,
    beta: float,
    fixed_classifier: bool,
    iid_units: bool,
    ideal_laplace_assumption: bool,
    missing_fractions: tuple[float, float] = (0, 0),
    distribution_shift_tv: tuple[float, float] = (0, 0),
) -> dict[str, Any]:
    """Post-process already released counts; never disclose exact sample sizes."""
    require(
        all(
            math.isfinite(x)
            for x in (
                *noisy_denominators,
                noisy_gap,
                epsilon,
                alpha,
                beta,
                *missing_fractions,
                *distribution_shift_tv,
            )
        ),
        "certificate-nonfinite",
    )
    require(
        epsilon > 0 and 0 < alpha < 1 and 0 < beta < 1 and alpha + beta < 1 and 0 <= noisy_gap <= 1,
        "certificate-domain",
    )
    require(
        all(0 <= x <= 1 for x in (*missing_fractions, *distribution_shift_tv)),
        "certificate-allowances",
    )
    result: dict[str, Any] = {
        "metric": "conditional-equal-opportunity-gap",
        "status": "inconclusive",
        "upper_bound": None,
        "confidence": 1 - alpha - beta,
        "measured_noisy_gap": noisy_gap,
        "limitations": [
            "Conditional confidence statement; no deployment fairness claim.",
            "Group-specific missingness/shift allowances must be externally justified.",
            "Finite-arithmetic DP mechanism remains a separate obligation.",
        ],
    }
    if not (fixed_classifier and iid_units and ideal_laplace_assumption):
        result["reason"] = "Required fixed-classifier, IID or ideal-noise assumption unavailable."
        return result
    b = 2 / epsilon * math.log(4 / beta)
    result["noise_bound"] = b
    if any(n <= 2 * b for n in noisy_denominators):
        result["reason"] = "Noisy denominator does not exceed twice the noise bound."
        return result
    errors = [2 * b / (n - 2 * b) for n in noisy_denominators]
    radii = [math.sqrt(math.log(4 / alpha) / (2 * (n - b))) for n in noisy_denominators]
    result.update(
        status="conditional-confidence",
        ratio_error_bounds=errors,
        sampling_radii=radii,
        missing_fractions=list(missing_fractions),
        distribution_shift_tv=list(distribution_shift_tv),
        upper_bound=min(
            1.0,
            noisy_gap
            + sum(errors)
            + sum(radii)
            + sum(missing_fractions)
            + sum(distribution_shift_tv),
        ),
    )
    return result


def measured_gap(raw: tuple[int, int, int, int]) -> Fraction:
    k0, n0, k1, n1 = raw
    require(
        all(type(v) is int for v in raw) and 0 <= k0 <= n0 and 0 <= k1 <= n1 and n0 > 0 and n1 > 0,
        "metric-count-domain",
    )
    return abs(Fraction(k0, n0) - Fraction(k1, n1))
