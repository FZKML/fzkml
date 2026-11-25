"""Exact rational folded geometric reference, not a distributed DP protocol.

CKS (2020), Lemma 29, is the selected discrete Laplace privacy result. See the
original finite-ring derivation in specs/protocol/DP-MECHANISM.md for equivalence.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from .integer import FixedSlotQuery, Vector


@dataclass(frozen=True)
class Geometric:
    numerator: int = 255
    denominator: int = 256
    modulus: int = 257

    def __post_init__(self) -> None:
        if not all(type(x) is int for x in (self.numerator, self.denominator, self.modulus)):
            raise ValueError("integer-mechanism-parameters")
        if not (
            1 <= self.numerator < self.denominator <= 256
            and 3 <= self.modulus <= 257
            and self.modulus % 2 == 1
        ):
            raise ValueError("unsupported-finite-mechanism")

    def weights(self) -> tuple[int, ...]:
        a, b, m = self.numerator, self.denominator, self.modulus
        return tuple(a**r * b ** (m - 1 - r) for r in range(m))

    def _geometric_residue(self, uniform: Callable[[int], int]) -> int:
        weights = self.weights()
        total = sum(weights)
        draw = uniform(total)
        if type(draw) is not int or not 0 <= draw < total:
            raise ValueError("uniform-source-contract")
        for residue, weight in enumerate(weights):
            if draw < weight:
                return residue
            draw -= weight
        raise AssertionError("unreachable-cdf")

    def _noise(self, uniform: Callable[[int], int]) -> int:
        return (self._geometric_residue(uniform) - self._geometric_residue(uniform)) % self.modulus

    def sample(self) -> int:
        """Independent exact uniform draws supplied by the OS-backed stdlib source."""
        return self._noise(secrets.randbelow)

    def pmf(self) -> tuple[Fraction, ...]:
        """Closed-form folded infinite law; independent of the inverse-CDF sampler."""
        p = Fraction(self.numerator, self.denominator)
        factor = (1 - p) / ((1 + p) * (1 - p**self.modulus))
        return tuple(factor * (p**r + p ** (self.modulus - r)) for r in range(self.modulus))

    def release(self, contributions: tuple[Vector, ...], query: FixedSlotQuery) -> Vector:
        answer = query.evaluate(contributions)
        return tuple_centered((answer[0] + self.sample(), answer[1] + self.sample()), self.modulus)

    def account(
        self, query: FixedSlotQuery, adjacency: str, multiplicity: int = 1, releases: int = 1
    ) -> tuple[Fraction, Fraction]:
        if type(releases) is not int or not 1 <= releases <= 1000:
            raise ValueError("release-count")
        delta = query.sensitivity(adjacency, multiplicity)
        # epsilon = releases * delta * ln(b/a) <= releases * delta * (b-a)/a.
        # Returning a rational upper bound avoids downward floating-point rounding.
        return Fraction(
            releases * delta * (self.denominator - self.numerator), self.numerator
        ), Fraction(0)


def tuple_centered(value: Vector, modulus: int) -> Vector:
    def center(x: int) -> int:
        return (x + modulus // 2) % modulus - modulus // 2

    return center(value[0]), center(value[1])
