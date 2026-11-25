#!/usr/bin/env python3
"""Bounded local pipeline/reference experiments; no private PSI or proof is fabricated."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict, replace
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from python.fzkml_math.data_experiment_contract import INPUT_PATHS, validate_config
from python.fzkml_math.data_lineage import (
    ORGS,
    Policy,
    Row,
    canonical,
    digest,
    partition,
    snapshot,
    synthetic_parts,
    verify_snapshot,
)
from python.fzkml_math.join_reference import JoinPolicy, authorized_join, binary_correspondence
from python.fzkml_math.streaming_data import Stream
from python.fzkml_math.summary_cache import (
    FeatureModel,
    SummaryCache,
    approximation_bound,
    break_even,
    cache_key,
    direct,
    evaluate,
    examples,
    stats,
)
from python.fzkml_math.toy_generation import control, copied_training_sample, denoise

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path: Path) -> tuple[tuple[F, F], ...]:
    raw = path.read_bytes()
    if len(raw) > 1_000_000:
        raise ValueError("bounded-synthetic-data-file")
    rows = json.loads(raw)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        raise ValueError("synthetic-row-array")
    result = tuple((F(x), F(y)) for x, y in rows)
    if any(abs(x) > 2 or abs(y) > 2 for x, y in result):
        raise ValueError("synthetic-domain")
    return result


def summary_profile(path: Path, n: int, queries: int, root: Path) -> dict[str, Any]:
    model = FeatureModel()
    thetas = [(F(i % 3 - 1, 2), F(i % 5 + 1, 4)) for i in range(queries)]
    baseline = []
    start = time.perf_counter()
    for theta in thetas:
        baseline.append(direct(read_rows(path), theta, model))
    full = time.perf_counter() - start
    dataset_id = digest("rational-source-file", json.loads(path.read_text()))
    pre = digest("preprocessor", {"op": "bounded-rational-identity", "version": 1})
    policy = digest(
        "summary-policy", {"objective": "mean", "lambda": "1", "data": "original-synthetic"}
    )
    schema = digest("schema", {"row": ["rational_x", "rational_y"], "bounds": "[-2,2]"})
    modes = []
    for name, grid in [("exact", None), ("approximate", F(1, 2))]:
        start = time.perf_counter()
        summary = stats(read_rows(path), model, grid)
        cache = SummaryCache(root / name)
        key = cache_key(dataset_id, model, pre, policy, schema)
        if grid is not None:
            key = digest("approximation-cache-key", {"base": key, "grid": str(grid)})
        cache.put(key, summary)
        setup = time.perf_counter() - start
        errors = []
        start = time.perf_counter()
        for theta, ref in zip(thetas, baseline, strict=True):
            result = evaluate(cache.get(key), theta, model)
            gap = abs(result["objective"] - ref["objective"])
            gradients = [
                abs(a - b) for a, b in zip(result["gradient"], ref["gradient"], strict=True)
            ]
            bound = approximation_bound(theta, model)
            if grid is None and result != ref:
                raise ValueError("exact-summary-is-not-full-data-equivalent")
            if gap > bound["objective"] or any(
                g > bound[f"gradient{i}"] for i, g in enumerate(gradients)
            ):
                raise ValueError("approximation-error-exceeds-declared-bound")
            errors.append(
                {
                    "theta": [str(x) for x in theta],
                    "objective_error": str(gap),
                    "gradient_error": [str(x) for x in gradients],
                    "objective_bound": str(bound["objective"]) if grid else "0",
                    "gradient_bounds": [str(bound[f"gradient{i}"]) for i in range(2)]
                    if grid
                    else ["0", "0"],
                }
            )
        online = time.perf_counter() - start
        size = (root / name / (key + ".json")).stat().st_size
        modes.append(
            {
                "mode": name,
                "status": "completed",
                "summary_setup_seconds": setup,
                "cached_query_seconds": online,
                "first_run_seconds": setup + online / queries,
                "total_seconds": setup + online,
                "reference_generation_seconds": full,
                "validated_comparison_total_seconds": full + setup + online,
                "break_even_scope": (
                    "trusted arithmetic-path estimate, not proof/trust-equivalent verification"
                ),
                "amortized_seconds_per_query": (setup + online) / queries,
                "actual_queries": queries,
                "actual_reuse_opportunities": queries - 1,
                "cache_builds": 1,
                "cache_reads": queries,
                "summary_dimension_scalars": 7,
                "serialized_summary_bytes": len(canonical(summary)),
                "cache_record_bytes": size,
                "application_bytes_read": path.stat().st_size + queries * size,
                "observed_reference_break_even_queries": break_even(
                    setup, full / queries, online / queries
                ),
                "cache_key": key,
                "errors": errors,
                "proof_seconds": None,
                "proof_break_even_queries": None,
                "proof_status": "not-run",
            }
        )
    return {
        "records": n,
        "queries": queries,
        "full_data_seconds": full,
        "full_data_application_bytes_read": queries * path.stat().st_size,
        "model_digest": digest("feature-model", model.descriptor),
        "preprocessor_digest": pre,
        "dataset_digest": dataset_id,
        "policy_digest": policy,
        "schema_digest": schema,
        "modes": modes,
        "scope": (
            "application-byte reads and local Fraction computation; "
            "page-cache/physical-disk effects not isolated"
        ),
    }


def make_event(
    r: Row, version: int = 1, previous: str | None = None, operation: str = "upsert"
) -> dict[str, Any]:
    return {
        "id": r.id,
        "version": version,
        "previous": previous,
        "operation": operation,
        "row": asdict(r),
        "arrival_time": 20,
    }


def stream_run(root: Path) -> dict[str, Any]:
    path = root / "state.sqlite"
    s = Stream(path, create=True)
    rows = [
        Row(f"synthetic:e{i}", f"synthetic:p{i}", ORGS[i], (2, 5, 4)[i], i + 1, 1, "cm", "train")
        for i in range(3)
    ]
    original = [make_event(r) for r in rows]
    h0 = s.ingest(original[0])
    h1 = s.ingest(original[1])
    retry = s.ingest(original[0])
    releases = []
    head = "genesis"
    start = time.perf_counter()
    for i, wm in enumerate((10, 10, 10, 12)):
        if i == 1:
            s.ingest(original[2], allow_closed_revision=True)
        if i == 2:
            s.ingest(make_event(replace(rows[0], value=4), 2, h0), allow_closed_revision=True)
        if i == 3:
            s.ingest(make_event(rows[1], 2, h1, "tombstone"), allow_closed_revision=True)
        result = s.advance(wm, expected_parent=head)
        head = result["snapshot"]
        rid = f"synthetic:release{i}"
        s.reserve(rid, head)
        result = s.recover_release(rid)
        releases.append(
            result
            | {
                "watermark_lag_synthetic_ticks": 20 - wm,
                "observer_event_count": s.status()["observer_ledger"]["events"],
            }
        )
    elapsed = time.perf_counter() - start
    before = s.status()
    s.close()
    s = Stream(path, expected_head=head)
    recovered = s.status()
    same = s.recover_release("synthetic:release0")
    s.close()
    if before != recovered or [r["sum_mm"] for r in releases] != [30, 60, 90, 70]:
        raise ValueError("stream-lineage-or-recovery-mismatch")
    return {
        "rounds": releases,
        "status_after_restart": recovered,
        "identical_redelivery": same
        == {
            k: v
            for k, v in releases[0].items()
            if k not in ("watermark_lag_synthetic_ticks", "observer_event_count")
        },
        "duplicate_transport_result": retry,
        "correction_delay_synthetic_ticks": 18,
        "compute_commit_and_accounting_seconds": elapsed,
        "release_slots_are_not_DP_budget": True,
        "DP_guarantee": False,
    }


def fault_run(root: Path) -> dict[str, Any]:
    root.mkdir()
    p = root / "fault.sqlite"
    s = Stream(p, create=True)
    s.close()
    row = Row("synthetic:crash-event", "synthetic:p0", ORGS[0], 2, 1, 1, "cm", "train")
    ev = make_event(row)
    child = """import json,os,sys
