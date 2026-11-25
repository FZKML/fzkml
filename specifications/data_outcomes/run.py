"""Local, unapproved data/outcome reference evidence; no real study or payments."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import time
from fractions import Fraction as F
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from specifications.data_outcomes.design import validate_adoption, validate_factorial
from specifications.data_outcomes.pilot import run_pilot
from specifications.data_outcomes.reference import (
    Row,
    check_lifecycle,
    digest,
    removal,
    residual,
    squared_norm,
    valuation_examples,
)

ROOT = Path(__file__).resolve().parents[2]


def encode(value: Any) -> Any:
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(v) for key, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    return value


def removal_examples() -> dict[str, Any]:
    rows = (
        Row("historical-teaching-row1", (F(1), F(0)), F(1)),
        Row("historical-teaching-row2", (F(0), F(1)), F(1)),
    )
    source = removal(rows, {rows[0].identity}, {r.identity for r in rows}, F(1))
    original = (
        Row("a", (F(1), F(0)), F(1)),
        Row("b", (F(0), F(1)), F(2)),
        Row("c", (F(1), F(1)), F(3)),
    )
    case = removal(original, {"c"}, {"a", "b", "c"}, F(1))
    approximate = (case["new"][0] + F(1, 1000), case["new"][1] - F(1, 1000))
    bound = squared_norm(residual(case["matrix"], case["rhs"], approximate))
    error = squared_norm((approximate[0] - case["new"][0], approximate[1] - case["new"][1]))
    if error > bound:
        raise ValueError("residual-parameter-bound")
    parent_model = digest({"weights": encode(case["old"]), "version": "parent0"})
    new_model = digest(
        {
            "weights": encode(case["new"]),
            "dataset": case["dataset_commitment"],
            "version": "retained1",
        }
    )
    trusted = {
        "parent_model": parent_model,
        "expected_retained_model": new_model,
        "known_artifacts": ["synthetic-source", "synthetic-cache", "synthetic-checkpoint"],
        "prior_releases": ["public-synthetic-parent0"],
        "privacy_spent_before": "1/4",
    }
    lifecycle = {
        "claim_scope": "current-model-and-known-inventory-only",
        "parent_model": parent_model,
        "new_model": new_model,
        "known_artifacts": trusted["known_artifacts"],
        "artifact_actions": {
            "synthetic-source": "removed",
            "synthetic-cache": "quarantined-not-erased",
            "synthetic-checkpoint": "removed",
        },
        "prior_releases": trusted["prior_releases"],
        "retained_release_history": trusted["prior_releases"],
        "privacy_spent_after": "1/4",
        "unobserved_copy_status": "unknown",
        "certificate_kind": "transparent-reference-not-cryptographic-proof",
    }
    check_lifecycle(lifecycle, trusted)
    return cast(
        dict[str, Any],
        encode(
            {
                "historical_teaching_inputs_reference": source,
                "original_perturbation_reference": case,
                "approximate_error_squared": error,
                "lambda1_residual_bound_squared": bound,
                "certificate_kind": "transparent-reference-not-cryptographic-proof",
                "unobserved_copy_status": "unknown",
                "privacy_refund_authorized": False,
                "lineage_reference": lifecycle,
            }
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = ROOT / "specifications/data_outcomes"
    factorial = json.loads((folder / "factorial-v1.json").read_text())
    adoption = json.loads((folder / "adoption-v1.json").read_text())
    validate_factorial(factorial)
    validate_adoption(adoption)
    started = time.perf_counter()
    deletion, valuation, pilot = removal_examples(), valuation_examples(), run_pilot()
    elapsed = time.perf_counter() - started
    data = {
        "schema_version": "data-outcomes-reference-1.0.0",
        "kind": "bounded-reference-and-synthetic-pilot",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
        ),
        "source_version": json.loads((folder / "contracts-v1.json").read_text())["source_version"],
        "contract_sha256": hashlib.sha256((folder / "contracts-v1.json").read_bytes()).hexdigest(),
        "program_sha256": hashlib.sha256(
            b"".join(
                (folder / p).read_bytes()
                for p in ("reference.py", "design.py", "pilot.py", "run.py")
            )
        ).hexdigest(),
        "claim_ids": [],
        "issues": [101, 102, 103, 104, 105],
        "execution": {
            "kind": "local",
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "jsonschema": importlib.metadata.version("jsonschema"),
            "cpu_count": os.cpu_count(),
            "accelerator": "none",
            "dependency_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
            "repetitions": 1,
            "reference_seconds": elapsed,
            "reproduction_command": (
                "PYTHONPATH=.:src python -m specifications.data_outcomes.run --output OUTPUT.json"
            ),
        },
        "observations": {"deletion": deletion, "valuation": valuation, "synthetic_pilot": pilot},
        "factorial_training_status": "not-run",
        "sector_replication_status": "not-replicated",
        "adoption_study_status": "not-run",
        "payments_executed": 0,
        "genuine_proofs_verified": 0,
        "publication_review": {"approved": False},
        "limitations": [
            "Historical MS20261124 inputs are pinned; current-edition migration remains pending.",
            (
                "Toy arithmetic/pilot does not establish cryptographic removal, "
                "economic fairness or learning gains."
            ),
            "No real deletion, erasure, refund, payment, contact or field study.",
            "Pilot uses original synthetic data; no source-paper or FZKML treatment comparison.",
            "One deterministic pilot supplies no population uncertainty or adoption effect.",
        ],
    }
    schema = json.loads((folder / "report-schema-v1.json").read_text())
    Draft202012Validator(schema).validate(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print("References completed; factorial, sector replication and adoption remain unexecuted.")


if __name__ == "__main__":
    main()
