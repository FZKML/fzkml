"""Regenerate only original synthetic vectors; book inputs require source inspection."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from python.fzkml_math.datasets import representation_digest, synthetic  # noqa: E402
from python.fzkml_math.numeric import CONTRACT_VERSION, encode, evaluate  # noqa: E402


def generate() -> dict[str, dict[str, object]]:
    batches = [
        (1, [0, 0, 8], [0, 0, 8], [1, 1, 2]),
        (-1, [0, 0, 8], [0, 0, -8], [1, 1, 2]),
        (32, [32, -32, 0], [-32, 32, 0], [4, 1, 4]),
        (-32, [-32, 32, 0], [32, -32, 0], [1, 4, 1]),
    ]
    for w in (-32, -1, 0, 1, 32):
        for x in (-32, -8, 0, 8, 32):
            for y in (-32, -1, 0, 1, 32):
                batches.append((w, [x, x, x], [y, y, y], [1, 2, 4]))
    vectors = [{"canonical_hex": (b := encode(*a)).hex(), "expected": evaluate(b)} for a in batches]
    zero = encode(0, [0] * 3, [0] * 3, [1] * 3)
    invalid = [
        b"",
        zero[:15],
        zero[:-1],
        zero + b"\x00",
        zero[:8] + struct.pack("<HHI", 1, 3, 0) + zero[16:],
        zero[:8] + struct.pack("<HHI", 2, 3, 16) + zero[16:],
        zero[:8] + struct.pack("<HHI", 1, 4, 16) + zero[16:],
    ]
    for value in (0, 5, 2**32 - 1):
        invalid.append(zero[:40] + struct.pack("<I", value) + zero[44:])
    for value in (-(2**63), -33, 33, 2**63 - 1):
        invalid.append(zero[:16] + struct.pack("<q", value) + zero[24:])
    rows = synthetic()
    return {
        "s02-boundaries-v1.json": {
            "fixture_version": "s02-boundaries-1.0.0",
            "contract_version": CONTRACT_VERSION,
            "contract_sha256": hashlib.sha256(
                (ROOT / "specs/numeric-contract-v1.json").read_bytes()
            ).hexdigest(),
            "origin": "original synthetic, not manuscript values",
            "valid": vectors,
            "invalid_hex": [b.hex() for b in invalid],
            "limitations": [
                "Full-state aggregation; RNE is not generally invariant "
                "under odd integer translation.",
                "Preserves assets/public/numeric-v1.json unchanged.",
            ],
        },
        "s02-data-v1.json": {
            "fixture_version": "s02-data-1.0.0",
            "origin": "original deterministic public synthetic records",
            "seed": 20261124,
            "license": "Apache-2.0",
            "representation_sha256": representation_digest(rows),
            "records": [asdict(r) for r in rows],
            "limitations": [
                "Multiple records per entity are clustered, not IID mechanism runs.",
                "Representation commitment establishes neither truth nor consent "
                "or population coverage.",
            ],
        },
    }


if __name__ == "__main__":
    for name, value in generate().items():
        path = ROOT / "tests/vectors/synthetic" / name
        text = json.dumps(value, indent=2) + "\n"
        if sys.argv[1:] == ["--check"]:
            if path.read_text() != text:
                raise ValueError("s02-fixture-regeneration-drift")
        elif len(sys.argv) == 1:
            path.write_text(text)
        else:
            raise ValueError("unsupported-generator-argument")
    print("S02 deterministic synthetic vectors verified")
