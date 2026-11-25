"""Small exact rational linear algebra, independent of the native proof circuit."""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction as Q
from typing import Any

Matrix = tuple[tuple[Q, ...], ...]


def ensure(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def matrix(rows: list[list[int | Q]] | Matrix) -> Matrix:
    ensure(0 < len(rows) <= 8, "matrix-row-bound")
    width = len(rows[0])
    ensure(0 < width <= 8 and all(len(r) == width for r in rows), "matrix-shape")
    ensure(all(type(x) in {int, Q} for row in rows for x in row), "exact-scalars-only")
    result = tuple(tuple(Q(x) for x in row) for row in rows)
    ensure(
        all(
            max(abs(x.numerator).bit_length(), x.denominator.bit_length()) <= 128
            for row in result
            for x in row
        ),
        "scalar-bit-bound",
    )
    return result


def transpose(a: Matrix) -> Matrix:
    return tuple(zip(*a, strict=True))


def add(a: Matrix, b: Matrix) -> Matrix:
    ensure(len(a) == len(b) and len(a[0]) == len(b[0]), "addition-shape")
    return matrix([[x + y for x, y in zip(r, s, strict=True)] for r, s in zip(a, b, strict=True)])


def scale(a: Matrix, factor: Q) -> Matrix:
    return matrix([[factor * x for x in row] for row in a])


def multiply(a: Matrix, b: Matrix) -> Matrix:
    ensure(len(a[0]) == len(b), "product-shape")
    return matrix(
        [
            [sum((x * y for x, y in zip(row, col, strict=True)), Q(0)) for col in transpose(b)]
            for row in a
        ]
    )


def norm2(a: Matrix) -> Q:
    return sum((x * x for row in a for x in row), Q(0))


def identity(n: int) -> Matrix:
    ensure(1 <= n <= 8, "dimension-bound")
    return matrix([[int(i == j) for j in range(n)] for i in range(n)])


def solve(a: Matrix, b: Matrix) -> Matrix:
    n = len(a)
    ensure(len(a[0]) == n and len(b) == n, "solve-shape")
    rows = [list(a[i] + b[i]) for i in range(n)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if rows[i][col]), None)
        ensure(pivot is not None, "singular-matrix")
        assert pivot is not None
        rows[col], rows[pivot] = rows[pivot], rows[col]
        value = rows[col][col]
        rows[col] = [x / value for x in rows[col]]
        for i in range(n):
            if i != col:
                factor = rows[i][col]
                rows[i] = [x - factor * y for x, y in zip(rows[i], rows[col], strict=True)]
    return matrix(tuple(tuple(row[n:]) for row in rows))


def rank(a: Matrix) -> int:
    rows = [list(row) for row in a]
    pivot_row = 0
    for col in range(len(a[0])):
        pivot = next((i for i in range(pivot_row, len(a)) if rows[i][col]), None)
        if pivot is None:
            continue
        rows[pivot_row], rows[pivot] = rows[pivot], rows[pivot_row]
        value = rows[pivot_row][col]
        rows[pivot_row] = [x / value for x in rows[pivot_row]]
        for i in range(pivot_row + 1, len(a)):
            factor = rows[i][col]
            rows[i] = [x - factor * y for x, y in zip(rows[i], rows[pivot_row], strict=True)]
        pivot_row += 1
        if pivot_row == len(a):
            break
    return pivot_row


def sqrt_upper(value: Q) -> Q:
    ensure(value >= 0, "negative-square")
    units = 1_000_000
    ceiling = (value.numerator * units * units + value.denominator - 1) // value.denominator
    root = math.isqrt(ceiling)
    return Q(root + int(root * root < ceiling), units)


def rne(value: Q) -> int:
    q, r = divmod(value.numerator, value.denominator)
    return q + int(2 * r > value.denominator or (2 * r == value.denominator and q % 2 != 0))


def canonical(value: Any) -> bytes:
    def encode(item: Any) -> Any:
        if isinstance(item, Q):
            return str(item)
        if isinstance(item, dict):
            return {k: encode(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [encode(v) for v in item]
        return item

    return json.dumps(
        encode(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()
