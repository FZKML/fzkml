"""Public reference runner; no witnesses, randomness or exception payloads emitted."""

from __future__ import annotations

import argparse
import copy
import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from fzkml_ci.report import verify_report, write_report
from fzkml_ci.validate import ROOT, load, validate_claims

from .experiments import run_all
from .visibility import public_bytes, validate_observers


def shared_results(observations: dict[str, Any], run_id: int) -> dict[str, Any]:
    if run_id < 1:
        raise ValueError("hosted-workflow-identity-required")
    if public_bytes(observations) != public_bytes(
        load(ROOT / "experiments" / "protocol" / "observations.json")
    ):
        raise ValueError("reference-observation-drift")
    template = load(ROOT / "examples" / "results.json")["results"][0]
    claims = {
        row["responsible_issue"]: row
        for row in load(ROOT / "claims" / "protocol-privacy.json")["claims"]
    }
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dependency = "sha256:" + hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
    program = (
        "sha256:"
        + hashlib.sha256(
            b"".join(p.read_bytes() for p in sorted((ROOT / "src" / "fzkml_protocol").glob("*.py")))
        ).hexdigest()
    )
    results = []
    for name, issue in [
        ("histories", 51),
        ("visibility", 52),
        ("harmful_updates", 53),
        ("sensitivity", 54),
        ("mechanism", 55),
    ]:
        claim = claims[issue]
        row = copy.deepcopy(template)
        row.update(run_id=f"synthetic:protocol-{name}", claim_ids=[claim["id"]])
        row["scenario"].update(
            id=f"protocol-{name}",
            statement=claim["id"],
            relation_version="protocol-reference-v1",
            numerical_semantics="m0-half-up-v1",
            backend="exact-python-reference",
            security_mode="synthetic-test",
            program_digest=program,
            circuit_digest="sha256:" + "0" * 64,
        )
        embedded = (
            "sha256:"
            + hashlib.sha256(
                (ROOT / "src" / "fzkml_protocol" / "experiments.py").read_bytes()
            ).hexdigest()
        )
        for kind in ["model", "dataset"]:
            row["scenario"][kind] = {
                "id": f"synthetic:protocol-embedded-{kind}",
                "version": "1",
                "digest": embedded,
                "license": "Apache-2.0",
                "publication": "permitted",
            }
        row["scenario"]["parameters_digest"] = (
            "sha256:"
            + hashlib.sha256(
                (ROOT / "specs" / "protocol" / "DP-MECHANISM.md").read_bytes()
            ).hexdigest()
        )
        row["provenance"].update(
            source_commit=source,
            workflow_run=run_id,
            dependency_digest=dependency,
            toolchain="cpython-3.11.14",
        )
        if "/reports.yml@" in os.environ.get("GITHUB_WORKFLOW_REF", ""):
            row["provenance"]["workflow_path"] = ".github/workflows/reports.yml"
        row["provenance"]["hardware"].update(
            cpu="github-hosted-cpu",
            memory_bytes=0,
            os=platform.system().lower(),
            runner_image_revision=os.environ.get("ImageVersion", "unavailable"),
        )
        row["outcome"] = {
            "status": "successful",
            "reason": "Reference case executed; no proof/DP system claim.",
        }
        row["repetitions"] = [
            {
                "id": "reference-1",
                "attempt": 1,
                "status": "successful",
                "timeout": False,
                "excluded": False,
                "reason": "Exact reference checks against retained observations.",
                "measurements": [],
                "quality": "not-measured",
            }
        ]
        row["limitations"] = [
            "Synthetic implementation-conformance only; no real proof or performance measurement.",
            "Memory metadata unavailable; schema placeholder 0 is not a memory measurement.",
            "No external review, DP deployment, authenticity, consensus or prover security.",
        ]
        row["publication_review"] = {
            "approved": True,
            "review_id": "synthetic:original-fixture-policy",
        }
        results.append(row)
    return {"schema_version": "1.0.0", "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("protocol-evidence"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        inventory = load(ROOT / "experiments" / "protocol" / "observers.json")
        validate_observers(inventory)
        validate_claims(load(ROOT / "claims" / "protocol-privacy.json"))
        observations = run_all()
        encoded = public_bytes(observations)
        if args.check:
            expected = public_bytes(load(ROOT / "experiments" / "protocol" / "observations.json"))
            if encoded != expected:
                raise ValueError("reference-observation-drift")
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "observations.json").write_bytes(encoded)
        if os.environ.get("GITHUB_RUN_ID"):
            bundle = shared_results(observations, int(os.environ["GITHUB_RUN_ID"]))
            write_report(
                bundle,
                load(ROOT / "claims" / "protocol-privacy.json"),
                args.output / "public-report",
            )
            verify_report(args.output / "public-report")
        print("Histories: disconnected edges reject; two valid forks possible; withholding stalls.")
        print("Opposing update norms: 256,256; clean losses: 0,4; incorrect training rejected.")
        print(
            "Fixed-slot L1 sensitivity: add/remove 24; replace 48. Geometric epsilon upper: 16/85."
        )
        print("Canary absent; exact PMF agrees. Distribution tests are not a DP proof.")
        print("Real proof, network/outsourced privacy, consensus and deployment DP: not-run.")
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        print(
            "protocol reference failed: invalid input, output or unavailable dependency",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
