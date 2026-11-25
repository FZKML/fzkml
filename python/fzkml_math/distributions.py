"""Whole finite-law calculations, distinct from empirical sampling tests or general DP proofs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from fractions import Fraction
from math import lcm
from typing import TypeVar

K = TypeVar("K")


def law(values: Mapping[K, Fraction]) -> dict[K, Fraction]:
    if (
        not values
        or any(not isinstance(v, Fraction) or v < 0 for v in values.values())
        or sum(values.values()) != 1
    ):
        raise ValueError("normalized-exact-finite-law-required")
    return dict(values)


def hockey_stick(
    p: Mapping[K, Fraction], q: Mapping[K, Fraction], exp_epsilon: Fraction
) -> Fraction:
    p, q = law(p), law(q)
    if not isinstance(exp_epsilon, Fraction) or exp_epsilon < 1:
        raise ValueError("exact-exp-epsilon-at-least-one")
    return sum(
        (
            max(Fraction(0), p.get(k, Fraction(0)) - exp_epsilon * q.get(k, Fraction(0)))
            for k in p.keys() | q.keys()
        ),
        Fraction(0),
    )


def postprocess(p: Mapping[int, Fraction], mapping: Callable[[int], int]) -> dict[int, Fraction]:
    out: dict[int, Fraction] = {}
    for k, v in law(p).items():
        key = mapping(k)
        out[key] = out.get(key, Fraction(0)) + v
    return out


def conditioned(p: Mapping[int, Fraction], event: Callable[[int], bool]) -> dict[int, Fraction]:
    selected = {k: v for k, v in law(p).items() if event(k)}
    mass = sum(selected.values())
    if mass == 0:
        raise ValueError("zero-probability-conditioning")
    return {k: v / mass for k, v in selected.items()}


def cyclic_geometric(a: int, b: int, modulus: int) -> dict[int, Fraction]:
    """Independent polynomial convolution of two finite geometric residues.

    This derives the exact probability law; it does not supply a private sampler.
    It is intentionally independent of PR70's closed-form folded infinite PMF.
    """
    if (
        any(type(x) is not int for x in (a, b, modulus))
        or not 0 < a < b <= 256
        or not 3 <= modulus <= 33
        or modulus % 2 != 1
    ):
        raise ValueError("bounded-finite-law-profile")
    weights = [a**r * b ** (modulus - 1 - r) for r in range(modulus)]
    total = sum(weights)
    result = {r: Fraction(0) for r in range(modulus)}
    for i, wi in enumerate(weights):
        for j, wj in enumerate(weights):
            result[(i - j) % modulus] += Fraction(wi * wj, total * total)
    return law(result)


def exact_uniform_cdf(p: Mapping[int, Fraction], draw: int) -> int:
    """Deterministic inverse-CDF check on a supplied public test draw, no RNG."""
    p = law(p)
    denominator = lcm(*(v.denominator for v in p.values()))
    if type(draw) is not int or not 0 <= draw < denominator:
        raise ValueError("public-test-draw-domain")
    for k, v in sorted(p.items()):
        mass = v.numerator * (denominator // v.denominator)
        if draw < mass:
            return k
        draw -= mass
    raise AssertionError("unreachable-cdf")
