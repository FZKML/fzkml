"""Run CI-16 through CI-20 synthetic reference contracts without live dispatch."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from specifications.ci_assurance.disclosure import scan_views
from specifications.ci_assurance.parameters import check_parameters, ticket_map, weights
from specifications.ci_assurance.planner import plan_matrix
from specifications.ci_assurance.rounds import (
    ACTIONS,
    Authority,
    State,
    classification,
    explore,
    model_step,
    replay,
    require,
)

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def read_json(path: Path) -> dict[str, Any]:
    require(path.stat().st_size <= 131072, "json-resource-budget")
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def checked_json(path: Path, schema: str) -> dict[str, Any]:
    result = read_json(path)
    Draft202012Validator(read_json(HERE / schema)).validate(result)
    return result


def check_report(report: dict[str, Any]) -> None:
    Draft202012Validator(read_json(HERE / "report-schema-v1.json")).validate(report)
    require(
        report["outcome"] == "successful"
        and all(row["outcome"] == "successful" for row in report["records"]),
        "non-success-is-not-pass",
    )


def source_metadata() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, timeout=5).strip()

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--untracked-files=normal")),
        "files": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(HERE.iterdir())
            if p.is_file()
        },
    }


def concurrent_conformance() -> int:
    authority = Authority()
    admissions = [ACTIONS[0], ACTIONS[1], ACTIONS[2], ACTIONS[3]] * 3
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(authority.apply, admissions))
    authority.apply(("freeze", "", "", "h0"))
    authority.apply(("reserve", "", "", "h0"))
    final = [ACTIONS[6], ACTIONS[7], ACTIONS[8]] * 4
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(authority.apply, final))
    # Force a final attempt after both shares, regardless of their scheduled order.
    authority.apply(ACTIONS[8])
    model = State()
    for event in authority.history:
        model = model_step(model, event)
    require(
        authority.state == model and model.releases == 1 and len(model.accepted) == 2,
        "concurrent-history-not-linearizable",
    )
    return len(authority.history)


def run(
    fixtures_path: Path, *, unsafe_release: bool = False, max_states: int = 4096
) -> dict[str, Any]:
    fixture = checked_json(fixtures_path, "fixture-schema-v1.json")
    contracts = checked_json(HERE / "contracts-v1.json", "schema-v1.json")
    require(
        [(c["id"], c["issue"]) for c in contracts["contracts"]]
        == [(f"CI-{i + 16}", i + 111) for i in range(5)],
        "contract-coverage",
    )
    require(
        len({row["id"] for row in fixture["traces"]}) == len(fixture["traces"])
        and {row["id"] for row in fixture["traces"]}
        == set(contracts["contracts"][0]["fixture_ids"]),
        "trace-fixture-coverage",
    )
    traces: list[dict[str, Any]] = []
    accepted: tuple[tuple[str, str], ...] | None = None
    for row in fixture["traces"]:
        result = replay(row["events"])
        require(
            classification(result) == row["classification"]
            and result.charged == row["charged"]
            and result.releases == row["releases"],
            "positive-trace-expectation-failed",
        )
        if result.phase == "released":
            require(accepted is None or result.accepted == accepted, "replay-accepted-set-changed")
            accepted = result.accepted
        traces.append(
            {
                "id": row["id"],
                "classification": classification(result),
                "charged": result.charged,
                "releases": result.releases,
                "accepted": [list(item) for item in result.accepted],
            }
        )
    model = explore(max_states, unsafe_release)
    require(model["outcome"] == "successful", "bounded-model-" + model["outcome"])
    linearized_events = concurrent_conformance()
    with tempfile.TemporaryDirectory(prefix="fzkml-public-views-") as directory:
        public = Path(directory)
        for entry in fixture["views"]:
            # Fixture schema admits flat bounded names only; scanner independently checks inventory.
            (public / entry["path"]).write_text(entry["payload"])
        inventory = [{k: v for k, v in e.items() if k != "payload"} for e in fixture["views"]]
        scanned = scan_views(public, inventory, fixture["canary"].encode())
    parameter_result = check_parameters(fixture["parameters"], HERE / "dp-geometric-v1.md")
    tickets = ticket_map(17)
    require(tuple(tickets.count(z) for z in range(17)) == weights(17), "ticket-law-mismatch")
    matrix = read_json(HERE / "matrix-v1.json")
    review = read_json(HERE / "matrix-review-v1.json")
    require(
        review["scope"] == "synthetic-test-only" and review["live_approved_digests"] == [],
        "live-review-not-established",
    )
    plan = plan_matrix(
        matrix,
        frozenset(review["synthetic_digests"]),
        HERE / "dataset-v1.json",
        HERE / "software-v1.json",
    )
    observations = [
        {"traces": traces, "production_protocol_executed": False},
        {
            "states": model["states"],
            "edges": model["edges"],
            "linearized_events": linearized_events,
            "production_consensus_executed": False,
        },
        {**scanned, "semantic_confidentiality_established": False},
        parameter_result,
        plan,
    ]
    report = {
        "schema_version": "1.0.0",
        "kind": "synthetic-engineering-reference",
        "outcome": "successful",
        "source": source_metadata(),
        "fixture_sha256": hashlib.sha256(fixtures_path.read_bytes()).hexdigest(),
        "execution_kind": "reference-process",
        "workflow_run_id": None,
        "workflow_job_id": None,
        "publication": {"approved": False},
        "scientific_claim_ids": [],
        "records": [
            {
                "contract_id": c["id"],
                "issue": c["issue"],
                "fixture_ids": c["fixture_ids"],
                "outcome": "successful",
                "observations": observations[i],
                "limits": c["limits"],
            }
            for i, c in enumerate(contracts["contracts"])
        ],
    }
    check_report(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=HERE / "fixtures-v1.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mutation", choices=["duplicate-release"])
    parser.add_argument("--max-states", type=int, default=4096)
    args = parser.parse_args()
    try:
        report = run(
            args.fixtures,
            unsafe_release=args.mutation == "duplicate-release",
            max_states=args.max_states,
        )
    except Exception as error:
        # Schema exceptions may embed instance bytes. Never echo exception details or raw inputs.
        reason = "inconclusive" if str(error) == "bounded-model-inconclusive" else "failed"
        failure = {
            "schema_version": "1.0.0",
            "kind": "synthetic-engineering-reference",
            "outcome": reason,
            "diagnostic": "ci-assurance-gate-rejected",
            "publication": {"approved": False},
            "scientific_claim_ids": [],
            "records": [],
            "source": source_metadata(),
        }
        Draft202012Validator(read_json(HERE / "report-schema-v1.json")).validate(failure)
        args.output.write_text(json.dumps(failure, indent=2) + "\n")
        print(json.dumps({"outcome": reason, "diagnostic": "ci-assurance-gate-rejected"}))
        return 1
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"outcome": "successful", "contracts": len(report["records"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
