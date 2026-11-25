from __future__ import annotations

import hashlib
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from fzkml_ci.research import write
from fzkml_ci.validate import ROOT, load, public_tree, require

BASE = "b602197104d810bc1a41a2ea24085b25484272b7"
OUTPUT = ROOT / "reports/assurance"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(name: str) -> str:
    return sha((ROOT / name).read_bytes())


def check_schema(value: Any, name: str) -> None:
    public_tree(value)
    definition = load(ROOT / f"ci/assurance/{name}-schema-v1.json")
    require(Draft202012Validator(definition).is_valid(value), f"assurance-{name}-schema")


def provenance() -> dict[str, Any]:
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    )
    run = os.environ.get("GITHUB_RUN_ID")
    require(
        not run
        or (
            run.isdigit() and int(run) > 0 and not dirty and os.environ.get("GITHUB_SHA") == source
        ),
        "assurance-hosted-provenance",
    )
    rust = subprocess.check_output(["rustc", "--version"], text=True).split()[1]
    uv = subprocess.check_output(["uv", "--version"], text=True).split()[1]
    require(
        (rust, uv, platform.python_version()) == ("1.85.1", "0.9.11", "3.11.14"),
        "pinned-tools-required",
    )
    return {
        "source_commit": source,
        "source_dirty": dirty,
        "execution_kind": "github-actions" if run else "local",
        "workflow_run": int(run) if run else None,
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF") if run else None,
        "python": platform.python_version(),
        "rust": rust,
        "uv": uv,
        "hardware": {
            "architecture": platform.machine(),
            "os": platform.system(),
            "logical_cpus": os.cpu_count(),
            "processor": platform.processor() or "unavailable",
            "memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
            "runner_image_revision": os.environ.get("ImageVersion", "unavailable"),
            "execution_hosts": 1,
            "physical_hardware_inventory": "not-verified",
            "accelerator": "none",
        },
        "dependency_digest": sha(
            (ROOT / "Cargo.lock").read_bytes() + (ROOT / "uv.lock").read_bytes()
        ),
    }


def save(name: str, value: Any) -> None:
    if name in {"golden-run.json", "authenticity-run.json", "benchmark-run.json"}:
        check_schema(value, name.removesuffix(".json"))
    write(OUTPUT / name, value)


def blob(commit: str, path: str) -> bytes:
    require(
        len(commit) == 40 and all(c in "0123456789abcdef" for c in commit),
        "immutable-source-required",
    )
    require(not Path(path).is_absolute() and ".." not in Path(path).parts, "source-path")
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
