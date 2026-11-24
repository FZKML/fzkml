"""Generate independent v2 public vectors from S01's explicitly supplied contract."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import hashlib
import json
import struct
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from python.fzkml_math.numeric import encode  # noqa: E402
from python.fzkml_math.private_v2 import (
    CONTRACT_SHA256,
    StatementV2,
    arithmetic,
    digest,
    envelope_layout,
    public_test_commitment,
    synthetic,
)  # noqa: E402


def generate(contract_json: str) -> dict[str, object]:
    if hashlib.sha256(contract_json.encode()).hexdigest() != CONTRACT_SHA256:
        raise ValueError("source-contract-drift")
    batch = encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1])
    context = synthetic()
    valid = []
    previous = None
    for round_id in (1, 2):
        if previous is not None:
            context = replace(
                context,
                round=round_id,
                parent=digest(previous.encode()),
                parent_value=previous.output,
            )
            batch = encode(context.parent_value, [16, -8, 24], [16, -16, 8], [1, 2, 1])
        output = arithmetic(context, batch)["output"]
        if type(output) is not int:
            raise AssertionError("numeric-output")
        m = public_test_commitment(
            b"FZKMOD02",
            bytes([10 + round_id]) * 32,
            context,
            struct.pack("<q", context.parent_value),
        )
        d = public_test_commitment(
            b"FZKDAT02",
            bytes([18 + round_id]) * 32,
            context,
            struct.pack("<qqqqqq", 16, 16, -8, -16, 24, 8),
        )
        statement = StatementV2(context, m, d, output)
        valid.append(
            {
                "round": round_id,
                "numeric_hex": batch.hex(),
                "parent_value": context.parent_value,
                "expected": arithmetic(context, batch),
                "context_hex": context.encode().hex(),
                "context_sha256": digest(context.encode()).hex(),
                "statement_hex": statement.encode().hex(),
                "statement_sha256": digest(statement.encode()).hex(),
                "model_commitment": m.hex(),
                "data_commitment": d.hex(),
                "public_test_openings": {
                    "model_blinding_byte": 10 + round_id,
                    "data_blinding_byte": 18 + round_id,
                },
                "envelope_layout_hex": envelope_layout(statement, bytes(128)).hex(),
                "envelope_cryptographic_validity": (
                    "invalid-placeholder-proof-must-be-rejected-by-real-verifier"
                ),
            }
        )
        previous = statement
    raw = synthetic().encode()
    invalid = [
        b"",
        raw[:-1],
        raw + b"\0",
        b"FZKCTX01" + raw[8:],
        raw[:8] + bytes(16) + raw[24:],
        raw[:24] + struct.pack("<Q", 0) + raw[32:],
        raw[:32] + struct.pack("<q", 81) + raw[40:],
        raw[:120] + struct.pack("<I", 0) + raw[124:],
        raw[:228] + struct.pack("<I", 0) + raw[232:],
    ]
    return {
        "fixture_version": "s02-private-transition-v2-1.0.0",
        "contract_version": "fzk-private-2.0.0",
        "contract_sha256": CONTRACT_SHA256,
        "contract_source": (
            "https://github.com/FZKML/fzkml/blob/"
            "2e8a464ffd7eb5f358e811b9285519d46f594bc2/specs/private-transition-v2.json"
        ),
        "contract_source_commit": "2e8a464ffd7eb5f358e811b9285519d46f594bc2",
        "contract_snapshot_json": contract_json,
        "numeric_contract": "fzknum-1.0.0",
        "valid": valid,
        "invalid_context_hex": [b.hex() for b in invalid],
        "negative_binding_cases": [
            {
                "id": "wrong-private-parent",
                "public_parent_value": 8,
                "private_initial_weight": 7,
                "expected": "reject",
            },
            {
                "id": "format-valid-unprovable-parent",
                "public_parent_value": 33,
                "private_initial_weight": 33,
                "expected": "reject-numeric-v1-input-domain",
            },
        ],
        "limitations": [
            "Public deterministic test openings only; "
            "not private RNG, hiding or cryptographic proof evidence.",
            "Envelope layout vectors contain an invalid zero proof "
            "and MUST NOT satisfy a real-proof gate.",
            "Context parent format range[-80,80] is wider than "
            "the unchanged numeric initial-weight range[-32,32].",
            "Same-repository contract snapshot is not a second normative specification "
            "or a silent v1 change.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=Path, nargs="?")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = ROOT / "tests/vectors/synthetic/private-transition-v2.json"
    source = (
        args.contract.read_text()
        if args.contract
        else json.loads(target.read_text())["contract_snapshot_json"]
    )
    document = generate(source)
    text = json.dumps(document, indent=2) + "\n"
    if args.check:
        if target.read_text() != text:
            raise ValueError("private-v2-fixture-drift")
    else:
        target.write_text(text)
    print("S02 independent private-v2 public test vectors verified")
