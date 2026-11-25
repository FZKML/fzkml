"""Bounded experiment driver with incremental truthful local/hosted receipts."""

from __future__ import annotations

import copy
import hashlib
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from fzkml_ci.research import write
from fzkml_ci.validate import ROOT, load, public_tree, require, validate_bundle, validate_claims

from . import adapters as ad
from . import capacity as cp
from . import ridge as rd
from .algebra import canonical, digest, identity, multiply, norm2, rank
from .algebra import matrix as m

MANIFEST = ROOT / "reports/models/manifest.json"
CONTRACT = "specs/models/model-capacity-v1.json"
FIXTURE = "assets/public/model-capacity-v1.json"
NATIVE = "crates/fzkml-models/src/main.rs"
IDS = {
    "capacity": "FZK-S04M5-C68-CAPACITY-001",
    "ridge": "FZK-S04M5-C76-RIDGE-001",
    "adapter": "FZK-S04M5-C72-ADAPTER-001",
    "eligibility": "FZK-S04M5-C50-ELIGIBILITY-001",
}


def file_hash(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def validate_native(value: Any) -> None:
    definition = load(ROOT / "specs/models/run-schema-v1.json")["$defs"]["native"]
    require(Draft202012Validator(definition).is_valid(value), "models-native-schema")
    public_tree(value)
    for name, path in [
        ("contract_digest", CONTRACT),
        ("program_digest", NATIVE),
        ("dependency_digest", "Cargo.lock"),
    ]:
        require(value[name] == file_hash(path), "models-stale-binary")
    expected = [
        ("ridge-statistics-v1", [1, 0, 2, 2, 6, 1, 1, 2, 0, 0], 15),
        ("fixed-factor-v1", [2, 2, 2, 0, 2, 0, 9, 2], 13),
    ]
    # Expected values are independently computed by the rational reference below.
    for record, (name, outputs, negatives) in zip(value["proofs"], expected, strict=True):
        require(
            record["relation"] == name
            and record["outputs"] == outputs
            and record["negatives_rejected"] == negatives,
            "models-native-conformance",
        )
        for key in ["key_digest", "parameters_digest", "context_digest", "data_commitment"]:
            require(record[key] != "0" * 64, "models-real-identity")
        require(record["context_digest"] == value["contract_digest"], "models-context-binding")
    subprocess.run(
        [str(ROOT / "target/release/fzkml-models"), "--verify"],
        input=canonical(value),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=30,
    )


def reference_checks(rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = [] if rows is None else rows

    def record(name: str, values: dict[str, Any]) -> None:
        rows.append(
            {"name": name, "status": "successful", "values": {k: str(v) for k, v in values.items()}}
        )

    fixture = load(ROOT / FIXTURE)
    capacity = next(r for r in fixture["source_numeric_vectors"] if r["id"] == "capacity-window")
    work = cp.Workload(
        capacity["enrolled"],
        capacity["selected"],
        capacity["coordinates"],
        capacity["coordinate_bits"],
        capacity["buckets"],
        capacity["assumed_proof_envelope_bytes"],
        Q(capacity["assumed_verifier_seconds"]),
        capacity["hypothetical_workers"],
        Q(capacity["window_seconds"]),
        capacity["ingress_bits_per_second"],
        32,
    )
    metrics: dict[str, Any] = dict(work.metrics())
    require(
        metrics["client_upload_bytes"] == capacity["expected_client_payload_bytes"]
        and metrics["proof_traffic_bytes"] == capacity["expected_proof_traffic_bytes"]
        and metrics["ideal_ingress_seconds"] == Q(capacity["expected_ideal_ingress_seconds"]),
        "source-capacity-numbers",
    )
    # Each sweep changes only one declared scale axis. These are analytic
    # budgets, never measured large populations or proof-trace extrapolations.
    metrics.update(
        {
            "record_axis": str(
                [(n, replace(work, records_per_client=n).metrics()["records"]) for n in [1, 2, 4]]
            ),
            "participant_axis": str(
                [
                    (n, replace(work, selected=n).metrics()["client_upload_bytes"])
                    for n in [5000, 10000, 20000]
                ]
            ),
            "coordinate_axis": str(
                [
                    (n, replace(work, coordinates=n).metrics()["client_upload_bytes"])
                    for n in [16384, 32768, 65536]
                ]
            ),
            "concurrency_axis": str(
                [
                    (n, replace(work, workers=n).metrics()["ideal_verification_seconds"])
                    for n in [16, 32, 64]
                ]
            ),
            "arrival_axis": str(
                [
                    (n, replace(work, window_seconds=Q(n)).metrics()["utilization"])
                    for n in [15, 30, 60]
                ]
            ),
            "trace_axis": "Metadata only; no unmeasured proof cost extrapolation.",
        }
    )
    record("capacity-arithmetic-hypothetical", metrics)
    for row in fixture["source_numeric_vectors"]:
        if row["id"].startswith("ridge-statistic"):
            count = rd.statistic_scalars(row["d"], row["c"])
            require(
                count * 4 == row["expected_bytes"]
                and rd.crossover(row["d"], row["c"]) == Q(row["crossover_rounds"]),
                "source-statistic-numbers",
            )
            record(
                row["id"],
                {
                    "scalars": count,
                    "bytes": count * 4,
                    "crossover": rd.crossover(row["d"], row["c"]),
                },
            )
    stats = rd.statistics(m([[1, 0], [0, 1]]), m([[2], [3]]), (Q(1), Q(2)), ("r1", "r2"))
    model = rd.fit(stats, Q(1))
    require(
        model == m([[1], [2]]) and rd.objective(stats, model, Q(1)) == 4, "independent-ridge-oracle"
    )
    cert = rd.certificate(stats, model, Q(1))
    bounds = rd.verify(stats, model, cert, Q(0), stats.id, Q(1))
    record(
        "ridge-numeric-certificate",
        {
            "statistics_digest": stats.id,
            "model_digest": digest(model),
            "residual_squared": cert.residual_squared,
            **bounds,
        },
    )
    policy = ad.FixedFactor(
        m([[1, 0]]), "synthetic-selection-basis-v1", "zero-B-v1", Q(3), Q(3), Q(1)
    )
    bs = (m([[1], [0]]), m([[1], [2]]))
    mean, dense = ad.fixed_aggregate(policy, bs, (Q(1, 2), Q(1, 2)), (policy.id, policy.id))
    require(mean == m([[1], [1]]) and dense == m([[1, 0], [1, 0]]), "independent-adapter-oracle")
    require(ad.gram_squared(bs[1], policy.a) == norm2(multiply(bs[1], policy.a)), "gram-identity")
    _, truncation_error = ad.rank_one_approximation(identity(2))
    record(
        "adapter-algebra",
        {
            "policy_digest": policy.id,
            "dense_digest": digest(dense),
            "exact_sum_rank": rank(identity(2)),
            "rank1_approximation_squared_error": truncation_error,
            "dense_replacement_sensitivity_squared": ad.delivery_sensitivity_squared(
                policy, Q(1, 2)
            ),
        },
    )
    quality = ad.evaluate_frozen_layer(
        identity(2), m([[1], [0]]), policy.a, identity(2), m([[2, 0], [0, 2]])
    )
    require(quality["mean_squared_vector_error"] == Q(1, 2), "restricted-subspace-quality")
    record("frozen-backbone-quality", quality)
    messages = (
        ad.ComponentMessage("A", (Q(2), None), "full-state", "zero", None),
        ad.ComponentMessage("B", (Q(4), Q(8)), "full-state", "zero", None),
    )
    eligible = ad.heterogeneous(
        messages,
        ((True, False), (True, True)),
        (Q(1), Q(1)),
        (Q(0), Q(0)),
        "zero",
        (None, None),
        "record",
    )
    require(eligible == (Q(3), Q(8)), "source-eligibility-numbers")
    record(
        "eligibility-and-hidden-state",
        {
            "eligible": eligible,
            "padded": (3, 4),
            "selected_clients": 2,
            "accepted_clients": 2,
            "exclusion_rate": Q(0),
            "component_eligible_counts": (2, 1),
            "population_fairness": "not-measured",
            **ad.hidden_state_counterexample(4, Q(1)),
        },
    )
    jobs = tuple(cp.Job(str(i), Q(0), Q(1), Q(1)) for i in range(4))
    queue = cp.simulate(jobs + (cp.Job("dropout", Q(0), Q(1), Q(1), True),), (Q(1), Q(1)))
    stragglers = cp.simulate(
        (
            cp.Job("slow", Q(0), Q(8), Q(4)),
            cp.Job("fast", Q(0), Q(1), Q(4)),
            cp.Job("later", Q(1), Q(1), Q(4)),
        ),
        (Q(1), Q(1, 2)),
    )
    record(
        "burst-deadline-dropout-simulation",
        {
            "simulated_clients": len(queue),
            "physical_client_processes": 0,
            "physical_driver_processes": 1,
            "simulated_verifiers": 2,
            "exclusion_rate": Q(sum(r["status"] != "accepted" for r in queue), len(queue)),
            "heterogeneous_speeds": (Q(1), Q(1, 2)),
            "straggler_latencies": tuple(r["latency"] for r in stragglers),
            "straggler_failures": sum(r["status"] != "accepted" for r in stragglers),
            "accepted": sum(r["status"] == "accepted" for r in queue),
            "deadline_failures": sum(r["status"] == "deadline" for r in queue),
            "dropouts": sum(r["status"] == "dropout" for r in queue),
            "all_simulated_latencies": tuple(r["latency"] for r in queue),
            "population_quality_or_fairness": "not-measured",
        },
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic.sqlite"
        ledger = cp.ReleaseLedger(path, "public-synthetic", ("a", "b"), "fixed-roster-v1")
        try:
            ledger.submit("a", 2)
            try:
                ledger.finalize()
            except ValueError:
                pass
            else:
                raise ValueError("missing-payload-falsely-finalized")
            ledger.submit("b", 3)
            try:
                ledger.finalize(interrupt_before_commit=True)
            except RuntimeError:
                pass
            else:
                raise ValueError("crash-not-observed")
            receipt = ledger.finalize()
        finally:
            ledger.close()
        ledger = cp.ReleaseLedger(path, "public-synthetic", ("a", "b"), "fixed-roster-v1")
        try:
            ledger.submit("a", 2)
            require(ledger.finalize() == receipt, "restart-release-changed")
            require(
                ledger.db.execute("SELECT COUNT(*) FROM output").fetchone() == (1,),
                "duplicate-release",
            )
        finally:
            ledger.close()
    record(
        "local-public-recovery",
        {
            "atomic_output_records": 1,
            "released_sum": 5,
            "scope": "one-local-SQLite-authority-no-external-delivery",
        },
    )
    return rows


def provenance() -> dict[str, Any]:
    run = os.environ.get("GITHUB_RUN_ID")
    workflow = os.environ.get("GITHUB_WORKFLOW_REF", "")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    )
    require(not run or (run.isdigit() and int(run) > 0 and not dirty), "models-hosted-provenance")
    require(
        not run
        or (
            source == os.environ.get("GITHUB_SHA")
            and os.environ.get("GITHUB_REPOSITORY") == "FZKML/fzkml"
        ),
        "models-hosted-source-identity",
    )
    actual_path = next(
        (
            p
            for p in ["cpu.yml", "language.yml", "research.yml"]
            if f".github/workflows/{p}@" in workflow
        ),
        None,
    )
    require(not run or actual_path is not None, "models-unknown-workflow")
    return {
        "source_commit": source,
        "source_dirty": dirty,
        "execution_kind": "github-actions" if run else "local",
        "workflow_run": int(run) if run else None,
        "workflow_path": f".github/workflows/{actual_path}" if run else None,
        "python": platform.python_version(),
        "rust": subprocess.check_output(["rustc", "--version"], text=True).split()[1],
        "uv": subprocess.check_output(["uv", "--version"], text=True).split()[1],
        "hardware": {
            "architecture": platform.machine(),
            "os": platform.system(),
            "physical_driver_processes": 1,
            "accelerator": "none",
            "runner_image": os.environ.get("ImageVersion", "unavailable"),
        },
        "fixture_digest": file_hash(FIXTURE),
        "contract_digest": file_hash(CONTRACT),
        "program_digest": file_hash(NATIVE),
        "dependency_digest": hashlib.sha256(
            (ROOT / "Cargo.lock").read_bytes() + (ROOT / "uv.lock").read_bytes()
        ).hexdigest(),
    }


def validate_manifest(value: Any) -> None:
    public_tree(value)
    definition = load(ROOT / "specs/models/run-schema-v1.json")
    require(Draft202012Validator(definition).is_valid(value), "models-run-schema")
    p = value["provenance"]
    local = p["execution_kind"] == "local"
    require(
        (p["workflow_run"] is None and p["workflow_path"] is None)
        if local
        else (
            type(p["workflow_run"]) is int
            and p["workflow_run"] > 0
            and p["workflow_path"] is not None
            and not p["source_dirty"]
        ),
        "models-execution-identity",
    )
    require(len(value["repetitions"]) == value["requested_repetitions"], "models-repetition-count")
    require(set(value["claim_ids"]) == set(IDS.values()), "models-claim-scope")
    expected_checks = [
        "capacity-arithmetic-hypothetical",
        "ridge-statistic-payload-768",
        "ridge-statistic-payload-4096",
        "ridge-numeric-certificate",
        "adapter-algebra",
        "frozen-backbone-quality",
        "eligibility-and-hidden-state",
        "burst-deadline-dropout-simulation",
        "local-public-recovery",
    ]
    for index, rep in enumerate(value["repetitions"]):
        require(rep["index"] == index, "models-repetition-order")
        if rep["status"] == "successful":
            require(
                rep["reference_seconds"] is not None
                and [r["name"] for r in rep["checks"]] == expected_checks,
                "models-executed-reference",
            )
            if value["mode"] == "genuine-and-reference":
                require(
                    rep["proofs"] is not None and rep["native_seconds"] is not None,
                    "models-genuine-proof-unavailable",
                )
                validate_native(rep["proofs"])
            else:
                require(
                    rep["proofs"] is None and rep["native_seconds"] is None,
                    "references-must-not-claim-proof",
                )
    if value["status"] in {"completed", "references-only"}:
        require(
            all(r["status"] == "successful" for r in value["repetitions"]),
            "models-incomplete-success",
        )
        require(
            (value["status"] == "completed") == (value["mode"] == "genuine-and-reference"),
            "models-status-mode",
        )


def scientific_results(state: dict[str, Any]) -> dict[str, Any]:
    p = state["provenance"]
    require(
        not p["source_dirty"] and state["status"] == "completed", "models-clean-results-required"
    )
    require(
        p["workflow_path"] in {None, ".github/workflows/cpu.yml", ".github/workflows/language.yml"},
        "models-result-workflow-unsupported",
    )
    claims = load(ROOT / "claims/models-v1.json")
    validate_claims(claims)
    base = load(ROOT / "examples/results.json")["results"][0]
    rows = []
    for index, name in enumerate(["ridge", "adapter"]):
        first = state["repetitions"][0]["proofs"]["proofs"][index]
        row = copy.deepcopy(base)
        row.update(
            schema_version="1.1.0", run_id=f"synthetic:s04-model-{name}", claim_ids=[IDS[name]]
        )
        row["scenario"].update(
            id=f"model-{name}-genuine",
            statement=first["relation"],
            relation_version="model-capacity-1.0.0",
            numerical_semantics="bounded-integer-exact-v1",
            backend=first["backend"],
            security_mode="research",
            program_digest="sha256:" + p["program_digest"],
            circuit_digest="sha256:" + p["contract_digest"],
            parameters_digest="sha256:" + first["parameters_digest"],
            key_digest="sha256:" + first["key_digest"],
        )
        for kind in ["model", "dataset"]:
            row["scenario"][kind] = {
                "id": f"synthetic:s04-models-{kind}",
                "version": "1.0.0",
                "digest": "sha256:" + p["fixture_digest"],
                "license": "Apache-2.0",
                "publication": "permitted",
            }
        row["provenance"].update(
            source_commit=p["source_commit"],
            workflow_run=p["workflow_run"],
            workflow_path=p["workflow_path"],
            execution_kind=p["execution_kind"],
            toolchain="rust-1.85.1-python-3.11.14",
            dependency_digest="sha256:" + p["dependency_digest"],
        )
        row["provenance"]["hardware"].update(
            cpu=platform.machine(),
            os=platform.system(),
            memory_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
            runner_image_revision=os.environ.get("ImageVersion", "unavailable"),
        )
        # Each repetition has fresh parameters/keys. A result has one setup/key
        # identity, so do not fold independent setups under the first key.
        row["limitations"] = first["limitations"] + [
            "Only repetition zero is in this row; all fresh-key trials remain in manifest.json.",
            "Prove includes synthesis; native wall includes negative setup and verification.",
        ]
        row["randomness"]["protocol_randomness"] = "private-not-recorded"
        row["outcome"] = {
            "status": "successful",
            "reason": "Actual proof and every mandatory negative executed.",
        }
        row["repetitions"] = [
            {
                "id": "rep0",
                "attempt": 1,
                "status": "successful",
                "timeout": False,
                "excluded": False,
                "reason": "One fresh native setup; no mock or skip path.",
                "quality": "not-measured",
                "measurements": [
                    {"phase": phase, "quantity": "time", "unit": "s", "value": first[key]}
                    for phase, key in [
                        ("setup", "setup_seconds"),
                        ("prove", "prove_seconds"),
                        ("verify", "verify_seconds"),
                    ]
                ]
                + [
                    {
                        "phase": "communicate",
                        "quantity": "communication",
                        "unit": "byte",
                        "value": 128,
                    }
                ],
            }
        ]
        row["metrics"] = []
        row["publication_review"] = {
            "approved": False,
            "review_id": "synthetic:models-policy-review-pending",
        }
        rows.append(row)
    result = {"schema_version": "1.1.0", "results": rows}
    validate_bundle(result, claims)
    return result


def run(repetitions: int = 1, references_only: bool = False) -> int:
    require(type(repetitions) is int and 1 <= repetitions <= 3, "models-resource-budget")
    state: dict[str, Any] = {
        "version": 1,
        "issue_ids": [84, 86, 87, 88],
        "claim_ids": list(IDS.values()),
        "mode": "references-only" if references_only else "genuine-and-reference",
        "status": "running",
        "requested_repetitions": repetitions,
        "provenance": provenance(),
        "reproduction": "./scripts/models --repetitions "
        + str(repetitions)
        + (" --references-only" if references_only else ""),
        "publication_review": {
            "approved": False,
            "reason": "New producer has no approved publication policy.",
        },
        "dependencies": [
            {"name": "protected-vector-aggregation", "status": "not-run"},
            {"name": "differential-privacy-mechanism", "status": "not-run"},
            {"name": "foundation-model-feature-proof", "status": "not-run"},
        ],
        "limitations": [
            "Only public synthetic data; no production or independent review.",
            "Queue time/client counts are simulated; one real driver process.",
            "Peak child RSS is a process-wide cumulative maximum, not joint role memory.",
            "Private proof witnesses are not saved; clean public statistics are disclosed.",
            "No authoritative manuscript claim status is changed.",
        ],
        "repetitions": [
            {
                "index": i,
                "status": "pending",
                "reference_seconds": None,
                "native_seconds": None,
                "native_cpu_seconds": None,
                "peak_child_rss_bytes": None,
                "checks": [],
                "proofs": None,
            }
            for i in range(repetitions)
        ],
    }
    (MANIFEST.parent / "results.json").unlink(missing_ok=True)
    write(MANIFEST, state)
    for rep in state["repetitions"]:
        rep["status"] = "running"
        write(MANIFEST, state)
        try:
            start = time.perf_counter()
            try:
                reference_checks(rep["checks"])
            finally:
                rep["reference_seconds"] = time.perf_counter() - start
            if not references_only:
                before = resource.getrusage(resource.RUSAGE_CHILDREN)
                start = time.perf_counter()
                try:
                    completed = subprocess.run(
                        [str(ROOT / "target/release/fzkml-models")],
                        cwd=ROOT,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        check=True,
                        timeout=240,
                    )
                finally:
                    rep["native_seconds"] = time.perf_counter() - start
                require(len(completed.stdout) <= 64_000, "models-native-output-bound")
                import json

                native = json.loads(completed.stdout)
                validate_native(native)
                after = resource.getrusage(resource.RUSAGE_CHILDREN)
                rep["native_cpu_seconds"] = (
                    after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
                )
                rep["peak_child_rss_bytes"] = int(
                    after.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
                )
                rep["proofs"] = native
            rep["status"] = "successful"
        except Exception:
            rep["status"], state["status"] = "failed", "failed"
            write(MANIFEST, state)
            print("Model reference/proof execution failed; incomplete repetitions retained.")
            return 1
        write(MANIFEST, state)
    state["status"] = "references-only" if references_only else "completed"
    validate_manifest(state)
    write(MANIFEST, state)
    if not references_only and not state["provenance"]["source_dirty"]:
        write(MANIFEST.parent / "results.json", scientific_results(state))
    print(f"Model checks: {state['status']}; {repetitions} bounded repetition(s).")
    print("Scientific candidates remain unapproved; protected vector/DP dependencies are not-run.")
    return 0
