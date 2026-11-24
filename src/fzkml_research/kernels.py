"""Exact CPU modular matrix reference and layout optimization. No approximate ML path."""

from __future__ import annotations

from fzkml_ci.validate import require

Matrix = tuple[tuple[int, ...], ...]
RELATION = "modular-matmul-v1"
NUMERICAL_SEMANTICS = "unbounded-integer-dot-then-mod-v1"


def validate(a: Matrix, b: Matrix, modulus: int) -> None:
    require(type(modulus) is int and 2 <= modulus < 2**64, "modulus-domain")
    require(bool(a) and bool(b) and bool(a[0]) and bool(b[0]), "matrix-empty")
    require(len(a) <= 128 and len(b) <= 128 and len(b[0]) <= 128, "matrix-size")
    require(
        all(len(row) == len(b) for row in a) and all(len(row) == len(b[0]) for row in b),
        "matrix-shape",
    )
    require(
        all(
            type(v) is int and -(2**64) < v < 2**64
            for matrix in (a, b)
            for row in matrix
            for v in row
        ),
        "matrix-integer-domain",
    )


def reference(a: Matrix, b: Matrix, modulus: int) -> Matrix:
    validate(a, b, modulus)
    output = []
    for row in a:
        values = []
        for j in range(len(b[0])):
            total = 0
            for k, value in enumerate(row):
                total = (total + (value * b[k][j]) % modulus) % modulus
            values.append(total)
        output.append(tuple(values))
    return tuple(output)


def transposed(a: Matrix, b: Matrix, modulus: int) -> Matrix:
    validate(a, b, modulus)
    columns = tuple(zip(*b, strict=True))
    return tuple(
        tuple(sum(x * y for x, y in zip(row, column, strict=True)) % modulus for column in columns)
        for row in a
    )
