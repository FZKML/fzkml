"""Offline quota checking; synthetic trust anchors never authorize live dispatch."""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

from specifications.ci_assurance.rounds import require


def matrix_digest(config: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def check_software(manifest: Path) -> None:
    require(manifest.stat().st_size <= 8192, "software-manifest-budget")
    descriptor = json.loads(manifest.read_text())
    expected = {
        "__init__.py",
        "disclosure.py",
        "parameters.py",
        "planner.py",
        "rounds.py",
        "run.py",
    }
    require(
        set(descriptor) == {"kind", "files"}
        and descriptor["kind"] == "reference-python-source-v1"
        and set(descriptor["files"]) == expected,
        "software-manifest-shape",
    )
    for name, digest in descriptor["files"].items():
        path = manifest.parent / name
        require(
            not path.is_symlink()
            and path.is_file()
            and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
            "software-member-mismatch",
        )


def plan_matrix(
    config: dict[str, Any],
    trusted_digests: frozenset[str],
    dataset: Path,
    software: Path,
    *,
    trusted_context: bool = True,
    dispatch_requested: bool = False,
) -> dict[str, Any]:
    require(not dispatch_requested, "live-dispatch-unsupported")
    require(trusted_context, "untrusted-dispatch-context")
    require(matrix_digest(config) in trusted_digests, "matrix-review-digest-not-authorized")
    require(
        set(config)
        == {
            "id",
            "command_id",
            "axes",
            "resources",
            "quotas",
            "attempts",
            "concurrency",
            "dataset_sha256",
            "software_sha256",
        },
        "matrix-fields",
    )
    require(
        config["id"] == "synthetic-ci20-v1" and config["command_id"] == "ci-assurance-reference-v1",
        "unsupported-producer",
    )
    for key, path in (("dataset_sha256", dataset), ("software_sha256", software)):
        require(
            config[key] == hashlib.sha256(path.read_bytes()).hexdigest(), "immutable-input-mismatch"
        )
    check_software(software)
    resource = config["resources"]
    require(
        resource
        == {
            "hardware": "cpu-reference",
            "cpus": 1,
            "gpus": 0,
            "gpu_model": None,
            "ram_mib": 2048,
            "disk_mib": 1024,
            "timeout_seconds": 60,
        }
        and all(
            type(resource[k]) is int
            for k in ("cpus", "gpus", "ram_mib", "disk_mib", "timeout_seconds")
        ),
        "hardware-resource-policy",
    )
    require(
        type(config["attempts"]) is int
        and 1 <= config["attempts"] <= 2
        and type(config["concurrency"]) is int
        and 1 <= config["concurrency"] <= 2,
        "retry-concurrency-policy",
    )
    axes = config["axes"]
    require(isinstance(axes, dict) and 1 <= len(axes) <= 4, "axis-budget")
    jobs = 1
    for name, values in axes.items():
        require(
            re.fullmatch(r"[a-z][a-z0-9_]{0,15}", name)
            and isinstance(values, list)
            and 1 <= len(values) <= 8
            and all(isinstance(v, str) and re.fullmatch(r"[a-z0-9-]{1,24}", v) for v in values)
            and len(set(values)) == len(values),
            "explicit-axis-required",
        )
        jobs *= len(values)
        require(jobs <= 16, "matrix-product-budget")
    attempts = jobs * config["attempts"]
    simultaneous = min(jobs, config["concurrency"])
    totals = {
        "jobs": jobs,
        "attempts": attempts,
        "serial_seconds": attempts * 60,
        "cpu_seconds": attempts * 60,
        "gpu_seconds": 0,
        "concurrent_ram_mib": simultaneous * 2048,
        "concurrent_disk_mib": simultaneous * 1024,
        "cumulative_disk_mib": attempts * 1024,
    }
    quotas = config["quotas"]
    require(
        set(quotas) == set(totals)
        and all(type(v) is int and 0 <= v <= 65536 for v in quotas.values()),
        "explicit-quota-required",
    )
    require(all(totals[k] <= quotas[k] for k in totals), "total-work-exceeds-quota")
    rows = [dict(zip(axes, values, strict=True)) for values in itertools.product(*axes.values())]
    return {
        "matrix_digest": matrix_digest(config),
        "totals": totals,
        "rows": rows,
        "dispatch_authorized": False,
        "review_scope": "synthetic-test-only",
    }
