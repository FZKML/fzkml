"""Deterministic independent exact vectors and actual cross-language rejection."""

from __future__ import annotations

import copy
import json
import random
import struct
import subprocess
from fractions import Fraction
from typing import Any

from fzkml_ci.validate import ROOT, load, require
from reference.numeric import encode, evaluate

from .common import check_schema, file_sha, provenance, save, sha

MODULUS = 21888242871839275222246405745257275088548364400416034343698204186575808495617
FIXTURE = "assets/public/ci14-golden-v1.json"
SIDECAR = "ci/assurance/ci14-golden-v1.sha256"


class ConformanceFailure(ValueError):
    def __init__(self, operation: str, case: str, exit_code: int, expected: str, actual: str):
        super().__init__("native-conformance-mismatch")
        self.detail = {
            "operation": operation,
            "case": case,
            "native_exit_code": exit_code,
            "expected_digest": sha(expected.encode()),
            "observed_digest": sha(actual.encode()),
        }


def generate() -> dict[str, Any]:
    rounding = [
        {"n": n, "d": d, "floor": n // d, "remainder": n % d, "rounded": round(Fraction(n, d))}
        for n in range(-32, 33)
        for d in range(1, 17)
    ]
    signed = [
        {
            "integer": n,
            "signed_le_hex": n.to_bytes(8, "little", signed=True).hex(),
            "field_decimal": str(n % MODULUS),
            "field_le_hex": (n % MODULUS).to_bytes(32, "little").hex(),
        }
        for n in [0, 1, -1, 32, -32, -(1 << 63), (1 << 63) - 1]
    ]
    rng = random.Random(20261125)
    batches = [
        (8, [16, -8, 24], [16, -16, 8], [1, 2, 1]),
        (-32, [-32, 32, -32], [32, -32, -32], [4, 4, 4]),
        (32, [32, -32, 32], [-32, 32, 32], [1, 4, 1]),
        (32, [8, 8, 8], [32, 32, 32], [1, 1, 1]),
    ]
    batches += [
        (
            rng.randint(-32, 32),
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(1, 4) for _ in range(3)],
        )
        for _ in range(32)
    ]
    valid = [
        {"canonical_hex": encode(*args).hex(), "expected": evaluate(encode(*args))}
        for args in batches
    ]
    zero = encode(0, [0, 0, 0], [0, 0, 0], [1, 1, 1])
    invalid = [
        zero[:-1],
        zero + b"\0",
        zero[:16] + struct.pack("<q", 33) + zero[24:],
        zero[:16] + struct.pack("<q", -33) + zero[24:],
        zero[:40] + struct.pack("<I", 0) + zero[44:],
        zero[:40] + struct.pack("<I", 5) + zero[44:],
    ]
    return {
        "version": "ci14-1.0.0",
        "relation": "fzknum-1.0.0",
        "field": "bn254-scalar-Fr",
        "modulus": str(MODULUS),
        "signed_encoding": "i64-twos-complement-little-endian",
        "field_encoding": "canonical-32-byte-little-endian",
        "rounding": "nearest-ties-to-even-euclidean-division",
        "input_domain": {
            "w_min": -32,
            "w_max": 32,
            "x_y_min": -32,
            "x_y_max": 32,
            "count_min": 1,
            "count_max": 4,
            "clients": 3,
            "scale": 16,
        },
        "seed": 20261125,
        "contract_digest": file_sha("specs/numeric-contract-v1.json"),
        "oracle_digest": file_sha("reference/numeric.py"),
        "generator_digest": file_sha("src/fzkml_assurance/golden.py"),
        "classification": "original-implementation-vectors-not-book-numerical-transcription",
        "rounding_vectors": rounding,
        "signed_vectors": signed,
        "batch_vectors": valid,
        "invalid_i64": ["9223372036854775808", "-9223372036854775809", "NaN", "inf", "1.0"],
        "invalid_batch_hex": [x.hex() for x in invalid],
    }


