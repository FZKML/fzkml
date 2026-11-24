"""Run only the original public fixture, keeping protocol randomness unrecorded."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import torch  # noqa: E402
from fzkml_native.torch_adapter import profile_tiny  # noqa: E402

from fzkml_ci.validate import validate_result  # noqa: E402


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


model = torch.nn.Linear(1, 1, bias=False, dtype=torch.float64)
with torch.no_grad():
    model.weight.fill_(0.5)
x = torch.tensor([[1.0], [-0.5], [1.5]], dtype=torch.float64)
y = torch.tensor([[1.0], [-1.0], [0.5]], dtype=torch.float64)
profile = profile_tiny(model, x, y, (1, 2, 1))
profile["digests"] = {
    name: digest((ROOT / name).read_bytes())
    for name in (
        "Cargo.lock",
        "uv.lock",
        "specs/numeric-contract-v1.json",
        "assets/public/numeric-v1.json",
    )
}
profile["source_commit"] = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
).strip()
profile["source_dirty"] = bool(
    subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT)
)
profile["workflow_run"] = int(os.environ.get("GITHUB_RUN_ID", "0"))
output = ROOT / "reports"
output.mkdir(exist_ok=True)
(output / "language-profile.json").write_text(json.dumps(profile, indent=2) + "\n")
print(json.dumps(profile, sort_keys=True))
if not profile["proof_valid"]:
    raise SystemExit("public synthetic proof failed")

# The general CI result schema cannot express every detailed conversion/witness
# phase. Retain those raw phases in the companion profile; map coarse phases here.
# A local run with no workflow identity stays a local profile, never invent run IDs.
if profile["workflow_run"]:
    result = copy.deepcopy(json.loads((ROOT / "examples/results.json").read_text())["results"][0])
    result["run_id"] = "synthetic:language-tiny-" + str(profile["workflow_run"])
    scenario = result["scenario"]
    scenario.update(
        {
            "id": "language-tiny",
            "statement": "public-exact-linear-three-client",
            "relation_version": profile["contract_version"],
            "numerical_semantics": "fixed16-rne",
            "backend": profile["backend"],
            "security_mode": "research",
            "parameters_digest": "sha256:" + profile["parameters_id"],
            "key_digest": "sha256:" + profile["key_id"],
            "program_digest": digest((ROOT / "crates/fzkml-core/src/lib.rs").read_bytes()),
            "circuit_digest": digest((ROOT / "crates/fzkml-core/src/proof.rs").read_bytes()),
        }
    )
    for key in ("model", "dataset"):
        scenario[key] = {
            "id": "synthetic:tiny-linear-" + key,
            "version": "numeric-v1",
            "digest": digest((ROOT / "assets/public/numeric-v1.json").read_bytes()),
            "license": "Apache-2.0",
            "publication": "permitted",
        }
    memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    result["provenance"] = {
        "source_commit": profile["source_commit"],
        "workflow_path": ".github/workflows/language.yml",
        "workflow_run": profile["workflow_run"],
        "toolchain": "rust-1.85.1-python-3.11.14-torch-2.5.1",
        "dependency_digest": digest(
            (ROOT / "Cargo.lock").read_bytes() + (ROOT / "uv.lock").read_bytes()
        ),
        "hardware": {
            "cpu": platform.machine(),
            "memory_bytes": memory,
            "accelerator": "none",
            "os": platform.system(),
            "runner_image_revision": os.environ.get("ImageVersion", "unknown"),
        },
    }
    result["randomness"] = {
        "public_experiment_seed": 7,
        "protocol_randomness": "private-not-recorded",
        "dp_randomness": "not-applicable",
    }
    result["outcome"] = {
        "status": "successful",
        "reason": "Tiny public exact arithmetic proof verified; no quality/security claim.",
    }
    seconds = profile["seconds"]
    phases = {
        "train": seconds["training"],
        "evaluate": seconds["conversion_and_copying"],
        "setup": seconds["setup"],
        "prove": seconds["host_witness_generation"] + seconds["proving"],
        "verify": seconds["verification"],
    }
    measurements = [
        {"phase": phase, "quantity": "time", "unit": "s", "value": value}
        for phase, value in phases.items()
    ]
    result["repetitions"] = [
        {
            "id": "rep1",
            "attempt": 1,
            "status": "successful",
            "timeout": False,
            "excluded": False,
            "reason": "One original public synthetic fixture.",
            "quality": "not-measured",
            "measurements": measurements,
        }
    ]
    result["metrics"] = [
        {**m, "aggregation": "mean", "repetition_ids": ["rep1"]} for m in measurements
    ]
    result["limitations"] = profile["limitations"] + [
        "Quality differences and detailed phases are in reports/language-profile.json."
    ]
    result["publication_review"] = {"approved": True, "review_id": "synthetic:fixed-fixture-only"}
    validate_result(result)
    (output / "language-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Validated actual CI result against shared result schema 1.0.0")
