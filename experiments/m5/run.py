"""Run the three proofs, compare with an independent reference, and record provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from workloads import neural, observations, robust

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "experiments/m5"
BUILD = "cargo build --release --locked -p fzkml-core --bin fzkml-m5-proof"
COMMAND = f"{BUILD} && python experiments/m5/run.py"
SOURCE_FILES = (
    "experiments/m5/contract-v1.json",
    "experiments/m5/workloads.py",
    "experiments/m5/run.py",
    "experiments/m5/run-v1.schema.json",
    "crates/fzkml-core/src/model_workloads.rs",
    "crates/fzkml-core/src/bin/fzkml-m5-proof.rs",
    "crates/fzkml-core/src/proof.rs",
    "Cargo.lock",
    "uv.lock",
)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def host_cpu() -> str:
    # Apple systems frequently leave platform.processor() as only "arm".
    if sys.platform == "darwin":
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    if Path("/proc/cpuinfo").is_file():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() in {"model name", "Processor"}:
                return value.strip()
    return platform.processor() or f"{platform.machine()} (CPU model unavailable)"


def record(binary: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(binary.resolve())],
        check=True,
        text=True,
        capture_output=True,
        timeout=120,
    )
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_bytes = int(peak if sys.platform == "darwin" else peak * 1024)
    proofs = json.loads(result.stdout)
    observed = observations()
    expected = {
        "median": observed["89"]["expected_output"],
        "inference": observed["90"]["expected_inference_output"],
        "train": observed["90"]["expected_training_output"],
    }
    for kind, output in expected.items():
        if proofs[kind]["output"] != output:
            raise ValueError(f"proof/reference disagreement: {kind}")

    contract_path = EXPERIMENT / "contract-v1.json"
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    fingerprint = sha256((EXPERIMENT / "workloads.py").read_bytes())
    return {
        "version": "fzkml-m5-run-1",
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "source_files": {name: sha256((ROOT / name).read_bytes()) for name in SOURCE_FILES},
        "input_digests": {
            issue: sha256(canonical([issue, fingerprint, values.get("input")]))
            for issue, values in observed.items()
        },
        "contract_sha256": sha256(contract_bytes),
        "dataset_provenance": contract["provenance"],
        "scope": contract["scope"],
        "reproduce": COMMAND,
        "environment": {
            "os": platform.platform(),
            "arch": platform.machine(),
            "cpu": host_cpu(),
            "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
            "python": platform.python_version(),
            "binary_sha256": sha256(binary.read_bytes()),
            "runner": os.environ.get("RUNNER_OS", "local"),
        },
        "proof_peak_process_rss_bytes": peak_bytes,
        "excluded_phases": [
            "Rust compilation and executable launch excluded from per-proof phase times",
            "Distributed proving, network and accelerator runs excluded",
            "Raw witness, commitment openings and keys intentionally omitted from records",
        ],
        "outcomes": {
            issue: "proof-verified" if issue in {"89", "90"} else "reference-executed"
            for issue in observed
        },
        "proofs": proofs,
        "observations": observed,
    }


def validate(report: dict[str, Any]) -> None:
    definition = json.loads((EXPERIMENT / "run-v1.schema.json").read_bytes())
    Draft202012Validator(definition).validate(report)
    if report["contract_sha256"] != sha256((EXPERIMENT / "contract-v1.json").read_bytes()):
        raise ValueError("run contract digest differs")
    contract = json.loads((EXPERIMENT / "contract-v1.json").read_bytes())
    if report["scope"] != contract["scope"]:
        raise ValueError("observer or release policy differs from the run contract")
    files = report["source_files"]
    if set(files) != set(SOURCE_FILES):
        raise ValueError("source file list differs")
    for name, digest in files.items():
        if sha256((ROOT / name).read_bytes()) != digest:
            raise ValueError(f"run source digest differs: {name}")
    seen = report["observations"]
    if canonical(seen["89"]) != canonical(robust()) or canonical(seen["90"]) != canonical(neural()):
        raise ValueError("recorded proof reference observations differ")
    expected = {
        "median": seen["89"]["expected_output"],
        "inference": seen["90"]["expected_inference_output"],
        "train": seen["90"]["expected_training_output"],
    }
    if any(report["proofs"][kind]["output"] != value for kind, value in expected.items()):
        raise ValueError("proof and reference outputs differ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release/fzkml-m5-proof")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check", type=Path, help="validate a stored run without generating a proof"
    )
    args = parser.parse_args()
    if args.check is not None:
        validate(json.loads(args.check.read_bytes()))
        return
    report = record(args.binary)
    validate(report)
    content = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        print(content, end="")
    else:
        args.output.write_text(content)


if __name__ == "__main__":
    main()
