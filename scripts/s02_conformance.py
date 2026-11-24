"""Compare an external Rust CLI against canonical independent Python vectors."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from python.fzkml_math.numeric import CONTRACT_VERSION, evaluate  # noqa: E402


def check(binary: Path) -> dict[str, Any]:
    data = json.loads((ROOT / "tests/vectors/synthetic/s02-boundaries-v1.json").read_text())
    if data["contract_version"] != CONTRACT_VERSION:
        raise ValueError("fixture-contract-drift")

    def call(args: list[str], hexadecimal: str) -> tuple[int, str]:
        result = subprocess.run(
            [str(binary.resolve()), *args],
            input=(hexadecimal + "\n").encode(),
            capture_output=True,
            timeout=15,
            check=False,
        )
        if len(result.stdout) > 4096:
            raise ValueError("bounded-cli-output")
        return result.returncode, result.stdout.decode().strip()

    for item in data["valid"]:
        wire = item["canonical_hex"]
        expected = evaluate(bytes.fromhex(wire))
        if expected != item["expected"]:
            raise ValueError("oracle-fixture-drift")
        output = expected["output"]
        if type(output) is not int:
            raise ValueError("oracle-output-shape")
        code, found = call(["evaluate"], wire)
        if code or found != str(expected["output"]):
            raise ValueError("external-evaluate-disagreement")
        code, found = call(["check", str(expected["output"])], wire)
        if code or found != "true":
            raise ValueError("external-valid-witness-rejected")
        code, found = call(["check", str(output + 1)], wire)
        if code or found != "false":
            raise ValueError("external-wrong-output-accepted")
    for wire in data["invalid_hex"]:
        code, _ = call(["evaluate"], wire)
        if not code:
            raise ValueError("external-invalid-wire-accepted")
    return {
        "contract_version": CONTRACT_VERSION,
        "fixture_version": data["fixture_version"],
        "accepted": len(data["valid"]),
        "rejected": len(data["invalid_hex"]),
        "wrong_output_rejections": len(data["valid"]),
        "scope": "external CLI comparison; independent oracle does not import native bindings",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    print(json.dumps(check(parser.parse_args().binary), sort_keys=True))
