"""Bounded local/CI execution journal. This is operational metadata, not results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .s04 import COMMANDS, artifact_tree, journal, proof_receipt, summary
from .validate import ROOT, Invalid, load, require, schema, validate_result

PROFILES = {
    "contract",
    "tiny-reference",
    "conformance",
    "nightly-adversarial",
    "weekly-proof",
    "integration",
    "protocol-invariants",
}


def write(path: Path, value: Any) -> None:
    if path.absolute().is_relative_to(ROOT):
        current = ROOT
        for part in path.absolute().relative_to(ROOT).parts[:-1]:
            current /= part
            require(not current.is_symlink(), "output-parent-symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def profile(name: str) -> dict[str, Any]:
    require(name in PROFILES, "profile-not-allowlisted")
    value: dict[str, Any] = load(ROOT / "ci" / "profiles" / f"{name}.json")
    require(
        set(value)
        == {
            "version",
            "id",
            "task",
            "repetitions",
            "timeout_seconds",
            "threads",
            "max_input_bytes",
            "warmups",
        },
        "profile-fields",
    )
    require(value["version"] == 1 and value["id"] == name, "profile-version-or-id")
    require(value["task"] in set(COMMANDS) | {"unavailable"}, "profile-task")
    for key, maximum in [
        ("repetitions", 5),
        ("timeout_seconds", 900),
        ("threads", 2),
        ("max_input_bytes", 1000000),
    ]:
        require(type(value[key]) is int and 1 <= value[key] <= maximum, "profile-budget")
    require(value["warmups"] == 0, "warmup-policy")
    require(
        (ROOT / "assets/public/numeric-v1.json").stat().st_size <= value["max_input_bytes"],
        "profile-input-budget",
    )
    return value


def proof_results(value: Any) -> None:
    # Reuse CI-04's executable contract; do not invent a second scientific schema.
    schema(value, "bundle")
    for row in value["results"]:
        validate_result(row)
    records = {row["scenario"]["id"]: row for row in value["results"]}
    require(len(records) == len(value["results"]), "duplicate-proof-scenario")
    for name in ["tiny-proof", "native-circuit-conformance", "negative-cases"]:
        require(name in records, "mandatory-proof-case-missing")
        row = records[name]
        scenario = row["scenario"]
        require(row["outcome"]["status"] == "successful", "mandatory-proof-case-not-passed")
        require(scenario["security_mode"] == "research", "real-proof-mode-required")
        require(
            not any(
                word in scenario["backend"].lower()
                for word in ["mock", "dev", "pending", "synthetic"]
            ),
            "real-backend-required",
        )
        for field in ["program_digest", "circuit_digest", "parameters_digest", "key_digest"]:
            require(scenario[field] != "sha256:" + "0" * 64, "proof-identity-unavailable")
        require(bool(row["repetitions"]), "mandatory-proof-repetitions-missing")
        require(
            all(
                r["status"] == "successful" and not r["timeout"] and not r["excluded"]
                for r in row["repetitions"]
            ),
            "proof-repetition-failed-or-skipped",
        )


def proof_command() -> list[str]:
    adapter = load(ROOT / "ci" / "proof-adapter.json")
    require(
        adapter["version"] == 1 and adapter["status"] == "available", "proof-backend-unavailable"
    )
    command = adapter["command"]
    require(
        isinstance(command, list) and bool(command) and all(isinstance(x, str) for x in command),
        "proof-command-invalid",
    )
    # An adapter is reviewed code. Never accept command/ref/seed strings from dispatch inputs.
    require(command[0].startswith("./scripts/") and ".." not in command[0], "proof-adapter-path")
    return list(command)


def execute(command: list[str], timeout: float, threads: int) -> tuple[str, float]:
    environment = dict(
        os.environ,
        OMP_NUM_THREADS=str(threads),
        OPENBLAS_NUM_THREADS=str(threads),
        MKL_NUM_THREADS=str(threads),
        RAYON_NUM_THREADS=str(threads),
    )
    start = time.monotonic()
    # Discard raw logs; publish bounded codes. Kill includes descendants.
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        code = process.wait(timeout=timeout)
        status = "completed" if code == 0 else "failed"
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        status = "timed-out"
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise
    return status, time.monotonic() - start


def initialize(name: str, output: Path) -> dict[str, Any]:
    config = profile(name)
    state = {
        "version": 1,
        "profile": name,
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "workflow_run": os.environ.get("GITHUB_RUN_ID", "local"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "status": "initialized",
        "repetitions": [
            {"index": i, "status": "not-started", "seconds": None}
            for i in range(config["repetitions"])
        ],
        "limitations": [
            "Operational journal, not scientific measurement or proof evidence.",
            "Artifact survival is not guaranteed; reconcile missing jobs from API.",
        ],
    }
    write(output, state)
    return state


def run(name: str, output: Path) -> int:
    config = profile(name)
    state = load(output)
    journal(state)
    require(state["profile"] == name and state["status"] == "initialized", "journal-state")
    require(
        state["source_sha"]
        == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "journal-source-drift",
    )
    try:
        require(config["task"] != "unavailable", "dependent-protocol-unavailable")
        command = COMMANDS[config["task"]]
        if config["task"] == "proof":
            proof_command()
    except Invalid:
        state["status"] = "unavailable"
        for repetition in state["repetitions"]:
            repetition["status"] = "not-run"
        write(output, state)
        return 1
    seconds: float | None
    for repetition in state["repetitions"]:
        state["status"] = "running"
        repetition["status"] = "running"
        write(output, state)
        try:
            status, seconds = execute(command, config["timeout_seconds"], config["threads"])
        except OSError:
            status, seconds = "failed", None
        repetition.update(status=status, seconds=seconds)
        write(output, state)
        if (
            status == "completed"
            and config["task"] == "proof"
            and (ROOT / "research/proof-results.json").exists()
        ):
            source = ROOT / "research/proof-results.json"
            proof_results(load(source))
            shutil.copyfile(source, output.parent / f"rep-{repetition['index']}-proof-results.json")
        if status != "completed":
            write(
                output.parent / "reproducer.json",
                {
                    "profile": name,
                    "repetition": repetition["index"],
                    "command": f"./scripts/research run {name}",
                    "source_sha": state["source_sha"],
                    "public_seed": 20261125,
                    "fixture_digest": "sha256:"
                    + hashlib.sha256(
                        (ROOT / "assets/public/numeric-v1.json").read_bytes()
                    ).hexdigest(),
                },
            )
    state["status"] = (
        "completed" if all(r["status"] == "completed" for r in state["repetitions"]) else "failed"
    )
    write(output, state)
    return 0 if state["status"] == "completed" else 1


def reconcile(jobs: Any, journal: Any | None) -> dict[str, Any]:
    require(isinstance(jobs, dict) and isinstance(jobs.get("jobs"), list), "workflow-jobs-shape")
    records = []
    for job in jobs["jobs"]:
        conclusion = job.get("conclusion")
        records.append(
            {
                "id": job["id"],
                "status": job["status"],
                "conclusion": conclusion,
                "repetitions": "unknown-without-journal" if journal is None else "see-journal",
            }
        )
    return {
        "version": 1,
        "jobs": records,
        "status": "inconclusive" if journal is None else "reconciled",
        "limitations": [
            "Never infer successful repetitions from a job conclusion.",
            "Cancelled/timed-out/missing journals retain unknown repetitions.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=[
            "init",
            "run",
            "proof",
            "reconcile",
            "verify-artifacts",
            "verify-journal",
            "summary",
        ],
    )
    parser.add_argument("profile", nargs="?", default="contract")
    parser.add_argument("--output", type=Path, default=Path("research/journal.json"))
    parser.add_argument("--jobs", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "verify-journal":
            journal(load(args.output))
        elif args.operation == "verify-artifacts":
            artifact_tree(args.output.parent)
        elif args.operation == "summary":
            print(summary(args.output))
        elif args.operation == "init":
            initialize(args.profile, args.output)
        elif args.operation == "run":
            if not args.output.exists():
                initialize(args.profile, args.output)
            return run(args.profile, args.output)
        elif args.operation == "reconcile":
            require(args.jobs is not None, "jobs-metadata-required")
            write(args.output, reconcile(load(args.jobs), None))
        else:
            command = proof_command()
            (ROOT / "research" / "proof-results.json").unlink(missing_ok=True)
            (ROOT / "research" / "proof-check.json").unlink(missing_ok=True)
            status, _ = execute(command, 600, 2)
            require(status == "completed", "real-proof-execution-failed")
            source = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
            receipt = load(ROOT / "research/proof-check.json")
            proof_receipt(receipt, source)
            if os.environ.get("GITHUB_RUN_ID"):
                results = load(ROOT / "research/proof-results.json")
                proof_results(results)
                require(
                    all(row["provenance"]["source_commit"] == source for row in results["results"]),
                    "stale-proof-results",
                )
            else:
                print("Local genuine proof executed; publication remains pending review.")
    except (Invalid, OSError, ValueError, KeyError, TypeError):
        print(
            "research gate failed: unavailable backend, invalid record or execution",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
