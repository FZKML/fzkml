"""Compatibility API for the canonical independent Python Fraction oracle."""

from python.fzkml_math.numeric import (
    CONTRACT_VERSION,
    FIXTURE_VERSION,
    HEADER,
    decode,
    encode,
    evaluate,
    integer,
    quantize,
)

__all__ = [
    "CONTRACT_VERSION",
    "FIXTURE_VERSION",
    "HEADER",
    "decode",
    "encode",
    "evaluate",
    "integer",
    "quantize",
]
