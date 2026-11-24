"""Exact fixed-public-denominator lattice analysis; no continuous-to-integer shortcut."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .arithmetic import rounded


def rounded_change_bound(
    numerator_change: int, denominator: int, rule: str = "nearest-even"
) -> int:
    if (
        type(numerator_change) is not int
        or numerator_change < 0
        or type(denominator) is not int
        or denominator <= 0
    ):
        raise ValueError("nonnegative-change-positive-denominator")
    q, r = divmod(numerator_change, denominator)
    if rule == "nearest-positive":
        return q + int(r > 0)
    if rule != "nearest-even":
        raise ValueError("unsupported-rounding-profile")
    # Odd integer translations swap tie parity; half-integer lattice points
    # exist only when the denominator is even. Even translations preserve RNE.
    return q + int(r > 0 or (r == 0 and q % 2 == 1 and denominator % 2 == 0))


@dataclass(frozen=True)
class FixedMean:
    cap: int
    weights: tuple[int, ...]

    def __post_init__(self) -> None:
        if (
            type(self.weights) is not tuple
            or type(self.cap) is not int
            or not 0 < self.cap <= 80
            or not 1 <= len(self.weights) <= 8
            or any(type(w) is not int or not 1 <= w <= 4 for w in self.weights)
        ):
            raise ValueError("fixed-mean-profile")

    def release(self, values: tuple[int, ...]) -> int:
        if len(values) != len(self.weights) or any(
            type(v) is not int or abs(v) > self.cap for v in values
        ):
            raise ValueError("declared-transmitted-domain")
        return rounded(
            sum(w * v for w, v in zip(self.weights, values, strict=True)), sum(self.weights)
        )

    def bound(self, adjacency: str, multiplicity: int = 1) -> int:
        if (
            adjacency not in {"add-remove-zero-slot", "replace-slot"}
            or type(multiplicity) is not int
            or not 1 <= multiplicity <= len(self.weights)
        ):
            raise ValueError("adjacency-or-contribution-multiplicity")
        change = (
            self.cap
            * sum(sorted(self.weights, reverse=True)[:multiplicity])
            * (2 if adjacency == "replace-slot" else 1)
        )
        return rounded_change_bound(change, sum(self.weights))

    def enumerate_sensitivity(
        self, adjacency: str
    ) -> tuple[int, tuple[tuple[int, ...], tuple[int, ...]]]:
        if (
            self.cap > 3
            or len(self.weights) > 4
            or adjacency not in {"add-remove-zero-slot", "replace-slot"}
        ):
            raise ValueError("bounded-enumeration-only")
        best = 0
        witness = (tuple(0 for _ in self.weights), tuple(0 for _ in self.weights))
        domain = range(-self.cap, self.cap + 1)
        for row in product(domain, repeat=len(self.weights)):
            for i in range(len(row)):
                replacements = domain if adjacency == "replace-slot" else (0,)
                for value in replacements:
                    other = (*row[:i], value, *row[i + 1 :])
                    change = abs(self.release(row) - self.release(other))
                    if change > best:
                        best, witness = change, (row, other)
        return best, witness
