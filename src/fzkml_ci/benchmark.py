"""Conservative comparisons over the shared CI-04 scientific result schema."""

from __future__ import annotations

import math
import statistics
from typing import Any

from .validate import require, validate_result

PHASES = {"setup", "witness", "prove", "aggregate", "verify", "transfer", "total"}


def summarize_times(raw: list[float], failures: int, excluded: int) -> dict[str, Any]:
    """Shared diagnostic summary for CI-04 results and local profiling companions."""
    require(
        len(raw) >= 2 and all(math.isfinite(v) and v >= 0 for v in raw),
        "benchmark-repetitions-required",
    )
    require(failures >= 0 and excluded >= 0, "benchmark-counts")
    return {
        "raw_seconds": raw,
        "mean_seconds": statistics.mean(raw),
        "variance_seconds2": statistics.variance(raw),
        "failures": failures,
        "excluded": excluded,
    }


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    for row in [left, right]:
        validate_result(row)
        require("benchmark" in row, "benchmark-declarations-required")
        require(row["outcome"]["status"] == "successful", "benchmark-outcome")
        plan = row["benchmark"]
        require(set(plan["phases"]) == PHASES, "benchmark-phase-coverage")
        require(
            all(r["quality"] == "pass" for r in row["repetitions"] if r["status"] == "successful"),
            "benchmark-quality-threshold",
        )
        for phase, availability in plan["phases"].items():
            if availability == "measured":
                require(
                    all(
                        any(
                            m["phase"] == phase and m["quantity"] == "time"
                            for m in r["measurements"]
                        )
                        for r in row["repetitions"]
                        if r["status"] == "successful"
                    ),
                    "benchmark-phase-missing",
                )
        # Required resource declarations include a reason when measurement is unavailable.
        for name, quantity in [
            ("peak_memory", "memory"),
            ("proof_bytes", "proof-bytes"),
            ("communication", "communication"),
        ]:
            declaration = plan["resources"][name].strip()
            require(
                declaration == "measured"
                or (declaration.startswith("unavailable:") and len(declaration) > 13),
                "benchmark-resource-declaration",
            )
            if declaration == "measured":
                require(
                    all(
                        any(m["quantity"] == quantity for m in r["measurements"])
                        for r in row["repetitions"]
                        if r["status"] == "successful"
                    ),
                    "benchmark-resource-missing",
                )
    fields = [
        "statement",
        "relation_version",
        "numerical_semantics",
        "security_mode",
        "parameters_digest",
        "model",
        "dataset",
    ]
    require(
        all(left["scenario"][k] == right["scenario"][k] for k in fields),
        "unmatched-scientific-workload",
    )
    require(left["provenance"]["hardware"] == right["provenance"]["hardware"], "unmatched-hardware")
    require(left["benchmark"] == right["benchmark"], "unmatched-benchmark-policy")
    distributions = []
    for row in [left, right]:
        raw = [
            m["value"]
            for r in row["repetitions"]
            if r["status"] == "successful" and not r["excluded"]
            for m in r["measurements"]
            if m["phase"] == "total" and m["quantity"] == "time"
        ]
        require(len(raw) >= 2, "benchmark-repetitions-required")
        distributions.append(
            summarize_times(
                raw,
                sum(r["status"] != "successful" for r in row["repetitions"]),
                sum(r["excluded"] for r in row["repetitions"]),
            )
        )
    return {
        "status": "diagnostic",
        "distributions": distributions,
        "limitations": [
            "Shared runner timings do not enforce performance regressions.",
            "One workload and machine do not establish global fastest performance.",
        ],
    }
