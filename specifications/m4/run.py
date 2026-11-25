"""Execute tiny original synthetic references. Output is unapproved local evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from specifications.m4.reference import (
    AdmissionReference,
    certificate,
    check_certificate_structure,
    check_checkpoint,
    check_external,
    check_topology,
    checkpoint,
    context,
    digest,
    require,
    subgroup_counterexample,
    word,
)

ROOT = Path(__file__).resolve().parents[2]


def validate_observations(data: dict[str, Any]) -> None:
    rows = data["memory"]
    require(
        len(rows) == 9
        and {(row["n"], row["strategy"]) for row in rows}
        == {(n, mode) for n in (64, 256, 1024) for mode in ("ram", "recompute", "external-memory")},
        "memory-case-coverage",
    )
    for n in (64, 256, 1024):
        group = [row for row in rows if row["n"] == n]
        require(
            len({row["statement_sha256"] for row in group}) == 1
            and len({row["witness_sha256"] for row in group}) == 1,
            "memory-statement-conservation",
        )
    for row in rows:
        expected_io = row["n"] * 8 if row["strategy"] == "external-memory" else 0
        require(
            row["application_file_read_bytes"]
            == row["application_file_write_bytes"]
            == row["temporary_file_bytes_peak"]
            == expected_io,
            "reference-I/O-accounting",
        )
    require(
        len(data["queue"]) == 3 and {row["offered"] for row in data["queue"]} == {8, 32, 128},
        "queue-case-coverage",
    )
    for row in data["queue"]:
        require(
            row["peak_queue"] <= 4
            and row["peak_reserved_work"] <= 12
            and row["synthetic_acceptances"] + row["synthetic_rejections"] + row["backpressure"]
            == row["offered"],
            "queue-bound-or-count-conservation",
        )
    pair = data["subgroup_counterexample"]
    require(
        pair["global_left"]
        == pair["global_right"]
        == sum(pair["subgroups_left"])
        == sum(pair["subgroups_right"])
        and pair["subgroups_left"] != pair["subgroups_right"],
        "subgroup-counterexample-invalid",
    )


def memory_case(n: int, strategy: str) -> dict[str, Any]:
    if n not in (64, 256, 1024) or strategy not in ("ram", "recompute", "external-memory"):
        raise ValueError("bounded-reference-policy")
    tracemalloc.start()
    prepare_start = time.perf_counter()
    fixed = hashlib.sha256()
    for i in range(n):
        fixed.update(word(i))
    expected = fixed.hexdigest()
    statement = digest({"relation": "synthetic-witness-hash-v1", "n": n, "witness": expected})
    prepare_seconds = time.perf_counter() - prepare_start
    started = time.perf_counter()
    generated = read_bytes = written = storage_peak = 0
    result = ""
    if strategy == "ram":
        values = [word(i) for i in range(n)]
        generated = n
        result = hashlib.sha256(b"".join(values)).hexdigest()
    elif strategy == "recompute":
        for _ in range(2):
            h = hashlib.sha256()
            for i in range(n):
                h.update(word(i))
                generated += 1
            result = h.hexdigest()
            if result != expected:
                raise ValueError("recomputed-witness-changed")
    else:
        with tempfile.TemporaryFile() as witness:
            for i in range(n):
                written += witness.write(word(i))
                generated += 1
            witness.flush()
            storage_peak = witness.tell()
            witness.seek(0)
            h = hashlib.sha256()
            while block := witness.read(256):
                read_bytes += len(block)
                h.update(block)
            result = h.hexdigest()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if result != expected:
        raise ValueError("statement-witness-mismatch")
    return {
        "n": n,
        "strategy": strategy,
        "statement_sha256": statement,
        "witness_sha256": result,
        "prepare_seconds": prepare_seconds,
        "reference_compute_seconds": elapsed,
        "peak_python_allocated_bytes": peak,
        "prepare_generated_records": n,
        "compute_generated_records": generated,
        "application_file_read_bytes": read_bytes,
        "application_file_write_bytes": written,
        "temporary_file_bytes_peak": storage_peak,
        "peak_process_rss_bytes": None,
        "peak_vram_bytes": None,
        "prove_seconds": None,
        "verify_seconds": None,
        "proof_outcome": "not-run",
    }


def rejected(action: Any) -> bool:
    try:
        action()
    except ValueError:
        return True
    return False


def observations() -> dict[str, Any]:
    memory = [
        memory_case(n, strategy)
        for n in (64, 256, 1024)
        for strategy in ("ram", "recompute", "external-memory")
    ]
    bound = {
        "n": 64,
        "program": "synthetic-witness-hash-v1",
        "parameters": "fixture-v1",
        "transcript_position": 32,
        "witness": digest("fixed-witness"),
    }
    prefix = b"".join(word(i) for i in range(32))
    cp = checkpoint(bound, 1, 32, prefix)
    check_checkpoint(cp, bound, 1, 32, prefix)
    invalid_checkpoints = [
        rejected(lambda: check_checkpoint(cp, bound, 2, 32, prefix)),
        rejected(lambda: check_checkpoint(cp, dict(bound, program="changed"), 1, 32, prefix)),
        rejected(lambda: check_external(prefix[:-1], 32, hashlib.sha256(prefix).hexdigest())),
    ]
    loads = []
    for count in (8, 32, 128):
        queue = AdmissionReference()
        rejected_proofs = backpressure = 0
        for i in range(count):
            status = queue.submit(str(i), b"original-synthetic-proof-placeholder", 2)
            if status == "backpressure":
                backpressure += 1
            if i % 2:
                if job := queue.start():
                    valid = int(job[0]) % 3 != 0
                    queue.finish(*job, valid)
                    rejected_proofs += not valid
        while job := queue.start():
            valid = int(job[0]) % 3 != 0
            queue.finish(*job, valid)
            rejected_proofs += not valid
        loads.append(
            {
                "offered": count,
                "synthetic_acceptances": len(queue.accepted),
                "synthetic_rejections": rejected_proofs,
                "backpressure": backpressure,
                "peak_queue": queue.peak_queue,
                "peak_reserved_work": queue.peak_reserved,
                "latency_p50_seconds": None,
                "latency_p95_seconds": None,
                "latency_p99_seconds": None,
                "genuine_proofs_verified": 0,
            }
        )
    tree = certificate()
    composition = check_certificate_structure(tree, context())
    bad_trees = []
    for mutation in ("duplicate", "omit", "key", "parent", "sum", "availability", "order"):
        bad = copy.deepcopy(tree)
        leaf = bad["children"][0]["children"][0]
        if mutation == "duplicate":
            bad["children"][0]["children"][1] = copy.deepcopy(leaf)
        elif mutation == "omit":
            bad["children"][0]["children"].pop()
        elif mutation in ("key", "parent"):
            leaf["context"][mutation] = "wrong"
        elif mutation == "sum":
            bad["sum"] += 1
        elif mutation == "availability":
            leaf["available"] = False
        else:
            bad["children"].reverse()
        bad_trees.append(rejected(lambda bad=bad: check_certificate_structure(bad, context())))
    roster = [f"c{i}" for i in range(12)]
    groups = [roster[i : i + 4] for i in (0, 4, 8)]
    views = {f"relay{i}": ["routing-metadata", "opaque-payloads"] for i in range(3)}
    views["coordinator"] = ["global-release"]
    check_topology(groups, set(roster), views)
    hierarchy_bad = [
        rejected(lambda: check_topology(groups, set(roster[:-1]), views)),
        rejected(lambda: check_topology(groups, set(roster), dict(views, relay0=["subgroup-sum"]))),
        rejected(lambda: check_topology(groups, set(roster), views, 2)),
    ]
    if not all(invalid_checkpoints + bad_trees + hierarchy_bad):
        raise ValueError("negative-conformance-case-accepted")
    return {
        "memory": memory,
        "checkpoint_rejections": len(invalid_checkpoints),
        "queue": loads,
        "certificate": composition,
        "certificate_rejections": len(bad_trees),
        "hierarchy_rejections": len(hierarchy_bad),
        "subgroup_counterexample": subgroup_counterexample(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    contract_path = ROOT / "specifications/m4/contracts-v1.json"
    contract = json.loads(contract_path.read_text())
    data = {
        "schema_version": "m4-reference-1.0.0",
        "kind": "synthetic-reference-conformance",
        "source_commit": source,
        "source_dirty": dirty,
        "claim_ids": [],
        "issues": [76, 77, 78, 79],
        "contracts_sha256": hashlib.sha256(
            (ROOT / "specifications/m4/contracts-v1.json").read_bytes()
        ).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "source_version": contract["source_version"],
        "identities": {
            "relation": "synthetic-witness-and-integer-sum-v1",
            "context_sha256": digest(context()),
            "model": "not-applicable-no-training",
            "preprocessor": "none",
            "dataset": "original-synthetic-indexed-words-and-integer-contributions",
            "dataset_license": "Apache-2.0",
            "seed": 17,
        },
        "execution": {
            "kind": "local",
            "repetitions_per_case": 1,
            "reproduction_command": (
                "PYTHONPATH=.:src python -m specifications.m4.run --output OUTPUT.json"
            ),
            "jsonschema_version": importlib.metadata.version("jsonschema"),
            "dependency_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
            "uncertainty": "Not estimated from one reference trial per configuration.",
            "excluded_phases": [
                "genuine-setup",
                "genuine-witness",
                "prove",
                "verify",
                "ZK-finalization",
                "network",
                "RSS-VRAM",
            ],
        },
        "observer_model": (
            "Original public synthetic values; no protected transport or privacy guarantee."
        ),
        "publication_review": {"approved": False},
        "observations": observations(),
        "limitations": [
            "No genuine prover, recursion backend, protected transport or durable ledger.",
            "Python allocator peak is not RSS/VRAM. File bytes are application I/O, "
            "not physical disk traffic.",
            "Reference timings are diagnostics; no complete-prover or learning benchmark.",
            "Synthetic queue labels; genuine-proof throughput and latency are unmeasured.",
            "No ZK, DP, composition theorem, availability or book numerical claim.",
        ],
    }
    schema = json.loads((ROOT / "specifications/m4/report-schema-v1.json").read_text())
    Draft202012Validator(schema).validate(data)
    validate_observations(data["observations"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print("Reference checks passed; genuine proof and performance obligations remain pending.")


if __name__ == "__main__":
    main()
