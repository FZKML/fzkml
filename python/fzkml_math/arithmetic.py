"""Arbitrary-precision primitives and an explicit manuscript-only profile.

No native binding is imported. Generic arithmetic never silently imposes machine
integer overflow; bounded encodings and field interpretation are separate checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

Rounding = Literal["nearest-even", "nearest-positive"]


def exact(value: int | Fraction) -> Fraction:
    if type(value) is not int and not isinstance(value, Fraction):
        raise ValueError("exact-integer-or-rational-required")
    return Fraction(value)


def rounded(n: int, d: int, rule: Rounding = "nearest-even") -> int:
    if type(n) is not int or type(d) is not int or d <= 0:
        raise ValueError("positive-integer-denominator-required")
    if rule == "nearest-even":
        return round(Fraction(n, d))
    if rule == "nearest-positive":
        return (2 * n + d) // (2 * d)
    raise ValueError("unsupported-rounding-profile")


def signed_field(value: int, modulus: int, bound: int) -> int:
    if (
        any(type(v) is not int for v in (value, modulus, bound))
        or not (0 <= bound and 2 * bound < modulus)
        or abs(value) > bound
    ):
        raise ValueError("bounded-signed-field-domain")
    return value % modulus


def lift_field(value: int, modulus: int, bound: int) -> int:
    if type(value) is not int or type(modulus) is not int or not 0 <= value < modulus:
        raise ValueError("noncanonical-field-residue")
    signed = value if value <= modulus // 2 else value - modulus
    signed_field(signed, modulus, bound)
    return signed


def no_wrap_residual(residual: int, modulus: int, bound: int) -> bool:
    if (
        any(type(v) is not int for v in (residual, modulus, bound))
        or not 0 <= bound < modulus
        or abs(residual) > bound
    ):
        raise ValueError("strict-residual-bound-required")
    return residual % modulus == 0


@dataclass(frozen=True)
class BookStep:
    dot: int
    prediction: int
    residual: int
    gradients: tuple[int, ...]
    updated: tuple[int, ...]
    loss_before: Fraction
    loss_after: Fraction
    rounded_prediction_after: int
    rounded_residual_loss_after: Fraction


def manuscript_step(w: tuple[int, ...], x: tuple[int, ...], y: int) -> BookStep:
    """Chapter40 profile only: scale16, rate1, two features, positive-infinity ties."""
    if len(w) != 2 or len(x) != 2 or any(type(v) is not int or abs(v) > 16 for v in (*w, *x, y)):
        raise ValueError("manuscript-ch40-input-domain")
    dot = sum(a * b for a, b in zip(w, x, strict=True))
    prediction = rounded(dot, 16, "nearest-positive")
    residual = prediction - y
    gradients = tuple(rounded(residual * v, 16, "nearest-positive") for v in x)
    updated = tuple(a - g for a, g in zip(w, gradients, strict=True))

    def loss(weights: tuple[int, ...]) -> Fraction:
        e = Fraction(sum(a * b for a, b in zip(weights, x, strict=True)), 256) - Fraction(y, 16)
        return e * e / 2

    rounded_prediction_after = rounded(
        sum(a * b for a, b in zip(updated, x, strict=True)), 16, "nearest-positive"
    )
    rounded_error = Fraction(rounded_prediction_after - y, 16)
    return BookStep(
        dot,
        prediction,
        residual,
        gradients,
        updated,
        loss(w),
        loss(updated),
        rounded_prediction_after,
        rounded_error**2 / 2,
    )


def floating_scalar(
    w: float, x: tuple[float, ...], y: tuple[float, ...], weights: tuple[int, ...]
) -> float:
    """Ordinary floating baseline; no clipping/rounding and no conformance assertion."""
    import math

    if (
        len(x) != 3
        or len(y) != 3
        or len(weights) != 3
        or not all(math.isfinite(v) for v in (w, *x, *y))
        or any(type(n) is not int or n <= 0 for n in weights)
    ):
        raise ValueError("floating-baseline-domain")
    return sum(n * (w - (w * a - b) * a / 4) for a, b, n in zip(x, y, weights, strict=True)) / sum(
        weights
    )