def encoded(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def mutate(value: dict[str, Any], name: str) -> dict[str, Any]:
    value = copy.deepcopy(value)
    if name == "rounding-tie":
        next(r for r in value["rounding_vectors"] if r["n"] == 1 and r["d"] == 2)["rounded"] = 1
    elif name == "negative-division":
        next(r for r in value["rounding_vectors"] if r["n"] == -3 and r["d"] == 2)["rounded"] = -1
    elif name == "byte-order":
        row = next(r for r in value["signed_vectors"] if r["integer"] == -32)
        row["field_le_hex"] = bytes.fromhex(row["field_le_hex"])[::-1].hex()
    else:
        raise ValueError("unknown-mutation")
    return value


def native(binary: str, args: list[str], data: bytes = b"") -> tuple[int, str]:
    result = subprocess.run(
        [str(ROOT / binary), *args],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=10,
    )
    require(len(result.stdout) <= 4000, "golden-native-output-bound")
    return result.returncode, result.stdout.decode().strip()


def cross_check(value: dict[str, Any]) -> dict[str, int]:
    check_schema(value, "golden")
    for row in value["rounding_vectors"]:
        rc, output = native(
            "target/release/fzkml-contract", ["round", str(row["n"]), str(row["d"])]
        )
        if rc != 0 or output != str(row["rounded"]):
            raise ConformanceFailure(
                "round", f"{row['n']}/{row['d']}", rc, str(row["rounded"]), output
            )
        require(
            row["n"] == row["floor"] * row["d"] + row["remainder"]
            and 0 <= row["remainder"] < row["d"],
            "euclidean-division-mismatch",
        )
    for row in value["signed_vectors"]:
        rc, text = native("target/release/fzkml-assurance", ["field", str(row["integer"])])
        require(rc == 0, "native-field-failed")
        actual = json.loads(text)
        if actual["modulus"] != value["modulus"] or any(actual[k] != v for k, v in row.items()):
            raise ConformanceFailure(
                "field",
                str(row["integer"]),
                rc,
                json.dumps(row, sort_keys=True),
                json.dumps(actual, sort_keys=True),
            )
    for row in value["batch_vectors"]:
        rc, out = native(
            "target/release/fzkml-contract", ["evaluate"], row["canonical_hex"].encode() + b"\n"
        )
        require(rc == 0 and out == str(row["expected"]["output"]), "cross-language-batch-mismatch")
    for value_i64 in value["invalid_i64"]:
        rc, _ = native("target/release/fzkml-assurance", ["field", value_i64])
        require(rc != 0, "invalid-signed-value-accepted")
    for data in value["invalid_batch_hex"]:
        rc, _ = native("target/release/fzkml-contract", ["evaluate"], data.encode() + b"\n")
        require(rc != 0, "invalid-batch-accepted")
    return {
        "rounding": len(value["rounding_vectors"]),
        "signed": len(value["signed_vectors"]),
        "batches": len(value["batch_vectors"]),
        "invalid_i64": len(value["invalid_i64"]),
        "invalid_batches": len(value["invalid_batch_hex"]),
    }


def run(write_fixture: bool = False) -> int:
    expected = generate()
    if write_fixture:
        (ROOT / FIXTURE).write_bytes(encoded(expected))
        (ROOT / SIDECAR).write_text(sha(encoded(expected)) + "\n")
        return 0
    actual = load(ROOT / FIXTURE)
    state: dict[str, Any] = {
        "version": 1,
        "issue": 109,
        "status": "running",
        "provenance": provenance(),
        "fixture": FIXTURE,
        "fixture_digest": file_sha(FIXTURE),
        "outcomes": [],
        "failure": None,
        "limitations": [
            "Exact public implementation vectors, not independent cryptographic "
            "or book verification.",
            "Only the pinned bounded fzknum relation; no ML utility or DP claim.",
        ],
    }
    save("golden-run.json", state)
    try:
        # Run cross-language validation before deterministic regeneration checks,
        # so mutations demonstrate native disagreement rather than only a hash.
        counts = cross_check(actual)
        require(encoded(actual) == encoded(expected), "golden-generator-drift")
        require((ROOT / SIDECAR).read_text().strip() == file_sha(FIXTURE), "golden-digest-drift")
        state["outcomes"].append({"case": "positive", "status": "accepted", "counts": counts})
        for name in ["rounding-tie", "negative-division", "byte-order"]:
            try:
                cross_check(mutate(expected, name))
            except ConformanceFailure as error:
                require(
                    error.detail["native_exit_code"] == 0,
                    "mutation-needs-zero-exit-native-disagreement",
                )
                state["outcomes"].append(
                    {
                        "case": name,
                        "status": "rejected-as-required",
                        "counts": {},
                        "counterexample": error.detail,
                    }
                )
            else:
                raise ValueError("cross-language-mutation-survived")
        state["status"] = "completed"
    except Exception as error:
        state["status"] = "failed"
        state["failure"] = (
            error.detail
            if isinstance(error, ConformanceFailure)
            else {"code": "execution-or-determinism-failure"}
        )
        save("golden-run.json", state)
        print("CI-14 failed closed:", json.dumps(state["failure"], sort_keys=True))
        return 1
    save("golden-run.json", state)
    print("CI-14: exact vectors and all three native-disagreement mutations checked.")
    return 0
