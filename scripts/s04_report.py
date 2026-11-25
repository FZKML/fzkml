"""Publish actual CI-04 evidence, including explicit failed/unavailable attempts."""

from __future__ import annotations

import copy
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from fzkml_ci.publication import authorize
from fzkml_ci.report import render, verify_report, write_report
from fzkml_ci.research import proof_results, write
from fzkml_ci.s04 import journal, proof_receipt
from fzkml_ci.validate import ROOT, bounded_file, load, require


def bundle() -> dict[str, Any]:
    run = os.environ.get("GITHUB_RUN_ID")
    require(
        run is not None and run.isdigit() and int(run) > 0,
        "truthful-hosted-result-identity-required",
    )
    assert run is not None
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    state = load(ROOT / "research/journal.json")
    journal(state)
    require(state["source_sha"] == source, "stale-journal")
    if state["status"] == "completed" and (ROOT / "research/proof-results.json").exists():
        receipt = load(ROOT / "research/proof-check.json")
        proof_receipt(receipt, source)
        result = load(ROOT / "research/proof-results.json")
        proof_results(result)
        require(
            all(
                r["provenance"]["source_commit"] == source
                and r["provenance"]["workflow_run"] == int(run)
                for r in result["results"]
            ),
            "stale-scientific-results",
        )
        return dict(result)
    row = copy.deepcopy(load(ROOT / "examples/results.json")["results"][0])
    row["run_id"] = "synthetic:s04-proof-job"
    row["scenario"].update(
        id="genuine-proof-job",
        statement="public-exact-linear-three-client",
        backend="ark-groth16-0.5.0-bn254",
        security_mode="research",
        relation_version="fzknum-1.0.0",
        numerical_semantics="fixed16-rne",
    )
    row["provenance"].update(
        source_commit=source,
        workflow_run=int(run),
        workflow_path=".github/workflows/reports.yml",
        toolchain="rust-1.85.1-python-3.11.14",
    )
    import hashlib

    row["provenance"]["dependency_digest"] = (
        "sha256:"
        + hashlib.sha256(
            (ROOT / "Cargo.lock").read_bytes() + (ROOT / "uv.lock").read_bytes()
        ).hexdigest()
    )
    row["provenance"]["hardware"].update(
        cpu=platform.machine(),
        os=platform.system(),
        memory_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
        runner_image_revision=os.environ.get("ImageVersion", "unavailable"),
    )
    executed = [r for r in state["repetitions"] if r["seconds"] is not None]
    status = (
        "not-run"
        if not executed
        else "failed"
        if all(r["status"] in {"failed", "timed-out"} for r in executed)
        else "inconclusive"
    )
    row["outcome"] = {
        "status": status,
        "reason": f"Operational outcome {state['status']}; no verified proof result available.",
    }
    row["repetitions"] = [
        {
            "id": f"rep{r['index']}",
            "attempt": 1,
            "status": "failed" if r["status"] in {"failed", "timed-out"} else "inconclusive",
            "timeout": r["status"] == "timed-out",
            "excluded": False,
            "reason": f"Attempt: {r['status']}; wall time includes build and preparation.",
            "quality": "not-measured",
            "measurements": [
                {"phase": "total", "quantity": "time", "unit": "s", "value": r["seconds"]}
            ],
        }
        for r in executed
    ]
    row["metrics"] = []
    row["limitations"] = [
        "Failed/unavailable/incomplete check; no cryptographic or scientific success.",
        "Zero relation/key/artifact identities denote unavailable measurements, not real keys.",
        "Operational skipped/unavailable states map to not-run with their explicit reason.",
        "Lost journals require workflow metadata reconciliation; upload is best effort.",
    ]
    row["schema_version"] = "1.1.0"
    row["provenance"]["execution_kind"] = "github-actions"
    row["publication_review"] = {
        "approved": False,
        "review_id": "synthetic:s04-policy-review-pending",
    }
    for kind in ["model", "dataset"]:
        row["scenario"][kind] = {
            "id": f"synthetic:s04-{kind}",
            "version": "numeric-v1",
            "digest": "sha256:"
            + hashlib.sha256((ROOT / "assets/public/numeric-v1.json").read_bytes()).hexdigest(),
            "license": "Apache-2.0",
            "publication": "permitted",
        }
    for repetition in row["repetitions"]:
        for measurement in repetition["measurements"]:
            if measurement["phase"] == "total":
                measurement["phase"] = "end-to-end"
    return {"schema_version": "1.1.0", "results": [row]}


if __name__ == "__main__":
    try:
        candidate, claims = bundle(), load(ROOT / "claims/registry.json")
        results, receipt = authorize(candidate, claims)
        rendered = render(results, claims)
        import hashlib

        receipt["artifact_digests"] = {
            name: "sha256:" + hashlib.sha256(data.encode()).hexdigest()
            for name, data in rendered.items()
        }
        if sys.argv[1:] == ["--verify"]:
            verify_report(Path("dist"))
            require(
                load(ROOT / "reports/s04-publication-receipt.json") == receipt,
                "publication-receipt-drift",
            )
            for name, expected in render(results, claims).items():
                require(
                    bounded_file(Path("dist") / name) == expected.encode(),
                    "stale-or-unbound-public-report",
                )
        else:
            require(not sys.argv[1:], "report-arguments")
            write_report(results, claims, Path("dist"))
            write(ROOT / "reports/s04-publication-receipt.json", receipt)
    except Exception:
        print("evidence publication rejected: incomplete, invalid or unreviewed public inputs")
        raise SystemExit(1) from None
