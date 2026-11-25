#!/usr/bin/env python3
"""Validate bounded retained numerical evidence; never turn it into a protected proof."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import math
import subprocess
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from python.fzkml_math.data_experiment_contract import INPUT_PATHS
from python.fzkml_math.toy_generation import verify_control, verify_denoising

ROOT = Path(__file__).resolve().parents[1]


def check_report(r: dict[str, Any]) -> None:
    Draft202012Validator(
        json.loads((ROOT / "schemas/s02-data-run-1.0.0.json").read_text())
    ).validate(r)
    if r["source_dirty"] or r["status"] != "completed" or r["failures"]:
        raise ValueError("incomplete-or-dirty-evidence")
    expected = set(itertools.product(range(3), (64, 256, 1024), (1, 4, 8)))
    actual = [(p["repetition"], p["records"], p["queries"]) for p in r["repetitions"]]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("missing-or-duplicated-profile")
    if set(r["digests"]) != set(INPUT_PATHS):
        raise ValueError("input-digest-inventory-mismatch")
    for name, value in r["digests"].items():
        path = ROOT / name  # INPUT_PATHS is a fixed local allowlist.
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != value:
            raise ValueError("input-drift:" + name)
    for p in r["repetitions"]:
        q = p["queries"]
        if {m["mode"] for m in p["modes"]} != {"exact", "approximate"}:
            raise ValueError("missing-comparison-mode")
        for m in p["modes"]:
            if (
                m["actual_queries"] != q
                or m["actual_reuse_opportunities"] != q - 1
                or m["cache_builds"] != 1
                or m["cache_reads"] != q
                or m["summary_dimension_scalars"] != 7
                or len(m["errors"]) != q
            ):
                raise ValueError("reuse-or-dimension-inventory-mismatch")
            for field in ("summary_setup_seconds", "cached_query_seconds", "total_seconds"):
                if not math.isfinite(m[field]) or m[field] < 0:
                    raise ValueError("invalid-measurement")
            if not math.isclose(
                m["total_seconds"], m["summary_setup_seconds"] + m["cached_query_seconds"]
            ) or not math.isclose(
                m["validated_comparison_total_seconds"], p["full_data_seconds"] + m["total_seconds"]
            ):
                raise ValueError("omitted-timing-phase")
            for e in m["errors"]:
                if F(e["objective_error"]) > F(e["objective_bound"]) or any(
                    F(a) > F(b)
                    for a, b in zip(e["gradient_error"], e["gradient_bounds"], strict=True)
                ):
                    raise ValueError("numerical-error-exceeds-bound")
                if m["mode"] == "exact" and (
                    F(e["objective_error"]) != 0 or any(F(g) != 0 for g in e["gradient_error"])
                ):
                    raise ValueError("inexact-exact-summary")
    for setup in r["fixture_setup"]:
        if setup["actual_profile_reuses"] != 3 or setup["unique_synthetic_pairs"] > 33:
            raise ValueError("incorrect-fixture-reuse-or-diversity")
    s = r["stream"]
    if (
        [v["sum_mm"] for v in s["rounds"]] != [30, 60, 90, 70]
        or [v["observer_event_count"] for v in s["rounds"]] != [1, 2, 3, 4]
        or not s["identical_redelivery"]
        or s["status_after_restart"]["observer_ledger"]["events"] != 4
    ):
        raise ValueError("stream-effect-or-observer-history-mismatch")
    faults = r["faults"]
    if (
        [v["exit_code"] for v in faults["crashes"]] != [91, 92, 94, 93]
        or faults["precommit_state"]["accepted_event_versions"] != 0
        or faults["postcommit_state"]["accepted_event_versions"] != 1
        or faults["advance_rolled_back"]["round"] != 0
        or faults["recovered"]["accounted_release_count"] != 1
        or faults["recovered"]["observer_ledger"]["events"] != 1
    ):
        raise ValueError("crash-recovery-evidence-mismatch")
    verify_denoising(r["toy"]["exact_denoising"])
    verify_denoising(r["toy"]["quantized_denoising"], scale=16)
    verify_control(r["toy"]["control"])
    if not r["toy"]["untrained_predictor_worsens_metric"]:
        raise ValueError("negative-finding-omitted")
    n = r["negative_findings"]
    if (
        n["hash_dictionary_matches"] != [3]
        or n["self_consistent_cache_checksum_accepts_wrong_derivation"] is not True
        or n["single_record_statistic_T0_reconstructs_label"] != "-1"
        or n["alias_without_canonical_map"] != "3/2"
        or n["alias_with_fixed_canonical_map"] != "3/4"
    ):
        raise ValueError("negative-finding-mismatch")


def mutation_checks(report: dict[str, Any]) -> None:
    cases = []
    for name in ("duplicate", "DP", "proof", "reuse", "cost", "exact", "fault", "toy"):
        r = copy.deepcopy(report)
        if name == "duplicate":
            r["repetitions"][1] = r["repetitions"][0]
        elif name == "DP":
            r["stream"]["DP_guarantee"] = True
        elif name == "proof":
            r["repetitions"][0]["modes"][0]["proof_seconds"] = 0
        elif name == "reuse":
            r["repetitions"][0]["modes"][0]["actual_queries"] += 1
        elif name == "cost":
            r["repetitions"][0]["modes"][0]["total_seconds"] += 1
        elif name == "exact":
            r["repetitions"][0]["modes"][0]["errors"][0]["objective_error"] = "1"
        elif name == "fault":
            r["faults"]["crashes"][0]["exit_code"] = 0
        else:
            r["toy"]["control"]["trajectory"] = []
        cases.append((name, r))
    for name, r in cases:
        try:
            check_report(r)
        except (ValueError, KeyError, AssertionError, TypeError, ValidationError):
            continue
        raise ValueError("evidence-mutation-was-accepted:" + name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    path = args.directory / "run.json"
    if path.is_symlink():
        raise ValueError("symlink-evidence-file")
    report = json.loads(path.read_text())
    check_report(report)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", report["source_commit"], "HEAD"],
        cwd=ROOT,
        check=True,
    )
    if args.mutations:
        mutation_checks(report)
    print(
        "Checked27 profiles, source/input pins, numerical bounds, four crashes and explicit limits."
    )


if __name__ == "__main__":
    main()
