"""Original exact quadratic precision experiment, separate from fzknum/book cases."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from .arithmetic import exact, rounded


def quadratic(scale: int, steps: int = 16, rate: Fraction = Fraction(1, 2)) -> dict[str, Any]:
    """f(w)=(w-1/3)^2/2, optimum1/3, declared L=mu=1, initial0.

    Compute the exact gradient, quantize the step at the selected scale, and
    reject state outside[-2,2]. This is a Python numerical experiment, not the
    proved scalar three-client program and not a claim about general optimizers.
    """
    rate = exact(rate)
    if (
        type(scale) is not int
        or scale not in (1, 2, 4, 8, 16, 32)
        or type(steps) is not int
        or not 1 <= steps <= 128
        or rate <= 0
    ):
        raise ValueError("quadratic-experiment-domain")
    target = Fraction(1, 3)
    w = Fraction(0)
    trace = []
    status = "completed"
    bound = abs(w - target)
    valid_contraction = 0 < rate < 2
    contraction = abs(1 - rate)
    for step in range(steps):
        intended = rate * (w - target)
        q = Fraction(rounded((intended * scale).numerator, (intended * scale).denominator), scale)
        candidate = w - q
        if abs(candidate) > 2:
            status = "rejected-state-domain"
            break
        perturbation = abs(q - intended)
        if perturbation > Fraction(1, 2 * scale):
            raise AssertionError("quantization-error-bound")
        bound = contraction * bound + Fraction(1, 2 * scale)
        w = candidate
        if abs(w - target) > bound:
            raise AssertionError("quadratic-recurrence-bound")
        trace.append(
            {
                "step": step + 1,
                "weight": str(w),
                "objective_gap": str((w - target) ** 2 / 2),
                "step_error": str(perturbation),
                "recurrence_bound": str(bound),
            }
        )
    return {
        "fixture_kind": "original-synthetic-not-book",
        "scale": scale,
        "learning_rate": str(rate),
        "smoothness": "1",
        "strong_convexity": "1",
        "analytic_optimum": str(target),
        "initial_weight": "0",
        "status": status,
        "steps_completed": len(trace),
        "final_weight": str(w),
        "objective_gap": str((w - target) ** 2 / 2),
        "stationarity_residual": str(abs(w - target)),
        "valid_contraction_assumption": valid_contraction,
        "trace": trace,
        "signed_i32_state_margin": 2**31 - 1 - 2 * scale,
        "constraint_cost": "not-measured-no-matching-circuit",
        "limitations": [
            "Finite deterministic toy trajectory, "
            "not global convergence evidence for other optimizers.",
            "State margin is for stored encoded weights only, "
            "not a circuit residual/no-wrap proof.",
            "No new book values or Rust numeric profile is inferred.",
        ],
    }


def class_status(
    original_scores: tuple[Fraction, ...],
    perturbed_scores: tuple[Fraction, ...],
    error_bound: Fraction,
) -> dict[str, bool | str]:
    if len(original_scores) < 2 or len(original_scores) != len(perturbed_scores):
        raise ValueError("classifier-shape")
    original = tuple(exact(v) for v in original_scores)
    perturbed = tuple(exact(v) for v in perturbed_scores)
    bound = exact(error_bound)
    if bound < 0 or any(abs(a - b) > bound for a, b in zip(original, perturbed, strict=True)):
        raise ValueError("unjustified-logit-error-bound")
    winner = max(range(len(original)), key=original.__getitem__)
    actual = max(range(len(perturbed)), key=perturbed.__getitem__)
    margin = min(original[winner] - s for i, s in enumerate(original) if i != winner)
    certified = margin > 2 * bound
    if certified and actual != winner:
        raise AssertionError("margin-certificate-contradiction")
    return {
        "observed_unchanged": actual == winner,
        "certified_unchanged": certified,
        "basis": "strict-margin-greater-than-twice-uniform-error-bound",
    }
