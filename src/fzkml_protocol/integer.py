"""Exact M0 arithmetic, plus an explicitly separate fixed-slot DP query."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

Vector = tuple[int, int]


def integer(value: int, bound: int) -> None:
    if type(value) is not int or abs(value) > bound:
        raise ValueError("integer-range")


def vector(value: Vector, bound: int) -> None:
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("vector-shape")
    for item in value:
        integer(item, bound)


def rounded(numerator: int, denominator: int) -> int:
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise ValueError("integer-division-domain")
    # floor(n/d+1/2), including negative ties; deliberately NOT fzknum's RNE profile.
    return (2 * numerator + denominator) // (2 * denominator)


def property_valid(delta: Vector) -> bool:
    try:
        vector(delta, 48)
    except ValueError:
        return False
    return sum(v * v for v in delta) <= 2 * 48**2


def training_step(model: Vector, features: Vector, label: int) -> Vector:
    vector(model, 16)
    vector(features, 16)
    integer(label, 16)
    prediction = rounded(sum(w * x for w, x in zip(model, features, strict=True)), 16)
    error = prediction - label
    delta = tuple(-rounded(error * x, 16) for x in features)
    result = (delta[0], delta[1])
    if not property_valid(result):
        raise ValueError("update-rejected")
    return result


def training_relation(model: Vector, features: Vector, label: int, delta: Vector) -> bool:
    try:
        return property_valid(delta) and training_step(model, features, label) == delta
    except ValueError:
        return False


def loss(model: Vector, features: Vector, label: int) -> Fraction:
    prediction = Fraction(sum(w * x for w, x in zip(model, features, strict=True)), 16**2)
    return (prediction - Fraction(label, 16)) ** 2


@dataclass(frozen=True)
class FixedSlotQuery:
    """4 public slots, 2 coordinates, clamp each integer before a fixed /4."""

    cap: int = 48
    slots: int = 4
    dimensions: int = 2

    def __post_init__(self) -> None:
        if not all(type(x) is int for x in (self.cap, self.slots, self.dimensions)) or (
            self.cap,
            self.slots,
            self.dimensions,
        ) != (48, 4, 2):
            raise ValueError("unsupported-query-profile")

    def evaluate(self, contributions: tuple[Vector, ...]) -> Vector:
        if not isinstance(contributions, tuple) or len(contributions) != self.slots:
            raise ValueError("fixed-public-roster-required")
        clipped = []
        for row in contributions:
            vector(row, 2**31 - 1)
            clipped.append(tuple(max(-self.cap, min(self.cap, x)) for x in row))
        return (
            rounded(sum(row[0] for row in clipped), self.slots),
            rounded(sum(row[1] for row in clipped), self.slots),
        )

    def sensitivity(self, adjacency: str, multiplicity: int = 1) -> int:
        if type(multiplicity) is not int or not 1 <= multiplicity <= self.slots:
            raise ValueError("contribution-multiplicity")
        if adjacency not in {"add-remove-zero-slot", "replace-slot"}:
            raise ValueError("unsupported-adjacency")
        factor = 1 if adjacency == "add-remove-zero-slot" else 2
        per_coordinate_change = factor * self.cap * multiplicity
        # Exact upper bound after rounded integer division: |rnd(x/N)-rnd(y/N)|<=ceil(|x-y|/N).
        return self.dimensions * ((per_coordinate_change + self.slots - 1) // self.slots)
