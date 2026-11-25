"""Exact analytical sequential/batch models, not observed prover performance."""

from __future__ import annotations

from fractions import Fraction

from .arithmetic import exact


def amdahl(f: Fraction, k: Fraction) -> Fraction:
    f, k = exact(f), exact(k)
    if not 0 <= f <= 1 or k <= 0:
        raise ValueError("amdahl-domain")
    return 1 / ((1 - f) + f / k)


def batch(a: Fraction, c: Fraction, b: int, spacing: Fraction) -> dict[str, Fraction]:
    a, c, spacing = exact(a), exact(c), exact(spacing)
    if a < 0 or c < 0 or type(b) is not int or b < 1 or spacing <= 0:
        raise ValueError("batch-domain")
    compute = a + b * c
    filling = Fraction(b - 1, 2) * spacing
    return {
        "compute": compute,
        "amortized_compute": compute / b,
        "mean_filling": filling,
        "mean_completion": filling + compute,
        "first_completion": (b - 1) * spacing + compute,
        "single_completion": a + c,
    }
