"""Real bounded same-host process measurements, plus a separate simulator.

No claim of heterogeneous physical devices, DP, energy instrumentation or a
completed four-arm field study. Unsupported assurance arms remain visible.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from typing import Any

from fzkml_ci.validate import ROOT, load, require
from fzkml_models.capacity import Job, simulate
from reference.numeric import encode

from .authenticity import validate_native
from .common import file_sha, provenance, save, sha


def sample(
    args: list[str], stdin: bytes = b"", timeout: float = 30, arrival: float | None = None
) -> dict[str, Any]:
    require(hasattr(os, "wait4"), "per-child-resource-accounting-unavailable")
    begin = time.perf_counter()
    process = subprocess.Popen(
        args,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    timed_out = False
    try:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(stdin)
        process.stdin.close()
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.perf_counter() - begin >= timeout:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                _, status, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.002)
        process.returncode = os.waitstatus_to_exitcode(status)
        data = process.stdout.read(32_001)
        require(len(data) <= 32_000, "benchmark-output-bound")
        result = {
            "status": "timeout"
            if timed_out
            else "completed"
            if process.returncode == 0
            else "failed",
            "exit_code": process.returncode,
            "wall_seconds": time.perf_counter() - begin,
            "queue_seconds": max(0, begin - arrival) if arrival is not None else 0.0,
            "cpu_seconds": usage.ru_utime + usage.ru_stime,
            "peak_process_rss_bytes": int(
                usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
            ),
            "stdin_bytes": len(stdin),
            "stdout_bytes": len(data),
            "response": data.decode(),
        }
        return result
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                _, status, _ = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(status)
            except ChildProcessError:
                process.returncode = -1
        if process.stdout is not None:
            process.stdout.close()


def quality(weight: int | None) -> str | None:
    # Disjoint fixed toy records. This is not population generalization.
    if weight is None:
        return None
    plan = load(ROOT / "ci/assurance/benchmark-plan-v1.json")
    holdout = plan["holdout"]
    return str(
        sum(
            (
                Fraction(round(Fraction(weight * x, 16)) - y, 16) ** 2
                for x, y in zip(holdout["x"], holdout["y"], strict=True)
            ),
            Fraction(0),
        )
        / len(holdout["x"])
    )


def validate_plan(plan: dict[str, Any]) -> None:
    require(
        plan["training"] == {"w": 8, "x": [16, -8, 24], "y": [16, -16, 8], "counts": [1, 2, 1]},
        "matched-training-contract",
    )
    train = set(zip(plan["training"]["x"], plan["training"]["y"], strict=True))
    holdout = set(zip(plan["holdout"]["x"], plan["holdout"]["y"], strict=True))
    require(bool(holdout) and not train.intersection(holdout), "evaluation-overlap")
    require(
        plan["holdout"]["x"] == [-12, 12] and plan["holdout"]["y"] == [-12, 12],
        "unsupported-heldout-fixture",
    )
    require(
        plan["quality_semantics"] == "mean-squared-decoded-error-of-RNE-encoded-predictions"
        and plan["quality_threshold"] == "1/9",
        "frozen-quality-semantics",
    )
    require(
        Fraction(quality(8) or "0") > Fraction(plan["quality_threshold"])
        and Fraction(quality(9) or "1") <= Fraction(plan["quality_threshold"]),
        "quality-target-must-distinguish-transition",
    )


def federated(timeout_client: bool) -> dict[str, Any]:
    started = time.perf_counter()

    def client(index: int, arrival: float) -> dict[str, Any]:
        delay = 200 if timeout_client and index == 2 else 10 if index == 1 else 0
        item = sample(
            [sys.executable, "-m", "fzkml_assurance.worker", str(index), str(delay)],
            timeout=0.05 if timeout_client and index == 2 else 5,
            arrival=arrival,
        )
        item.update(
            client=f"synthetic-client-{index}",
            source=f"synthetic-source-{index}",
            virtual_profile="emulated-slow" if delay else "same-host-normal",
            emulated_delay_ms=delay,
        )
        response = item.pop("response")
        item["update"] = None
        if item["status"] == "completed":
            output = json.loads(response)
            require(output["index"] == index and type(output["update"]) is int, "worker-output")
            item["update"] = output["update"]
        return item

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client, i, time.perf_counter()) for i in range(3)]
        clients = [future.result() for future in futures]
    accepted = [c for c in clients if c["status"] == "completed"]
    output = None
    if len(accepted) == 3:
        output = round(
            Fraction(sum(c["update"] * w for c, w in zip(clients, [1, 2, 1], strict=True)), 4)
        )
    return {
        "scenario": "injected-timeout" if timeout_client else "normal",
        "status": "inconclusive" if output is None else "completed",
        "selected": 3,
        "accepted": len(accepted),
        "accepted_sources": [c["source"] for c in accepted],
        "excluded_sources": [c["source"] for c in clients if c["status"] != "completed"],
        "clients": clients,
        "output": output,
        "quality_squared_loss": quality(output),
        "numeric_time_to_quality_seconds": time.perf_counter() - started if output == 9 else None,
        "certified_time_to_quality_seconds": None,
    }


def run(repetitions: int = 1) -> int:
    require(type(repetitions) is int and 1 <= repetitions <= 2, "benchmark-budget")
    fixture = load(ROOT / "ci/assurance/benchmark-plan-v1.json")
    state: dict[str, Any] = {
        "version": 1,
        "issue": 106,
        "status": "running",
        "provenance": provenance(),
        "fixture_digest": file_sha("ci/assurance/benchmark-plan-v1.json"),
        "model_digest": sha(b"public-linear-weight8-scale16-v1"),
        "preprocessor_digest": sha(b"synthetic-integer-identity-v1"),
        "relation_digest": file_sha("specs/numeric-contract-v1.json"),
        "dataset_digest": sha(encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1])),
        "program_digest": file_sha("src/fzkml_assurance/benchmark.py"),
        "field_study_status": "not-run",
        "heterogeneous_physical_devices": "not-inventoried",
        "maximum_concurrent_worker_processes": 2,
        "remote_physical_clients": 0,
        "energy_joules": None,
        "monetary_cost": None,
        "real_network_bytes": None,
        "privacy_budget": {"status": "not-implemented", "epsilon": None, "delta": None},
        "publication_review": {"approved": False},
        "repetitions": [],
        "limitations": [
            "One execution host; emulated delays are not heterogeneous physical hardware.",
            "Local stdio bytes are measured; network/energy/spend are not instrumented.",
            "Central arm executes the same federated transition, not local-only model training.",
            "No matched four-arm security/DP comparison or deployment generalization is claimed.",
            "Only a fixed public toy holdout and one transition; not a field utility study.",
            "Proof-arm wall time includes the complete CI-15 negative-case harness.",
        ],
    }
    validate_plan(fixture)
    require(
        fixture["quality_threshold"] == "1/9"
        and fixture["max_workers"] == 2
        and fixture["protected_unproved_arm"] == "unavailable",
        "benchmark-frozen-plan",
    )
    save("benchmark-run.json", state)
    for index in range(repetitions):
        rep: dict[str, Any] = {
            "index": index,
            "status": "running",
            "arms": [
                {"arm": arm, "status": "not-run"}
                for arm in ["local", "fl", "protected-fl", "proved-fl"]
            ],
        }
        state["repetitions"].append(rep)
        save("benchmark-run.json", state)
        try:
            central = sample(
                [str(ROOT / "target/release/fzkml-contract"), "evaluate"],
                encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1]).hex().encode() + b"\n",
            )
            response = central.pop("response")
            rep["arms"][0] = {
                "arm": "local",
                "scope": "central-same-transition-only",
                "requested_local_only_training": "not-run",
                "status": "inconclusive",
                "sample": central,
                "output": 9 if response.strip() == "9" else None,
                "quality_squared_loss": quality(9) if response.strip() == "9" else None,
                "numeric_time_to_quality_seconds": central["wall_seconds"],
                "certified_time_to_quality_seconds": None,
            }
            require(
                central["status"] == "completed" and response.strip() == "9",
                "central-numeric-output",
            )
            rep["arms"][1] = {
                "arm": "fl",
                "scope": "actual-same-host-virtual-clients",
                "status": "running",
                "scenarios": [],
            }
            normal = federated(False)
            rep["arms"][1]["scenarios"].append(normal)
            require(normal["output"] == 9, "normal-fl-numeric-output")
            rep["arms"][1]["scenarios"].append(federated(True))
            rep["arms"][1]["status"] = "completed-diagnostic"
            rep["arms"][2] = {
                "arm": "protected-fl",
                "scope": "unproved-protected-arm",
                "status": "not-run",
                "reason": "Existing protected backend requires its proof; no matched unproved arm.",
            }
            proof = sample(
                [str(ROOT / "target/release/fzkml-assurance"), "auth", "positive"], timeout=120
            )
            raw = proof.pop("response")
            rep["arms"][3] = {"arm": "proved-fl", "status": "running", "sample": proof}
            require(proof["status"] == "completed", "benchmark-proof-process")
            native = json.loads(raw)
            rep["arms"][3]["native"] = native
            validate_native(native)
            rep["arms"][3] = {
                "arm": "proved-fl",
                "scope": "public-arithmetic-proof-only",
                "status": "completed-diagnostic",
                "sample": proof,
                "native": native,
                "output": native["actual_output"],
                "quality_squared_loss": quality(native["actual_output"]),
                "certified_time_to_toy_quality_seconds": proof["wall_seconds"],
            }
            rep["status"] = "completed-diagnostic"
        except Exception:
            rep["status"] = state["status"] = "failed"
            save("benchmark-run.json", state)
            return 1
        save("benchmark-run.json", state)
    simulated = simulate(
        tuple(Job(str(i), Fraction(0), Fraction(1), Fraction(1)) for i in range(4)),
        (Fraction(1), Fraction(1, 2)),
    )
    state["separate_simulator"] = {
        "kind": "deterministic-discrete-event",
        "physical_clients": 0,
        "outcomes": [
            {"client": r["client"], "status": r["status"], "simulated_latency": str(r["latency"])}
            for r in simulated
        ],
    }
    state["comparison_eligible"] = False
    state["status"] = "completed-diagnostic-field-study-not-run"
    save("benchmark-run.json", state)
    print(
        "Budgeted CPU diagnostics completed; physical heterogeneous field study "
        "and matched security/DP arms remain not-run."
    )
    return 0