from pathlib import Path
from python.fzkml_math.streaming_data import Stream
s=Stream(Path(sys.argv[1]));e=json.loads(sys.argv[3]);case=sys.argv[2]
if case=='before':s.ingest(e,fault=lambda:os._exit(91))
elif case=='after':s.ingest(e,after_commit=lambda:os._exit(92))
elif case=='advance':s.advance(10,expected_parent='genesis',fault=lambda:os._exit(94))
else:s.recover_release('synthetic:crash-release',fault_after_journal=lambda:os._exit(93))
"""

    def crash(case: str, expected: int) -> dict[str, Any]:
        start = time.perf_counter()
        r = subprocess.run(
            [sys.executable, "-c", child, str(p), case, json.dumps(ev)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": ".:src"},
            timeout=10,
        )
        if r.returncode != expected:
            raise ValueError("unexpected-fault-process-outcome")
        return {
            "fault": case,
            "exit_code": r.returncode,
            "expected_exit_code": expected,
            "seconds": time.perf_counter() - start,
        }

    crashes = [crash("before", 91)]
    s = Stream(p)
    before = s.status()
    s.close()
    if before["accepted_event_versions"] != 0:
        raise ValueError("precommit-crash-leaked-accepted-effect")
    crashes.append(crash("after", 92))
    s = Stream(p)
    after = s.status()
    s.close()
    if after["accepted_event_versions"] != 1:
        raise ValueError("committed-effect-lost")
    crashes.append(crash("advance", 94))
    s = Stream(p)
    rolled = s.status()
    if rolled["head"] != "genesis" or rolled["round"] != 0:
        raise ValueError("partial-snapshot-committed")
    state = s.advance(10, expected_parent="genesis")
    s.reserve("synthetic:crash-release", state["snapshot"])
    s.close()
    crashes.append(crash("ledger", 93))
    s = Stream(p)
    pending = s.status()
    result = s.recover_release("synthetic:crash-release")
    final = s.status()
    s.close()
    if (
        pending["accounted_release_count"] != 0
        or pending["observer_ledger"]["events"] != 1
        or final["accounted_release_count"] != 1
        or final["observer_ledger"]["events"] != 1
        or result != state
    ):
        raise ValueError("outbox-recovery-duplicated-or-lost-disclosure")
    return {
        "crashes": crashes,
        "precommit_state": before,
        "postcommit_state": after,
        "advance_rolled_back": rolled,
        "after_journal_before_SQL_accounting": pending,
        "recovered": final,
        "scope": (
            "actual local process termination; no power-loss, malicious-storage or Byzantine test"
        ),
    }


def negative_findings(root: Path) -> dict[str, Any]:
    model = FeatureModel()
    rows = ((F(1), F(-1)),)
    summary = stats(rows, model)
    key = cache_key("synthetic-snapshot", model, "pre-1", "policy-1", "schema-1")
    cache = SummaryCache(root)
    cache.put(key, summary)
    path = root / (key + ".json")
    record = json.loads(path.read_text())
    record["payload"]["t0"] = "999"
    record["payload_digest"] = digest("cache-payload", record["payload"])
    path.write_bytes(canonical(record))
    forged = cache.get(key)
    changed = evaluate(forged, (F(0), F(0)), model) != direct(rows, (F(0), F(0)), model)
    original = Row("synthetic:hash-guess", "synthetic:p0", ORGS[0], 1, 3, 1, "cm", "train")
    root_digest = partition((original,), ORGS[0])["digest"]
    guesses = [
        v
        for v in range(-4, 5)
        if partition((replace(original, value=v),), ORGS[0])["digest"] == root_digest
    ]
    p = JoinPolicy()
    base = tuple(
        replace(original, id=f"synthetic:alias-{i}-{j}", org=o, value=1)
        for i, o in enumerate(ORGS)
        for j in range((2, 1, 1)[i])
    )
    aliases = base + tuple(replace(r, id=r.id + "other", entity="synthetic:p1") for r in base)
    without = authorized_join(aliases, p, recipient=p.recipient, purpose=p.purpose)
    mapped = replace(
        p, entity_map=(("synthetic:p0", "synthetic:p0"), ("synthetic:p1", "synthetic:p0"))
    )
    with_map = authorized_join(aliases, mapped, recipient=p.recipient, purpose=p.purpose)
    return {
        "alias_without_canonical_map": without["public_output"]["value"],
        "alias_with_fixed_canonical_map": with_map["public_output"]["value"],
        "hash_dictionary_matches": guesses,
        "self_consistent_cache_checksum_accepts_wrong_derivation": changed,
        "single_record_statistic_T0_reconstructs_label": str(F(summary["t0"])),
        "scope": (
            "Original synthetic negative cases. Hash/checksum integrity is not "
            "hiding or a correctness proof."
        ),
    }


def hardware() -> dict[str, Any]:
    cpu = platform.processor() or None
    status = "observed" if cpu else "unavailable"
    if platform.system() == "Darwin":
        probe = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=3
        )
        cpu = probe.stdout.strip() if probe.returncode == 0 else None
        status = "observed" if cpu else "unavailable-in-execution-environment"
    return {
        "os": platform.system(),
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "GPU": "not-used",
        "cpu_model": cpu,
        "cpu_probe_status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-real-proof", action="store_true")
    args = parser.parse_args()
    if args.require_real_proof:
        raise ValueError("matching-data-summary-proof-backend-unavailable")
    out = args.output.resolve()
    if out.exists():
        raise ValueError("fresh-output-directory-required")
    out.mkdir(parents=True)
    config = json.loads((ROOT / "experiments/s02-data/config-v1.json").read_text())
    validate_config(config)
    if (
        config["summary"]["records"] != [64, 256, 1024]
        or config["summary"]["queries"] != [1, 4, 8]
        or config["repetitions"] != 3
    ):
        raise ValueError("bounded-experiment-config")
    report: dict[str, Any] = {
        "schema_version": "s02-data-run-1.0.0",
        "kind": "local-synthetic-reference-companion",
        "status": "running",
        "planning_issue_claim_ids": config["planning_issue_claim_ids"],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "source_approval": (
            "contribution certification tracked in PR; no independent scientific/security approval"
        ),
        "hardware": hardware(),
        "software": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version},
        "provenance": config["provenance"],
        "digests": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in INPUT_PATHS
        },
        "observer_model": {
            "join_operator": (
                "trusted plaintext reference sees all identifiers/rows; not cryptographic PSI"
            ),
            "authorized_join_recipient": (
                "declared aggregate/context only; no diagnostic identifiers"
            ),
            "statistics_recipient": "clean synthetic moments can reveal labels; no DP",
            "stream": (
                "exact synthetic releases explicitly unprotected; durable observer journal reused"
            ),
            "toy": (
                "all simulated states/actions/rewards/noise tapes visible; no "
                "adaptive transcript privacy"
            ),
            "source_truth": (
                "content identity and declared metadata only; rights, real "
                "identity, timestamp/environment truth not authenticated"
            ),
        },
        "snapshot": {},
        "join": {},
        "stream": {},
        "faults": {},
        "toy": {},
        "fixture_setup": [],
        "repetitions": [],
        "proof_amortization": config["proof_amortization"],
        "negative_findings": {},
        "failures": [],
        "limitations": [
            (
                "No private join, production DP mechanism, full "
                "training/inference proof, real-world control or family safety "
                "claim."
            ),
            (
                "SQLite/journal/cache/authority/clock are trusted local "
                "components; no joint malicious rollback resistance."
            ),
            "Content hashes and sufficient statistics can leak; neither is a hiding/DP mechanism.",
            (
                "Approximation bounds concern the declared bounded quadratic; no"
                " general utility or privacy guarantee."
            ),
            (
                "Timings/application byte counts are diagnostic on this host; no"
                " physical-disk isolation or significance claim."
            ),
            (
                "Existing fixed-shape ridge proof does not match this data/cache"
                " pipeline; proof amortization not-run."
            ),
            (
                "Source-inspected numeric facts remain candidates with "
                "authoritative edition migration/review pending."
            ),
        ],
        "reproduction_command": (
            "PYTHONPATH=.:src .venv/bin/python scripts/run_s02_data.py .tools/fresh-data-run"
        ),
    }
    validator = Draft202012Validator(
        json.loads((ROOT / "schemas/s02-data-run-1.0.0.json").read_text())
    )

    def retain() -> None:
        validator.validate(report)
        (out / "run.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    retain()
    try:
        report["negative_findings"] = negative_findings(out / "negative-cache")
        start = time.perf_counter()
        parts = synthetic_parts()
        policy = Policy()
        state = snapshot(parts, policy)
        report["snapshot"] = {
            "identity": state["identity"],
            "manifest": state["manifest"],
            "accepted_rows": len(state["rows"]),
            "verification": verify_snapshot(state, parts, policy),
            "complete_relative_to_synthetic_fixture_inventory": verify_snapshot(
                state, parts, policy, {p["organization"]: p["digest"] for p in parts}
            ),
            "preprocessing_seconds": time.perf_counter() - start,
            "proof_seconds": None,
            "schema_digest": state["manifest"]["schema_digest"],
            "preprocessor_digest": state["manifest"]["preprocessing_digest"],
        }
        duplicate = tuple(
            replace(
                Row("synthetic:j", "synthetic:p0", org, 2, 1, 1, "cm", "train"),
                id=f"synthetic:j{i}-{j}",
            )
            for i, org in enumerate(ORGS)
            for j in range((2, 3, 1)[i])
        )
        jp = JoinPolicy()
        worlds = binary_correspondence()
        report["join"] = {
            "public": authorized_join(duplicate, jp, recipient=jp.recipient, purpose=jp.purpose),
            "privileged_synthetic_only": authorized_join(
                duplicate, jp, recipient="synthetic:trusted-operator", purpose=jp.purpose
            ),
            "entity_add_remove_sensitivity": str(jp.sensitivity("add-remove-entity")),
            "entity_replace_sensitivity": str(jp.sensitivity("replace-entity")),
            "missing_correspondence": {
                "same_marginals": worlds["same_marginals"],
                "equal_joint": [[*key, str(p)] for key, p in worlds["equal"].items()],
                "opposite_joint": [[*key, str(p)] for key, p in worlds["opposite"].items()],
            },
            "crypto_PSI_status": "not-implemented",
            "DP_guarantee": False,
        }
        stream_dir = out / "stream"
        stream_dir.mkdir()
        report["stream"] = stream_run(stream_dir)
        report["faults"] = fault_run(out / "faults")
        retain()
        start = time.perf_counter()
        exact = denoise()
        quant = denoise(scale=16)
        trajectory = control()
        report["toy"] = {
            "exact_denoising": exact,
            "quantized_denoising": quant,
            "control": trajectory,
            "full_path_seconds": time.perf_counter() - start,
            "initial_zero_target_mse": "5/8",
            "untrained_predictor_worsens_metric": F(exact["zero_target_mse"]) > F(5, 8),
            "copied_training_sample_negative": copied_training_sample((1, 2), ((1, 2), (0, 0))),
            "model_family_feasibility": "not-established",
            "safety": "not-established",
        }
        for rep in range(3):
            for n in config["summary"]["records"]:
                start = time.perf_counter()
                rows = examples(n)
                file = out / f"rows-{rep}-{n}.json"
                file.write_bytes(canonical([[str(x), str(y)] for x, y in rows]))
                report["fixture_setup"].append(
                    {
                        "repetition": rep,
                        "records": n,
                        "generation_and_serialization_seconds": time.perf_counter() - start,
                        "actual_profile_reuses": 3,
                        "unique_synthetic_pairs": len(set(rows)),
                        "repeated_rows": n - len(set(rows)),
                        "scope": (
                            "common public-fixture setup, recorded once, not a cryptographic"
                            " preprocessing cache"
                        ),
                    }
                )
                for q in config["summary"]["queries"]:
                    result = summary_profile(file, n, q, out / f"cache-{rep}-{n}-{q}")
                    result.update(repetition=rep, excluded=False, status="completed")
                    report["repetitions"].append(result)
                    retain()
        report["status"] = "completed"
        retain()
    except BaseException as error:
        report["status"] = "failed"
        report["failures"].append({"error_type": type(error).__name__, "excluded": False})
        retain()
        raise
    print(
        "S02 data run retained:27 raw profiles; exact summaries match; "
        "proof amortization not-run; outputs not DP."
    )


if __name__ == "__main__":
    main()
