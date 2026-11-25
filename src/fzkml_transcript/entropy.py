"""Declared entropy assumptions and analytic selective-retry counterexamples."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from .algebra import Matrix, residual_covariance, squared_separation


@dataclass(frozen=True)
class EntropyPolicy:
    source_reference: str
    independent_of_data: bool
    independent_contributions: bool
    hidden_from_observer: bool
    inclusion_independent_of_noise: bool
    adversary_fixed_before_honest_seed: bool
    retry_rule: str = "one-shot"

    def require_available(self) -> None:
        if (
            not self.source_reference
            or not self.independent_of_data
            or not self.independent_contributions
            or not self.hidden_from_observer
            or not self.inclusion_independent_of_noise
            or not self.adversary_fixed_before_honest_seed
            or self.retry_rule != "one-shot"
        ):
            raise ValueError("honest conditional entropy/retry assumption unavailable")


class EntropyUseRegistry:
    """Track declared source-instance IDs, never secret seeds or unblinded hashes.

    A trusted entropy service must enforce that instance IDs refer to fresh
    protected draws. This reference cannot detect covert reuse under new IDs.
    """

    def __init__(self, policy: EntropyPolicy):
        policy.require_available()
        self._releases: dict[str, tuple[str, str]] = {}
        self._instances: set[str] = set()

    def bind(self, release_id: str, context_digest: str, entropy_instance_id: str) -> None:
        if not release_id or not context_digest or not entropy_instance_id:
            raise ValueError("release, locked context and external entropy instance required")
        descriptor = (context_digest, entropy_instance_id)
        old = self._releases.get(release_id)
        if old is not None:
            if old != descriptor:
                raise ValueError("release identifier cannot change context or entropy")
            return
        if entropy_instance_id in self._instances:
            raise ValueError("declared entropy instance reused across releases")
        self._releases[release_id] = descriptor
        self._instances.add(entropy_instance_id)


def require_residual_noise(
    policy: EntropyPolicy,
    loadings: dict[str, Matrix],
    survivors: frozenset[str],
    revealed: frozenset[str],
    shifts: tuple[tuple[Fraction, ...], ...],
    max_squared_cost: Fraction,
) -> Matrix:
    policy.require_available()
    if not shifts or max_squared_cost < 0:
        raise ValueError("declared sensitivity directions/bound required")
    covariance = residual_covariance(
        loadings, survivors, revealed, independent=policy.independent_contributions
    )
    for shift in shifts:
        value = squared_separation(covariance, shift)
        if value is None or value > max_squared_cost:
            raise ValueError("insufficient surviving unknown noise")
    return covariance


def half_normal_delta_floor(delta_over_sigma: float) -> float:
    if not math.isfinite(delta_over_sigma) or delta_over_sigma <= 0:
        raise ValueError("positive finite query difference / sigma required")
    # P[0 <= |Z| < Delta] for an ideal continuous Gaussian, not a circuit sampler.
    return math.erf(delta_over_sigma / math.sqrt(2))


def select_nonnegative(candidates: tuple[float, ...]) -> tuple[float, int]:
    """Finite deterministic attack trace; no source of live protected noise."""
    for attempt, value in enumerate(candidates, 1):
        if not math.isfinite(value):
            raise ValueError("finite synthetic candidate required")
        if value >= 0:
            return value, attempt
    raise ValueError("synthetic retry tape exhausted")


def one_shot_public_filter(output: float, threshold: float) -> float | None:
    if not math.isfinite(output) or not math.isfinite(threshold):
        raise ValueError("finite public output and threshold required")
    return output if output >= threshold else None


def xor_counts(bits: int, adversarial: int) -> dict[int, int]:
    """Enumerate the conditional-uniform XOR lemma for a fixed adversarial input."""
    if type(bits) is not int or not 1 <= bits <= 12:
        raise ValueError("bounded synthetic bit width required")
    if type(adversarial) is not int or not 0 <= adversarial < 2**bits:
        raise ValueError("invalid fixed adversarial contribution")
    return {honest ^ adversarial: 1 for honest in range(2**bits)}
