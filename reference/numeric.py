"""Independent arbitrary-precision specification oracle. Never imports Rust/torch."""

from __future__ import annotations

import math
import struct
from fractions import Fraction

CONTRACT_VERSION = "fzknum-1.0.0"
FIXTURE_VERSION = "numeric-v1"
HEADER = b"FZKNUM01" + struct.pack("<HHI", 1, 3, 16)


def integer(value: int, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("integer-range")
    return value


def quantize(value: float) -> int:
    if type(value) is not float or not math.isfinite(value) or not -2 <= value <= 2:
        raise ValueError("nonfinite-or-out-of-range")
    return round(Fraction.from_float(value) * 16)


def encode(w: int, x: list[int], y: list[int], counts: list[int]) -> bytes:
    if len(x) != 3 or len(y) != 3 or len(counts) != 3:
        raise ValueError("shape")
    output = HEADER + struct.pack("<q", integer(w, -32, 32))
    for xi, yi, count in zip(x, y, counts, strict=True):
        output += struct.pack(
            "<qqI", integer(xi, -32, 32), integer(yi, -32, 32), integer(count, 1, 4)
        )
    return output


def decode(data: bytes) -> tuple[int, list[int], list[int], list[int]]:
    if type(data) is not bytes or len(data) != 84 or data[:16] != HEADER:
        raise ValueError("canonical-length-or-header")
    w = struct.unpack_from("<q", data, 16)[0]
    triples = [struct.unpack_from("<qqI", data, 24 + 20 * i) for i in range(3)]
    x, y, counts = (list(v) for v in zip(*triples, strict=True))
    encode(w, x, y, counts)
    return w, x, y, counts


def evaluate(data: bytes) -> dict[str, int | list[int]]:
    w, x, y, counts = decode(data)
    predictions = [round(Fraction(w * xi, 16)) for xi in x]
    gradients = [
        round(Fraction((pi - yi) * xi, 16)) for pi, yi, xi in zip(predictions, y, x, strict=True)
    ]
    updates = [w - round(Fraction(gi, 4)) for gi in gradients]
    numerator = sum(ni * ui for ni, ui in zip(counts, updates, strict=True))
    return {
        "predictions": predictions,
        "gradients": gradients,
        "updates": updates,
        "numerator": numerator,
        "denominator": sum(counts),
        "output": round(Fraction(numerator, sum(counts))),
    }
