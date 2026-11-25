"""Measure only the fixed public v0.2 fixture; no private protocol state is logged."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fzkml_ci.validate import validate_result  # noqa: E402


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sample(binary: Path) -> dict[str, Any]:
    # Fresh sampler: its only child is the native fixture. Cargo/git/Python RSS
    # cannot contaminate RUSAGE_CHILDREN's high-water mark.
    with tempfile.TemporaryDirectory(prefix="fzkml-private-aggregate-") as directory:
        start = time.perf_counter()
        run = subprocess.run(
            [str(binary), str(Path(directory) / "ledger.sqlite")],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if run.returncode or len(run.stdout) > 30_000:
            raise ValueError("fixed-aggregation-fixture-failed")
        report: dict[str, Any] = json.loads(run.stdout)
        report["seconds"]["end-to-end"] = time.perf_counter() - start
        peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        report["peak_process_rss_bytes"] = int(peak if sys.platform == "darwin" else peak * 1024)
        return report


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--sample":
        print(json.dumps(sample(Path(sys.argv[2]).resolve())))
        return
    if len(sys.argv) != 2:
        raise ValueError("output-directory-required")
    output = Path(sys.argv[1])
    binary = ROOT / "target/release/fzkml-aggregate-demo"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT)
    )
    samples = []
    for _ in range(3):
        data = subprocess.check_output(
            [sys.executable, __file__, "--sample", str(binary)], cwd=ROOT, timeout=130
        )
        samples.append(json.loads(data))
    if not all(s["reference_match"] for s in samples):
        raise ValueError("exact-reference-mismatch")
    workflow_run = int(os.environ.get("GITHUB_RUN_ID", "0")) or None
    result = copy.deepcopy(json.loads((ROOT / "examples/results.json").read_text())["results"][0])
    result.update(
        schema_version="1.1.0",
        run_id="synthetic:protected-aggregation-" + commit[:12],
        claim_ids=[],
    )
    scenario = result["scenario"]
    scenario.update(
        id="protected-aggregation-v02",
        statement="private-exact-sgd-three-client-vss",
        relation_version="fzkml-protected-aggregation-v1",
        numerical_semantics="fixed16-rne-offset80",
        backend="arkworks-groth16-bn254-pedersen-babyjubjub",
        security_mode="research",
        # Fresh research keys per repetition: these digests identify the ordered
        # list of all repetition keys, not an invented single shared setup.
        parameters_digest=digest(json.dumps([s["parameters_id"] for s in samples]).encode()),
        key_digest=digest(json.dumps([s["key_id"] for s in samples]).encode()),
        program_digest=digest(
            b"".join(
                p.read_bytes()
                for p in sorted((ROOT / "crates/fzkml-core/src/aggregation").glob("*.rs"))
            )
        ),
        circuit_digest=digest((ROOT / "crates/fzkml-core/src/aggregation/crypto.rs").read_bytes()),
    )
    for key in ("model", "dataset"):
        scenario[key] = {
            "id": "synthetic:protected-tiny-" + key,
            "version": "numeric-v1",
            "digest": digest((ROOT / "assets/public/numeric-v1.json").read_bytes()),
            "license": "Apache-2.0",
            "publication": "permitted",
        }
    result["provenance"] = {
        "source_commit": commit,
        "execution_kind": "github-actions" if workflow_run else "local",
        "workflow_path": ".github/workflows/cpu.yml" if workflow_run else None,
        "workflow_run": workflow_run,
        "toolchain": "rust-1.85.1-python-3.11.14",
        "dependency_digest": digest(
            (ROOT / "Cargo.lock").read_bytes() + (ROOT / "uv.lock").read_bytes()
        ),
        "hardware": {
            "cpu": platform.machine(),
            "memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
            "accelerator": "none",
            "os": platform.system(),
            "runner_image_revision": os.environ.get("ImageVersion", "local-unspecified"),
        },
    }
    result["randomness"] = {
        "public_experiment_seed": 0,
        "protocol_randomness": "private-not-recorded",
        "dp_randomness": "not-applicable",
    }
    result["outcome"] = {
        "status": "successful",
        "reason": (
            "Three original synthetic fixtures match the exact reference; "
            "cryptographic/domain review pending."
        ),
    }
    repetitions: list[dict[str, Any]] = []
    for i, s in enumerate(samples):
        measurements = [
            {"phase": k, "quantity": "time", "unit": "s", "value": v}
            for k, v in s["seconds"].items()
        ]
        measurements += [
            {
                "phase": "end-to-end",
                "quantity": "memory",
                "unit": "byte",
                "value": s["peak_process_rss_bytes"],
            },
            {
                "phase": "communicate",
                "quantity": "communication",
                "unit": "byte",
                "value": s["application_bytes"],
            },
        ]
        repetitions.append(
            {
                "id": f"rep{i + 1}",
                "attempt": 1,
                "status": "successful",
                "timeout": False,
                "excluded": False,
                "reason": "Fresh native process and independent private research setup.",
                "quality": "not-measured",
                "measurements": measurements,
            }
        )
    result["repetitions"] = repetitions
    result["metrics"] = [
        {
            **m,
            "value": sum(r["measurements"][j]["value"] for r in repetitions) / len(repetitions),
            "aggregation": "mean",
            "repetition_ids": [r["id"] for r in repetitions],
        }
        for j, m in enumerate(repetitions[0]["measurements"])
    ]
    result["limitations"] = samples[0]["limitations"] + [
        "All repetitions retained; setup included separately and in end-to-end wall/RSS. "
        "No quality experiment, transport benchmark or per-role memory measurement.",
        "Fresh per-repetition parameter/key IDs are in the companion profile; "
        "scenario digests hash their ordered lists.",
        "Public experiment seed 0 denotes literal fixed inputs; "
        "it does not seed credentials, proofs, sharing or setup.",
        "Source working tree dirty: "
        + str(dirty)
        + ". Companion profile records source/dependency/spec digests; "
        "no invented CI identity or independent approval.",
    ]
    result["publication_review"] = {
        "approved": False,
        "review_id": "synthetic:protected-aggregation-pending",
    }
    validate_result(result)
    output.mkdir(parents=True, exist_ok=True)
    (output / "aggregation-result.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "aggregation-profile.json").write_text(
        json.dumps(
            {
                "source_commit": commit,
                "source_dirty": dirty,
                "spec_digest": digest((ROOT / "specs/aggregation-v1.json").read_bytes()),
                "samples": samples,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        "Validated v0.2 aggregation: 3 repetitions; exact model 9; "
        "result schema 1.1.0; publication review pending."
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError):
        raise SystemExit("aggregation-measurement-failed") from None
