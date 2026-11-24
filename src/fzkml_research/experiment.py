"""Bounded synthetic CPU experiment; result records reuse CI-04, comparisons CI-11."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

from fzkml_ci.benchmark import summarize_times
from fzkml_ci.report import canonical
from fzkml_ci.validate import ROOT, Invalid, public_tree, require

from .kernels import NUMERICAL_SEMANTICS, RELATION, Matrix, reference, transposed
from .profiling import Event, LiveSample, ledger, summarize

SIZE, MODULUS, REPETITIONS, WARMUPS = 32, 2**61 - 1, 6, 1


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def worker(backend: str) -> dict[str, Any]:
    require(backend in {"reference", "transposed"}, "kernel-backend")
    events: list[Event] = []
    origin = time.perf_counter_ns()

    def phase(name: str, operation: Callable[[], Any], sent: int = 0) -> Any:
        start, cpu = time.perf_counter_ns(), time.process_time_ns()
        value = operation()
        end, used = time.perf_counter_ns(), time.process_time_ns() - cpu
        events.append(
            Event(
                name,
                "one",
                "cpu-0",
                name,
                start - origin,
                end - origin,
                used,
                sent,
                setup_mode="cold" if name == "setup" else "not-applicable",
            )
        )
        return value

    def prepare() -> tuple[Matrix, Matrix]:
        return (
            tuple(
                tuple((i * 97 + j * 31 + 17) % MODULUS for j in range(SIZE)) for i in range(SIZE)
            ),
            tuple(
                tuple((i * 19 - j * 73 - 11) % MODULUS for j in range(SIZE)) for i in range(SIZE)
            ),
        )

    a, b = phase("prepare", prepare)
    phase("setup", lambda: (SIZE, MODULUS))
    kernel = reference if backend == "reference" else transposed
    result = phase("evaluate", lambda: kernel(a, b, MODULUS))

    # Verify with an independently expressed integer sum, outside timed kernel work.
    def verify() -> None:
        for i in range(SIZE):
            for j in range(SIZE):
                expected = sum(a[i][k] * b[k][j] for k in range(SIZE)) % MODULUS
                require(result[i][j] == expected, "kernel-reference-mismatch")

    phase("verify", verify)
    encoded = canonical(result).encode()
    copied = phase("transfer", lambda: memoryview(encoded).tobytes(), len(encoded))
    with tempfile.TemporaryDirectory(prefix="fzkml-native-") as tmp:
        output = Path(tmp) / "synthetic-output.json"

        def release() -> None:
            with output.open("xb") as stream:
                stream.write(copied)
                stream.flush()
                os.fsync(stream.fileno())

        phase("release", release)
        disk = output.stat().st_size
    # One fresh process per repetition: joint process high-water RSS includes imports.
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = int(rss if sys.platform == "darwin" else rss * 1024)
    # A high-water RSS counter is not an instantaneous live-resource sample.
    samples: list[LiveSample] = []
    report = summarize(events, samples, [], budget_ns=20_000_000_000, quality_target=Fraction(0))
    report["memory_method"] = (
        "OS process lifetime high-water RSS; includes interpreter/imports; one worker"
    )
    report["disk_method"] = "Single complete temporary output file, removed after fsync"
    report["os_worker_peak_rss_bytes"] = rss_bytes
    report["disk_peak_bytes"] = disk
    report["coordinator_memory"] = (
        "unavailable; worker RSS is not aggregate parent-plus-child memory"
    )
    report["complete_protected_path"] = {
        p: "not-run" for p in ("train", "witness", "prove", "aggregate")
    }
    report["transfer_scope"] = "Local buffer copy; no network transfer or protected release"
    return {
        "backend": backend,
        "result_digest": digest(result),
        "rss_bytes": rss_bytes,
        "profile": report,
        "ledger": ledger(events, samples),
    }


def _invoke(backend: str) -> dict[str, Any]:
    start = time.perf_counter_ns()
    child = subprocess.run(
        [sys.executable, "-m", "fzkml_research.experiment", "--worker", backend],
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=20,
    )
    elapsed = time.perf_counter_ns() - start
    require(child.returncode == 0 and len(child.stdout) <= 100_000, "kernel-child-failed")
    value: dict[str, Any] = json.loads(child.stdout)
    public_tree(value)
    value["end_to_end_ns"] = elapsed
    value["launch_import_and_ipc_ns"] = max(0, elapsed - value["profile"]["wall_ns"])
    return value


def run() -> dict[str, Any]:
    require(
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", "src", "scripts", "schemas", "specs", "tests"],
            cwd=ROOT,
        ).returncode
        == 0,
        "commit-research-source-before-measurement",
    )
    require(
        not subprocess.check_output(
            [
                "git",
                "ls-files",
                "--others",
                "--exclude-standard",
                "--",
                "src",
                "scripts",
                "specs",
                "tests",
            ],
            cwd=ROOT,
        ).strip(),
        "untracked-research-source",
    )
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    plan = {
        "version": "native-kernel-plan-1",
        "size": SIZE,
        "modulus": MODULUS,
        "warmups": WARMUPS,
        "repetitions": REPETITIONS,
        "order": "alternating-reference-transposed",
        "assurance": "native-arithmetic-only",
        "seed": "no-random-input-generation",
    }
    records: dict[str, list[dict[str, Any]]] = {"reference": [], "transposed": []}
    warmups = [_invoke(name) for name in records for _ in range(WARMUPS)]
    for index in range(REPETITIONS):
        for name in ["reference", "transposed"] if index % 2 == 0 else ["transposed", "reference"]:
            records[name].append(_invoke(name))
    require(
        len({r["result_digest"] for rows in [warmups, *records.values()] for r in rows}) == 1,
        "optimized-semantics-mismatch",
    )
    if sys.platform == "darwin":
        cpu_model = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
        ).strip()
        memory_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True))
    else:
        cpu_model = next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            platform.machine(),
        )
        memory_bytes = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    hardware = {
        "cpu": cpu_model,
        "architecture": platform.machine(),
        "workers": 1,
        "threads_per_worker": 1,
        "python_version": platform.python_version(),
        "memory_bytes": memory_bytes,
        "accelerator": "none",
        "os": platform.system() + "-" + platform.release(),
        "runner_image_revision": os.environ.get("ImageVersion", "local-no-hosted-image"),
    }
    distributions = [
        summarize_times([r["end_to_end_ns"] / 1e9 for r in records[name]], 0, 0)
        for name in ("reference", "transposed")
    ]
    comparison = {
        "status": "diagnostic",
        "distributions": distributions,
        "scope": "Matched native arithmetic only; not a proof-backend bakeoff.",
    }

    def mean(name: str, field: str) -> float:
        return float(statistics.mean(row[field] for row in records[name]))

    return {
        "experiment": "synthetic-native-kernel-v1",
        "plan": plan,
        "companion_version": "native-profile-1.0.0",
        "execution_origin": {
            "kind": "github-actions" if os.environ.get("GITHUB_RUN_ID") else "local",
            "source_commit": source,
            "workflow_run": os.environ.get("GITHUB_RUN_ID"),
        },
        "hardware": hardware,
        "numerical_relation": RELATION,
        "numerical_semantics": NUMERICAL_SEMANTICS,
        "dependency_digest": "sha256:"
        + hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "program_digest": "sha256:"
        + hashlib.sha256((ROOT / "src/fzkml_research/kernels.py").read_bytes()).hexdigest(),
        "comparison": comparison,
        "raw_profiles": records,
        "warmup_profiles": warmups,
        "end_to_end_speed_ratio": mean("reference", "end_to_end_ns")
        / mean("transposed", "end_to_end_ns"),
        "gpu": {
            "status": "not-run",
            "reason": "No GPU/authorized accelerator adapter in this experiment.",
        },
        "backend_bakeoff": {
            "status": "not-run",
            "reason": "Full proof and payload-binding dependencies #33/#44 not available.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=["reference", "transposed"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = worker(args.worker) if args.worker else run()
        output = canonical(result)
        if args.output:
            with args.output.open("x") as stream:
                stream.write(output)
        else:
            print(output, end="")
    except (Invalid, OSError, ValueError, subprocess.SubprocessError):
        print("experiment failed: bounded-research-execution", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
