"""Bounded synthetic CI evidence gates. No private data or external services."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import os
import platform
import random
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from jsonschema import Draft202012Validator

from .benchmark import compare
from .validate import MAX_FILE, ROOT, Invalid, bounded_file, load, public_tree, require

FIXTURE = ROOT / "ci/fixtures/evidence-gates-v1.json"
SCHEMA = ROOT / "specs/ci/evidence-run-v1.schema.json"
DOC = dict[str, Any]
WINDOW = 5


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def benchmark_row(config: DOC, side: int) -> DOC:
    result: DOC = load(ROOT / "examples/results.json")["results"][0]
    result["outcome"] = {"status": "successful", "reason": "Synthetic timing fixture."}
    result["scenario"].update(
        statement="ci-fixture:one-exact-step",
        relation_version="fzknum-1.0.0",
        numerical_semantics="fixed16-RNE",
        backend=f"synthetic-cpu-{side}",
    )
    result["provenance"].update(
        source_commit="1" * 40, workflow_run=1, dependency_digest="sha256:" + "1" * 64
    )
    result["metrics"] = []
    result["benchmark"] = {
        "workload_digest": "sha256:" + sha(canonical(config["schedule"])),
        "warmups": 1,
        "setup_amortization": "none",
        "cached_work": "none",
        "quality_threshold": "all synthetic checks pass",
        "phases": {
            phase: "measured" if phase == "total" else "unavailable"
            for phase in ("setup", "witness", "prove", "aggregate", "verify", "transfer", "total")
        },
        "resources": dict.fromkeys(
            ("peak_memory", "proof_bytes", "communication"),
            "unavailable: synthetic timings",
        ),
    }
    result["repetitions"] = [
        {
            "id": rid,
            "attempt": 1,
            "status": "successful",
            "timeout": False,
            "excluded": idx == 0,
            "reason": "declared warm-up" if idx == 0 else "fixture",
            "quality": "pass",
            "measurements": [{"phase": "total", "quantity": "time", "unit": "s", "value": seconds}],
        }
        for idx, (rid, seconds) in enumerate(
            zip(config["schedule"], config["seconds"][side], strict=True)
        )
    ]
    return result


def matched_benchmark(left: DOC, right: DOC, expected_ids: list[str]) -> DOC:
    require(len(expected_ids) == len(set(expected_ids)) <= 16, "invalid-benchmark-plan")
    for row in (left, right):
        reps = row["repetitions"]
        if [r["id"] for r in reps] != expected_ids or any(r["attempt"] != 1 for r in reps):
            return {"status": "inconclusive", "reason": "raw-attempt-ledger-incomplete"}
        warmups = row["benchmark"]["warmups"]
        if any(r["excluded"] != (idx < warmups) for idx, r in enumerate(reps)):
            return {"status": "inconclusive", "reason": "undeclared-exclusion"}
        if any(r["status"] != "successful" or r["timeout"] or r["quality"] != "pass" for r in reps):
            return {"status": "inconclusive", "reason": "failed-or-censored-attempt"}
    try:
        return compare(left, right)
    except Invalid as error:
        code = str(error)
        return {
            "status": "unmatched" if code.startswith("unmatched-") else "inconclusive",
            "reason": code,
        }


def bounded_wh(value: int, unit: str) -> int:
    require(type(value) is int and 0 <= value <= 10_000, "energy-range")
    require(unit in {"Wh", "kWh"}, "unknown-energy-unit")
    wh = value * (1000 if unit == "kWh" else 1)
    require(wh <= 100_000, "energy-range")
    return wh


class Lineage:
    """Deterministic single-process reference. A release binds an ordered parent."""

    def __init__(self, config: DOC) -> None:
        rows = config["rows"]
        require(0 < len(rows) <= 16, "snapshot-size")
        require(sha(canonical(rows).rstrip(b"\n")) == config["source_sha256"], "source-digest")
        self.watermark: int = config["watermark"]
        self.horizon: int = config["correction_horizon"]
        require(self.watermark == WINDOW and 0 <= self.horizon <= WINDOW, "watermark-policy")
        self.rows: dict[str, DOC] = {}
        for row in rows:
            require(row["id"] not in self.rows and 0 <= row["t"] < self.watermark, "snapshot-row")
            self.rows[row["id"]] = {
                "entity": row["entity"],
                "t": row["t"],
                "unit": row["unit"],
                "wh": bounded_wh(row["value"], row["unit"]),
                "revision": 0,
            }
        self.source: str = config["source_sha256"]
        self.events: list[str] = []
        self.tip: str = "0" * 64
        self.releases: set[str] = set()
        self.last_state: str | None = None

    def state(self) -> str:
        return sha(
            canonical(
                {
                    "schema": "energy-wh-v1",
                    "source": self.source,
                    "rows": self.rows,
                    "watermark": self.watermark,
                    "horizon": self.horizon,
                    "events": self.events,
                }
            )
        )

    def apply(self, event: DOC) -> None:
        require(event["id"] not in self.events and len(self.events) < 16, "duplicate-or-full-event")
        row = self.rows.get(event["row_id"])
        require(row is not None, "unknown-correction-row")
        assert row is not None
        require(event["t"] == row["t"], "event-time-shift")
        require(self.watermark - self.horizon <= event["t"] < self.watermark, "late-horizon")
        require(event["revision"] == row["revision"] + 1, "revision-order")
        require(event["unit"] == row["unit"], "declared-unit-shift")
        wh = bounded_wh(event["value"], event["unit"])
        row.update(wh=wh, revision=event["revision"])
        self.events.append(event["id"])

    def release(self, rid: str, parent: str, expected_state: str) -> str:
        require(rid not in self.releases and len(self.releases) < 16, "duplicate-or-full-release")
        require(parent == self.tip and expected_state == self.state(), "release-parent-or-state")
        require(expected_state != self.last_state, "already-released-state")
        self.tip = sha(canonical([rid, parent, expected_state]))
        self.releases.add(rid)
        self.last_state = expected_state
        return self.tip


def release_gate(config: DOC, approved: set[str]) -> None:
    public_tree(config["candidate"])
    require(config["publication_approved"] is True, "release-approval-missing")
    assets = config["assets"]
    require(
        sorted(record["id"] for record in assets) == ["checkpoint", "dataset"], "release-inventory"
    )
    for record in assets:
        require(record["license"] in approved, "unknown-asset-license")
        require(record["redistributable"] is True, "restricted-asset")
        require(sha(record["payload"].encode()) == record["sha256"], "asset-checksum")
    train = config["train_ids"]
    evaluation = config["eval_ids"]
    require(
        len(train) == len(set(train)) and len(evaluation) == len(set(evaluation)),
        "duplicate-entity",
    )
    require(not set(train) & set(evaluation), "entity-split-overlap")
    require(bool(config["canary"]), "missing-canary")
    require(
        config["canary"].casefold() not in config["candidate"].casefold(),
        "synthetic-canary-in-output",
    )


def strength_gate(claim: DOC, linked: list[DOC]) -> None:
    kinds = {entry["kind"] for entry in linked}
    if claim["kind"] in {"assumption-theorem", "cryptographic-security"} and (
        claim["status"] in {"implemented", "tested", "replicated", "reviewed"}
        or claim["evidence_class"] == "formal"
    ):
        formal = {entry["evidence_id"] for entry in linked if entry["kind"] == "formal-proof"}
        ids = set(claim["formal_proof"]["artifact_ids"])
        require(bool(ids) and ids <= formal, "theorem-without-formal-evidence")
    if claim["status"] == "reviewed":
        require(
            "independent-review" in kinds and bool(claim["independent_review"]["artifact_ids"]),
            "review-without-attestation",
        )


def source_file_status(path: str, expected: str) -> str:
    path = path.split("::", 1)[0]
    candidate = ROOT / path
    if not candidate.resolve().is_relative_to(ROOT) or ".." in Path(path).parts:
        return "unsafe-path"
    if not candidate.exists() or any(
        (ROOT / p).is_symlink() for p in [Path(path), *Path(path).parents]
    ):
        return "unavailable"
    try:
        return "available" if sha(bounded_file(candidate)) == expected else "digest-mismatch"
    except (OSError, Invalid):
        return "unavailable"


def claim_portal(registry: DOC, trace: DOC, source: DOC) -> list[DOC]:
    records = {r["claim_id"]: r for r in trace["records"]}
    attestations = {r["evidence_id"]: r for r in trace["evidence"]}
    source_nodes = {node["id"]: node for node in source["nodes"]}
    rows = []
    for claim in sorted(registry["claims"], key=lambda c: c["id"]):
        record = records[claim["id"]]
        linked = [attestations[eid] for eid in record["evidence_ids"] if eid in attestations]
        strength_gate(claim, linked)
        evidence = []
        for eid in record["evidence_ids"]:
            if eid not in attestations:
                evidence.append({"id": eid, "availability": "unavailable"})
                continue
            entry = attestations[eid]
            evidence.append(
                {
                    "id": eid,
                    "kind": entry["kind"],
                    "scope": entry["scope"],
                    "path": entry["path"],
                    "availability": source_file_status(entry["path"], entry["sha256"]),
                    "tested_commit": entry["source_commit"],
                    "execution": entry["execution"],
                    "review": entry["review"],
                }
            )
        rows.append(
            {
                "id": claim["id"],
                "status": claim["status"],
                "class": claim["evidence_class"],
                "source": claim["source"],
                "statement": claim["statement"],
                "sources": [
                    {
                        "id": sid,
                        "extraction": source_nodes[sid]["extraction_status"],
                        "inspection": source_nodes[sid]["inspection_status"],
                    }
                    if sid in source_nodes
                    else {"id": sid, "extraction": "unavailable"}
                    for sid in record["source_refs"]
                ],
                "evidence": evidence,
                "required_reviews": record["required_reviews"],
                "limitations": claim["limitations"],
            }
        )
    public_tree(rows)
    return rows


def render_portal(rows: list[DOC], commit: str, gates: list[DOC]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    parts = [
        '<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>FZKML evidence portal</title>",
        "<h1>FZKML evidence portal</h1>",
        f"<p>Source commit {esc(commit)}. Candidate preview.</p>",
        "<h2>Synthetic gate outcomes</h2><ul>",
    ]
    for gate in gates:
        parts.append(f"<li>#{esc(gate['issue'])} {esc(gate['observed'])}: {esc(gate['id'])}</li>")
    parts.append("</ul><h2>Manuscript claim coverage</h2>")
    for row in rows:
        parts.append(
            f"<article><h3>{esc(row['id'])}</h3><p>{esc(row['status'])} · {esc(row['class'])}</p>"
        )
        parts.append(f"<p>{esc(row['statement'])}</p>")
        parts.append("<ul>")
        for source in row["sources"]:
            parts.append(f"<li>{esc(source['id'])}: {esc(source['extraction'])}</li>")
        for entry in row["evidence"]:
            parts.append(f"<li>{esc(json.dumps(entry, sort_keys=True))}</li>")
        for detail in row["limitations"] + row["required_reviews"]:
            parts.append(f"<li>{esc(detail)}</li>")
        parts.append("</ul></article>")
    return "\n".join(parts + ["</html>", ""])


def rne(n: int, d: int) -> int:
    return round(Fraction(n, d))


def numeric_trace(seed: int, config: DOC, bad: bool = False) -> tuple[bytes, list[int], int]:
    import struct

    rng = random.Random(seed)
    xs = config["x"]
    ys = [rng.choice([8, 12, 16]) * (1 if x > 0 else -1) for x in xs]
    if bad:
        ys[-1] = 32
    w = config["initial_w"]
    counts = config["counts"]
    batch = b"FZKNUM01" + struct.pack("<HHIq", 1, 3, 16, w)
    local = []
    for x, y, count in zip(xs, ys, counts, strict=True):
        batch += struct.pack("<qqI", x, y, count)
        p = rne(w * x, 16)
        local.append(w - rne(rne((p - y) * x, 16), 4))
    return batch, local, rne(sum(n * v for n, v in zip(counts, local, strict=True)), sum(counts))


def outcome_pilot(config: DOC, binary: Path) -> DOC:
    seeds = config["seeds"]
    require(len(seeds) == len(set(seeds)) == 3, "duplicate-or-unplanned-seed")
    heldout = config["heldout"]
    require(
        len(heldout) == len({row["id"] for row in heldout}) == 4
        and all(row["id"].startswith("ev") for row in heldout)
        and sorted(row["group"] for row in heldout) == ["A", "A", "B", "B"],
        "matched-holdout",
    )

    def quality(w: int) -> DOC:
        return {
            group: {
                "absolute_error": sum(
                    abs(rne(w * r["x"], 16) - r["y"]) for r in heldout if r["group"] == group
                ),
                "count": sum(r["group"] == group for r in heldout),
            }
            for group in ("A", "B")
        }

    attempts = []
    for seed in seeds:
        batch, local, ordinary = numeric_trace(seed, config)
        require(numeric_trace(seed, config) == (batch, local, ordinary), "seed-replay-drift")
        started = perf_counter_ns()
        try:
            evaluated = subprocess.run(
                [str(binary), "evaluate"],
                input=batch.hex(),
                text=True,
                capture_output=True,
                timeout=15,
                check=True,
            )
            require(evaluated.stdout.strip() == str(ordinary), "native-reference-disagreement")
            native_ns = perf_counter_ns() - started
            proof_started = perf_counter_ns()
            proved = subprocess.run(
                [str(binary), "smoke"],
                input=batch.hex(),
                text=True,
                capture_output=True,
                timeout=25,
                check=True,
            )
            require(proved.stdout.strip() == "true", "proof-verifier-rejected")
            proof_ns = perf_counter_ns() - proof_started
        except subprocess.TimeoutExpired as error:
            raise Invalid("outcome-native-or-proof-timeout") from error
        except (OSError, subprocess.CalledProcessError) as error:
            raise Invalid("outcome-native-or-proof-failed") from error
        attempts.append(
            {
                "seed": seed,
                "status": "completed",
                "input_sha256": sha(batch),
                "native_wall_ns": native_ns,
                "public_proof_setup_prove_verify_wall_ns": proof_ns,
                "local_only": quality(local[0]),
                "ordinary_federated": quality(ordinary),
                "transparent_proof_backed": quality(ordinary),
                "protected_federated": {
                    "status": "unsupported",
                    "reason": "no matched protected full-state relation",
                },
                "protected_plus_proof": {
                    "status": "unsupported",
                    "reason": "no matched protected full-state relation",
                },
                "bad_data": quality(numeric_trace(seed, config, bad=True)[2]),
            }
        )
    simulated = [
        {
            "seed": a["seed"],
            "status": "timed-out" if a["seed"] == config["timeout_seed"] else "completed",
        }
        for a in attempts
    ]
    selected = [a for a in attempts if a["seed"] != config["timeout_seed"]]
    require(0 < len(selected) < len(attempts), "invalid-selection-fixture")

    def mae(rows: list[DOC]) -> str:
        group = [row["ordinary_federated"]["B"] for row in rows]
        return str(
            Fraction(sum(r["absolute_error"] for r in group), sum(r["count"] for r in group))
        )

    require(mae(attempts) != mae(selected), "selection-fixture-no-subgroup-bias")
    return {
        "subgroup_b_full_mae": mae(attempts),
        "subgroup_b_survivor_mae": mae(selected),
        "attempts": attempts,
        "selection_mutant": simulated,
        "selection_status": complete_arm(simulated, seeds),
        "quality_threshold": "all reference/native checks agree",
        "budget": {"native_timeout_seconds": 15, "proof_timeout_seconds": 25, "seeds": 3},
    }


def complete_arm(attempts: list[DOC], seeds: list[int]) -> str:
    if [row["seed"] for row in attempts] != seeds or any(
        r["status"] != "completed" for r in attempts
    ):
        return "inconclusive"
    return "comparable"


def write_outputs(directory: Path, report: DOC, page: str) -> None:
    public_tree(report)
    require(
        len(canonical(report)) <= MAX_FILE and len(page.encode()) <= MAX_FILE,
        "evidence-output-size",
    )
    directory.mkdir()
    for name, body in (("evidence.json", canonical(report)), ("portal.html", page.encode())):
        with (directory / name).open("xb") as stream:
            stream.write(body)


def validate_report(report: DOC) -> None:
    public_tree(report)
    require(Draft202012Validator(load(SCHEMA)).is_valid(report), "evidence-schema")
    rows = report["gates"]
    require(len({row["id"] for row in rows}) == len(rows), "duplicate-gate")
    require({row["issue"] for row in rows} == {116, 117, 118, 119, 120}, "issue-coverage")
    require(all(row["expected"] == row["observed"] for row in rows), "unexpected-gate-outcome")


def build(binary: Path, mutation: str | None = None) -> tuple[DOC, str]:
    fixture: DOC = load(FIXTURE)
    require(fixture["version"] == "ci-evidence-fixture-v1", "unknown-fixture")
    gates: list[DOC] = []

    def gate(issue: int, case: str, expected: str, observed: str, raw: Any) -> None:
        require(observed == expected, f"{case}: expected {expected}, observed {observed}")
        gates.append(
            {"issue": issue, "id": case, "expected": expected, "observed": observed, "raw": raw}
        )

    def reject(issue: int, case: str, code: str, check: Any) -> None:
        try:
            check()
        except Invalid as error:
            require(str(error) == code, f"{case}: unexpected rejection")
            gate(issue, case, "rejected", "rejected", {"reason": code})
        else:
            raise Invalid(f"{case}: unexpected acceptance")

    bench = fixture["benchmark"]
    ids = bench["schedule"]
    left, right = benchmark_row(bench, 0), benchmark_row(bench, 1)
    unequal = copy.deepcopy(right)
    unequal["scenario"]["statement"] = "ci-fixture:inference-only"
    diagnostic = matched_benchmark(left, unequal if mutation == "benchmark-scope" else right, ids)
    gate(
        116,
        "matched-benchmark",
        "diagnostic",
        diagnostic["status"],
        {
            "raw_arms": [left["repetitions"], right["repetitions"]],
            "policy": left["benchmark"],
            "hardware": left["provenance"]["hardware"],
            "result": diagnostic,
        },
    )
    comparison = matched_benchmark(left, unequal, ids)
    gate(116, "unequal-relation", "unmatched", comparison["status"], comparison)
    no_attempt = copy.deepcopy(right)
    dropped = no_attempt["repetitions"].pop()
    comparison = matched_benchmark(left, no_attempt, ids)
    gate(
        116,
        "survivor-only",
        "inconclusive",
        comparison["status"],
        {
            "result": comparison,
            "missing_attempt": dropped["id"],
            "visible_attempts": no_attempt["repetitions"],
        },
    )
    censor = copy.deepcopy(right)
    censor["repetitions"][-1].update(
        status="failed", timeout=True, quality="unknown", measurements=[]
    )
    comparison = matched_benchmark(left, censor, ids)
    gate(
        116,
        "recorded-timeout",
        "inconclusive",
        comparison["status"],
        {"result": comparison, "raw_attempts": censor["repetitions"]},
    )
    warm = copy.deepcopy(right)
    warm["repetitions"][-1]["excluded"] = True
    comparison = matched_benchmark(left, warm, ids)
    gate(116, "hidden-setup-or-warmup", "inconclusive", comparison["status"], comparison)

    data = fixture["lineage"]
    stream = Lineage(data)
    first, second = data["events"]
    stream.apply(first)
    state_a = stream.state()
    parent = stream.release("release-0", stream.tip, state_a)
    require(
        [r["wh"] for r in stream.rows.values()] == data["expected_after_first"],
        "first-lineage-output",
    )
    reject(117, "replayed-event", "duplicate-or-full-event", lambda: stream.apply(first))
    reject(117, "wrong-unit", "declared-unit-shift", lambda: stream.apply(dict(second, unit="kWh")))
    reject(
        117,
        "double-release",
        "already-released-state",
        lambda: stream.release("release-1", parent, state_a),
    )
    reject(
        117,
        "late-outside-window",
        "late-horizon",
        lambda: stream.apply(
            {
                "id": "too-late",
                "row_id": "r0",
                "revision": 1,
                "t": 2,
                "value": 1,
                "unit": "kWh",
            }
        ),
    )
    stream.apply(second)
    state_b = stream.state()
    reject(
        117,
        "stale-parent",
        "release-parent-or-state",
        lambda: stream.release("release-1", "0" * 64, state_b),
    )
    child = stream.release("release-1", parent, state_b)
    require(
        [r["wh"] for r in stream.rows.values()] == data["expected_after_second"],
        "second-lineage-output",
    )
    gate(
        117,
        "ordered-late-correction",
        "completed",
        "completed",
        {
            "snapshot_sha256": data["source_sha256"],
            "watermark": stream.watermark,
            "state_sha256": [state_a, state_b],
            "release_ids": [parent, child],
            "applied_event_ids": stream.events,
            "normalized_wh": [r["wh"] for r in stream.rows.values()],
        },
    )
    tampered = copy.deepcopy(data)
    tampered["rows"][0]["value"] += 1
    reject(117, "changed-snapshot", "source-digest", lambda: Lineage(tampered))

    release = fixture["release"]
    licenses = set(load(ROOT / "compliance/files.json")["approved_licenses"])
    release_gate(release, licenses)
    gate(
        118,
        "cleared-synthetic-candidate",
        "completed",
        "completed",
        {
            "asset_digests": [a["sha256"] for a in release["assets"]],
            "train_count": len(release["train_ids"]),
            "eval_count": len(release["eval_ids"]),
        },
    )
    reject(
        118,
        "absent-release-approval",
        "release-approval-missing",
        lambda: release_gate(dict(release, publication_approved=False), licenses),
    )
    for case, field, value, code in [
        ("unknown-model-license", "license", "Unknown-Fixture-License", "unknown-asset-license"),
        ("restricted-checkpoint", "redistributable", False, "restricted-asset"),
        ("changed-checkpoint", "payload", "mutated checkpoint", "asset-checksum"),
    ]:
        altered = copy.deepcopy(release)
        checkpoint = next(a for a in altered["assets"] if a["id"] == "checkpoint")
        checkpoint[field] = value
        reject(118, case, code, lambda cfg=altered: release_gate(cfg, licenses))
    reject(
        118,
        "memorized-canary",
        "synthetic-canary-in-output",
        lambda: release_gate(
            dict(release, candidate=f"synthetic leaked token {release['canary'].upper()}"),
            licenses,
        ),
    )
    reject(
        118,
        "overlapping-entities",
        "entity-split-overlap",
        lambda: release_gate(
            dict(release, eval_ids=release["eval_ids"] + release["train_ids"][:1]),
            licenses,
        ),
    )

    outcomes = outcome_pilot(fixture["outcomes"], binary)
    gate(
        119,
        "executed-model-arms",
        "completed",
        "completed",
        {
            "attempts": outcomes["attempts"],
            "budget": outcomes["budget"],
            "quality_threshold": outcomes["quality_threshold"],
        },
    )
    gate(
        119,
        "proof-completion-selection",
        "inconclusive",
        outcomes["selection_status"],
        {
            "attempts": outcomes["selection_mutant"],
            "full_group_b_mae": outcomes["subgroup_b_full_mae"],
            "survivor_group_b_mae": outcomes["subgroup_b_survivor_mae"],
        },
    )
    schedule = fixture["outcomes"]["seeds"]
    survivors = [a for a in outcomes["selection_mutant"] if a["status"] == "completed"]
    gate(
        119,
        "missing-failure-outcome",
        "inconclusive",
        complete_arm(survivors, schedule),
        {"retained_attempts": survivors},
    )
    require(
        any(a["ordinary_federated"] != a["bad_data"] for a in outcomes["attempts"]),
        "bad-data-fixture-did-not-change-outcome",
    )
    gate(
        119,
        "bad-data-contributor",
        "diagnostic",
        "diagnostic",
        {"deviations": [a["bad_data"] != a["ordinary_federated"] for a in outcomes["attempts"]]},
    )

    registry = load(ROOT / "claims/registry.json")
    trace = load(ROOT / "claims/traceability-v1.json")
    # The already validated index is larger than the public artifact node budget.
    # Read under the byte cap, then apply the public bounds to the claim projection.
    source: DOC = json.loads(bounded_file(ROOT / "claims/source-map-v1.json"))
    require(len(source["nodes"]) <= 2048, "source-map-size")
    claims = claim_portal(registry, trace, source)
    gate(
        120,
        "authoritative-claim-coverage",
        "completed",
        "completed",
        {
            "claims": len(claims),
            "source_version": trace["source_version"],
            "status_counts": {
                status: sum(row["status"] == status for row in claims)
                for status in sorted({row["status"] for row in claims})
            },
        },
    )
    theorem = next(c for c in registry["claims"] if c["kind"] == "cryptographic-security")
    reject(
        120,
        "unit-test-theorem-promotion",
        "theorem-without-formal-evidence",
        lambda: strength_gate(
            dict(theorem, status="tested"),
            [{"kind": "unit-test", "evidence_id": "sample-test"}],
        ),
    )
    broken = copy.deepcopy(trace)
    broken["evidence"][0].update(
        path="specs/ci/unavailable-evidence.json",
        execution={"outcome": "failed", "scope": "synthetic failure display fixture"},
    )
    rows_with_errors = claim_portal(registry, broken, dict(source, nodes=[]))
    preview = render_portal(rows_with_errors, "synthetic", gates)
    require(
        all(
            term in preview
            for term in ("unavailable", "failed", "synthetic failure display fixture")
        ),
        "portal-hides-negative-evidence",
    )
    gate(
        120,
        "visible-broken-source-and-failed-evidence",
        "inconclusive",
        "inconclusive",
        {"reference": "unavailable", "observed_evidence_outcome": "failed"},
    )

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    ref = (
        os.environ.get("GITHUB_REF")
        or subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    report = {
        "schema_version": "1.0.0",
        "source_commit": commit,
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "provenance": {
            "python": platform.python_version(),
            "os_arch": platform.platform(),
            "workflow_run": os.environ.get("GITHUB_RUN_ID", "local"),
            "workflow_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local"),
            "native_binary_sha256": sha(binary.read_bytes()),
            "cargo_lock_sha256": sha(bounded_file(ROOT / "Cargo.lock")),
        },
        "source_ref": ref,
        "fixture_id": fixture["version"],
        "fixture_sha256": sha(bounded_file(FIXTURE)),
        "source_files": {
            name: sha(bounded_file(ROOT / name))
            for name in (
                "src/fzkml_ci/evidence_gates.py",
                "specs/ci/evidence-run-v1.schema.json",
                "claims/registry.json",
                "claims/traceability-v1.json",
                "claims/source-map-v1.json",
                "specs/numeric-contract-v1.json",
            )
        },
        "gates": gates,
        "claims": claims,
        "limitations": [
            "Synthetic benchmark timings and selection failures are controlled fixtures.",
            "Lineage is single-process. The preview performs no network release.",
            "The matched proof exposes the witness inputs and does not secure aggregation.",
            "A broken source or failed test remains visible. Claim status is authored.",
        ],
    }
    validate_report(report)
    return report, render_portal(claims, commit, gates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mutation", choices=("benchmark-scope",))
    args = parser.parse_args()
    try:
        report, page = build(args.binary.resolve(), args.mutation)
        if args.output is not None:
            write_outputs(args.output, report, page)
        print("## Synthetic CI evidence gates")
        print()
        for row in report["gates"]:
            print(f"- #{row['issue']} {row['id']}: {row['observed']}")
        print(f"- Portal candidate: {len(report['claims'])} claims")
        return 0
    except (Invalid, OSError) as error:
        print(
            f"evidence gate failed: {error if isinstance(error, Invalid) else 'io-error'}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
