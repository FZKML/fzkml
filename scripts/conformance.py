"""Exercise an independently built Rust CLI against exact public golden vectors."""

import argparse
import hashlib
import json
import random
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.numeric import (  # noqa: E402
    CONTRACT_VERSION,
    FIXTURE_VERSION,
    decode,
    encode,
    evaluate,
)


def invoke(binary: Path, args: list[str], data: bytes = b"") -> tuple[bool, str]:
    result = subprocess.run(
        [str(binary.resolve()), *args], input=data, capture_output=True, timeout=10, check=False
    )
    return result.returncode == 0, result.stdout.decode().strip()


def shrink(binary: Path, data: bytes) -> bytes:
    w, x, y, counts = decode(data)
    values = [w, *x, *y, *counts]
    for i in range(len(values)):
        for small in [0, int(values[i] / 2)] if i < 7 else [1]:
            candidate = values.copy()
            candidate[i] = small
            encoded = encode(candidate[0], candidate[1:4], candidate[4:7], candidate[7:10])
            ok, found = invoke(binary, ["evaluate"], encoded.hex().encode() + b"\n")
            if not ok or found != str(evaluate(encoded)["output"]):
                values = candidate
    return encode(values[0], values[1:4], values[4:7], values[7:10])


def check(binary: Path, extra_random: int = 0) -> dict[str, object]:
    fixture = json.loads((ROOT / "assets/public/numeric-v1.json").read_text())
    assert fixture["contract_version"] == CONTRACT_VERSION
    assert fixture["fixture_version"] == FIXTURE_VERSION
    assert (
        fixture["contract_sha256"]
        == hashlib.sha256((ROOT / "specs/numeric-contract-v1.json").read_bytes()).hexdigest()
    )
    # Smallest-magnitude ties first; this records a minimal rounding counterexample.
    for magnitude in range(33):
        for n in [0] if magnitude == 0 else [magnitude, -magnitude]:
            for d in range(1, 17):
                ok, found = invoke(binary, ["round", str(n), str(d)])
                if not ok or found != str(round(Fraction(n, d))):
                    raise ValueError(
                        json.dumps(
                            {
                                "operation": "round",
                                "n": n,
                                "d": d,
                                "expected": round(Fraction(n, d)),
                                "found": found,
                            }
                        )
                    )
    vectors = list(fixture["valid"])
    rng = random.Random(20261125)
    for _ in range(extra_random):
        data = encode(
            rng.randint(-32, 32),
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(1, 4) for _ in range(3)],
        )
        vectors.append({"canonical_hex": data.hex(), "expected": evaluate(data)})
    for vector in vectors:
        data = bytes.fromhex(vector["canonical_hex"])
        expected = evaluate(data)
        assert expected == vector["expected"], "oracle/fixture drift"
        ok, found = invoke(binary, ["evaluate"], data.hex().encode() + b"\n")
        if not ok or found != str(expected["output"]):
            minimal = shrink(binary, data)
            raise ValueError(
                json.dumps(
                    {
                        "operation": "evaluate",
                        "shrunk_canonical_hex": minimal.hex(),
                        "expected": evaluate(minimal)["output"],
                        "found": found,
                    }
                )
            )
        ok, satisfied = invoke(
            binary, ["check", str(expected["output"])], data.hex().encode() + b"\n"
        )
        if not ok or satisfied != "true":
            raise ValueError(
                json.dumps({"operation": "constraint-witness", "canonical_hex": data.hex()})
            )
    for value in fixture["invalid_hex"]:
        try:
            evaluate(bytes.fromhex(value))
        except ValueError:
            pass
        else:
            raise AssertionError("invalid fixture accepted by oracle")
        ok, _ = invoke(binary, ["evaluate"], value.encode() + b"\n")
        if ok:
            raise ValueError(
                json.dumps({"operation": "invalid-input-accepted", "canonical_hex": value})
            )
    return {
        "contract_version": CONTRACT_VERSION,
        "fixture_version": FIXTURE_VERSION,
        "accepted": len(vectors),
        "rejected": len(fixture["invalid_hex"]),
        "rounding_cases": 65 * 16,
        "build": str(binary),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument(
        "--extra-random", type=int, default=0, choices=range(2049), metavar="0..2048"
    )
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.binary, args.extra_random), sort_keys=True))
    except (ValueError, AssertionError) as error:
        (ROOT / "reports").mkdir(exist_ok=True)
        (ROOT / "reports/conformance-failure.json").write_text(str(error) + "\n")
        print(error, file=sys.stderr)
        sys.exit(1)
