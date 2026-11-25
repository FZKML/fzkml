"""Require Session 01's real private transition smoke test; no publication claim."""

from __future__ import annotations

import json
import re
import subprocess

from fzkml_ci.validate import ROOT, require


def main() -> None:
    completed = subprocess.run(
        [str(ROOT / "target/release/fzkml-private"), "smoke", "0"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=300,
        check=True,
    )
    require(len(completed.stdout) <= 16_384, "private-smoke-output-bound")
    record = json.loads(completed.stdout)
    require(
        record["contract_version"] == "fzk-private-1.0.0"
        and record["numeric_contract"] == "fzknum-1.0.0"
        and record["verified"] is True
        and record["output"] == 9
        and record["proof_bytes"] == 128
        and record["envelope_bytes"] == 576
        and record["constraints"] == 196_118
        and record["public_field_count"] == 101
        and record["substitutions_rejected"] == 12
        and record["fuzz_cases"] == 0
        and all(
            record[name] is True
            for name in [
                "fresh_allowed_proof_verified",
                "wrong_expected_rejected",
                "replay_rejected",
            ]
        ),
        "private-genuine-proof-required",
    )
    for name in ["key_id", "parameters_id", "statement_digest"]:
        require(
            isinstance(record[name], str)
            and re.fullmatch(r"[0-9a-f]{64}", record[name]) is not None
            and record[name] != "0" * 64,
            "private-real-identities-required",
        )
    print("Session 01 genuine private transition verified; 12 substitutions rejected.")
    print("Research candidate only; no aggregate privacy, DP or production security claim.")


if __name__ == "__main__":
    main()
