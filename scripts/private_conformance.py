"""Compare the private circuit against independent public numeric vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.numeric import encode, evaluate  # noqa: E402


def check(binary: Path, random_cases: int = 32) -> dict[str, object]:
    fixture_path = ROOT / "assets/public/numeric-v1.json"
    fixture = json.loads(fixture_path.read_text())
    if (
        fixture["contract_sha256"]
        != hashlib.sha256((ROOT / "specs/numeric-contract-v1.json").read_bytes()).hexdigest()
    ):
        raise ValueError("numeric-contract-digest-mismatch")
    cases = [
        (bytes.fromhex(vector["canonical_hex"]), vector["expected"]["output"])
        for vector in fixture["valid"]
    ]
    rng = random.Random(20261126)
    for _ in range(random_cases):
        raw = encode(
            rng.randint(-32, 32),
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(-32, 32) for _ in range(3)],
            [rng.randint(1, 4) for _ in range(3)],
        )
        cases.append((raw, evaluate(raw)["output"]))
    payload = "".join(f"{raw.hex()} {output}\n" for raw, output in cases).encode()
    result = subprocess.run(
        [str(binary.resolve()), "audit"],
        input=payload,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace")[:1000])
    report = json.loads(result.stdout)
    if report["cases"] != len(cases) or not report["all_satisfied"]:
        raise ValueError("private-circuit-case-count-or-satisfaction")
    for raw, expected in cases:
        if evaluate(raw)["output"] != expected:
            raise ValueError("independent-oracle-drift")
    return {
        **report,
        "random_seed": 20261126,
        "random_cases": random_cases,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "limitation": (
            "Bounded public cases compare this circuit with the Python Fraction oracle; "
            "they do not establish cryptographic soundness or security."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--random-cases", type=int, default=32, choices=range(257))
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.binary, args.random_cases), sort_keys=True))
    except (ValueError, AssertionError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
