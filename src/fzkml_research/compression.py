"""Exact rational synthetic compression, lineage binding and conservative diameters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from fzkml_ci.validate import require

Vector = tuple[Fraction, ...]


def norm_squared(x: Vector) -> Fraction:
    require(0 < len(x) <= 32 and all(isinstance(v, Fraction) for v in x), "exact-rational-vector")
    return sum((v * v for v in x), Fraction(0))


def encode(matrix: tuple[Vector, ...], x: Vector) -> Vector:
    require(bool(x) and all(len(row) == len(x) for row in matrix), "encoder-shape")
    return tuple(sum((a * b for a, b in zip(row, x, strict=True)), Fraction(0)) for row in matrix)


def kernel_vector(matrix: tuple[Vector, ...]) -> Vector:
    """Construct a null vector by exact RREF; reject injective maps."""
    require(bool(matrix) and 0 < len(matrix[0]) <= 32 and len(matrix) <= 32, "kernel-size")
    columns = len(matrix[0])
    require(all(len(row) == columns for row in matrix), "encoder-shape")
    rows = [list(row) for row in matrix]
    pivots: list[int] = []
    for column in range(columns):
        pivot = next((r for r in range(len(pivots), len(rows)) if rows[r][column]), None)
        if pivot is None:
            continue
        current = len(pivots)
        rows[current], rows[pivot] = rows[pivot], rows[current]
        divisor = rows[current][column]
        rows[current] = [v / divisor for v in rows[current]]
        for r in range(len(rows)):
            if r != current:
                factor = rows[r][column]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[current], strict=True)]
        pivots.append(column)
    free = next((c for c in range(columns) if c not in pivots), None)
    require(free is not None, "injective-encoder-no-kernel")
    assert free is not None
    result = [Fraction(0)] * columns
    result[free] = Fraction(1)
    for r, c in enumerate(pivots):
        result[c] = -rows[r][free]
    vector = tuple(result)
    require(norm_squared(vector) > 0 and not any(encode(matrix, vector)), "kernel-construction")
    return vector


def dense_bound_from_projection(matrix: tuple[Vector, ...]) -> None:
    # This API never promotes a projected norm claim to a dense norm claim.
    require(bool(matrix), "encoder-shape")
    raise ValueError("dense-bound-needs-an-independent-dense-check-or-inverse-operator-bound")


@dataclass(frozen=True)
class Compressor:
    version: str
    mode: Literal["top1", "unbiased-random1", "top1-postclip"]
    dimension: int
    bound: Fraction
    public_synthetic_tape: tuple[int, ...] = ()

    def validate(self) -> None:
        require(
            bool(self.version) and self.mode in {"top1", "unbiased-random1", "top1-postclip"},
            "compressor-version-mode",
        )
        require(
            type(self.dimension) is int
            and 1 <= self.dimension <= 32
            and isinstance(self.bound, Fraction)
            and self.bound > 0,
            "compressor-domain",
        )
        require(
            all(type(i) is int and 0 <= i < self.dimension for i in self.public_synthetic_tape),
            "compressor-tape",
        )
        require(
            self.mode != "unbiased-random1" or bool(self.public_synthetic_tape), "compressor-tape"
        )

    def digest(self) -> str:
        self.validate()
        payload = (
            self.version,
            self.mode,
            self.dimension,
            str(self.bound),
            self.public_synthetic_tape,
        )
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    round: int
    residual: Vector
    compressor_digest: str
    model_lineage: str
    parent_digest: str

    def digest(self) -> str:
        data = (
            self.round,
            tuple(map(str, self.residual)),
            self.compressor_digest,
            self.model_lineage,
            self.parent_digest,
        )
        return hashlib.sha256(json.dumps(data).encode()).hexdigest()


class CompressionChain:
    """Synthetic state machine. Hash binding is not a hiding commitment or a ZK proof."""

    def __init__(self, compressor: Compressor, model_lineage: str) -> None:
        compressor.validate()
        require(bool(model_lineage), "model-lineage-required")
        self.compressor = compressor
        self.snapshot = Snapshot(
            0, (Fraction(0),) * compressor.dimension, compressor.digest(), model_lineage, "genesis"
        )

    def step(
        self, update: Vector, *, expected_digest: str, round_id: int, model_lineage: str
    ) -> Vector:
        config, before = self.compressor, self.snapshot
        require(type(round_id) is int and 0 <= round_id < 1000, "compression-round-domain")
        require(
            before.digest() == expected_digest and before.round == round_id,
            "compression-stale-state",
        )
        require(
            config.digest() == before.compressor_digest and model_lineage == before.model_lineage,
            "compression-policy-or-lineage-change",
        )
        require(
            len(update) == config.dimension and norm_squared(update) <= config.bound**2,
            "fresh-update-domain",
        )
        combined = tuple(a + b for a, b in zip(update, before.residual, strict=True))
        if config.mode == "unbiased-random1":
            require(round_id < len(config.public_synthetic_tape), "compression-tape-exhausted")
            coordinate = config.public_synthetic_tape[round_id]
            value = config.dimension * combined[coordinate]
        else:
            coordinate = max(range(config.dimension), key=lambda i: (abs(combined[i]), -i))
            value = combined[coordinate]
            if config.mode == "top1-postclip":
                value = min(config.bound, max(-config.bound, value))
        sent = tuple(value if i == coordinate else Fraction(0) for i in range(config.dimension))
        residual = tuple(a - b for a, b in zip(combined, sent, strict=True))
        self.snapshot = Snapshot(
            before.round + 1,
            residual,
            before.compressor_digest,
            before.model_lineage,
            before.digest(),
        )
        return sent


def replacement_l2_bound(
    config: Compressor, preceding_rounds: int, error_feedback: bool
) -> Fraction:
    """Range-diameter bound for the actual transmitted vector, across full histories.

    Inputs have L2 <= C. Fixed-length tape is part of the synthetic policy. This
    bounds one released vector, not the complete observer transcript or a DP law.
    """
    config.validate()
    require(type(preceding_rounds) is int and 0 <= preceding_rounds <= 1000, "sensitivity-rounds")
    if config.mode == "top1-postclip":
        return 2 * config.bound
    residual_bound = Fraction(0)
    factor = max(1, config.dimension - 1) if config.mode == "unbiased-random1" else 1
    if error_feedback:
        for _ in range(preceding_rounds):
            residual_bound = factor * (config.bound + residual_bound)
    gain = config.dimension if config.mode == "unbiased-random1" else 1
    return 2 * gain * (config.bound + residual_bound)
