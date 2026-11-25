"""Fail closed on malformed or oversized public data, without echoing input."""

from __future__ import annotations

import ast
import json
import math
import re
import stat
import statistics
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
MAX_FILE = 1_000_000
MAX_TOTAL = 4_000_000
ARTIFACTS = frozenset(
    {"results.json", "claims.json", "summary.json", "report.md", "report.html", "plots.svg"}
)
SECRET = re.compile(
    r"FZKML_FORBIDDEN_SECRET|-----BEGIN .*PRIVATE KEY-----|"
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})|"
    r"(?i:password|api[_-]?key|access[_-]?token)\s*[:=]\s*\S+"
)


class Invalid(ValueError):
    """Safe, bounded diagnostic suitable for public CI logs."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise Invalid(code)


def bounded_file(path: Path) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "regular-single-link-file-required")
    require(info.st_size <= MAX_FILE, "file-size-limit")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE + 1)
    require(len(data) <= MAX_FILE, "file-size-limit")
    return data


def public_tree(value: Any) -> None:
    stack = [(value, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        require(count <= 30_000 and depth <= 24, "data-complexity-limit")
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
            stack.extend((k, depth + 1) for k in item)
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)
        elif isinstance(item, str):
            require(len(item) <= 1000 and not SECRET.search(item), "public-string-policy")
            require(all(ord(c) >= 32 or c == "\n" for c in item), "control-character")
        elif isinstance(item, float):
            require(math.isfinite(item), "nonfinite-number")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate-json-key")
        result[key] = value
    return result


def load(path: Path) -> Any:
    try:
        value = json.loads(bounded_file(path), object_pairs_hook=_pairs)
    except (ValueError, RecursionError, UnicodeError) as error:
        raise Invalid("invalid-json") from error
    public_tree(value)
    return value


def schema(value: Any, name: str) -> None:
    public_tree(value)
    if name in {"result", "bundle", "claims"}:
        version = value.get("schema_version") if isinstance(value, dict) else None
        supported = {
            "result": {"1.0.0", "1.1.0"},
            "bundle": {"1.0.0", "1.1.0"},
            "claims": {"1.0.0"},
        }
        require(isinstance(version, str) and version in supported[name], f"{name}-schema-version")
    else:
        require(name in {"ci-run", "ci-proof"}, "unknown-schema")
        version = "1.0.0"
    definition = json.loads((ROOT / "schemas" / f"{name}-{version}.json").read_text())
    local: Registry[Any] = Registry()
    for path in (ROOT / "schemas").glob("*.json"):
        document = json.loads(path.read_text())
        resource = Resource.from_contents(document)
        local = local.with_resource(document["$id"], resource)
    require(
        Draft202012Validator(definition, registry=local).is_valid(value),
        f"{name}-schema-invalid",
    )


def unique(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    mapped = {r[key]: r for r in records}
    require(len(mapped) == len(records), "duplicate-identifier")
    return mapped


def validate_result(result: dict[str, Any]) -> None:
    schema(result, "result")
    reps = unique(result["repetitions"], "id")
    status = result["outcome"]["status"]
    if status in {"not-run", "unsupported"}:
        require(not reps and not result["metrics"], "unrun-has-measurements")
    else:
        require(bool(reps), "executed-without-repetitions")
    if status == "successful":
        require(
            any(r["status"] == "successful" and not r["excluded"] for r in reps.values()),
            "success-without-successful-repetition",
        )
    if status == "failed":
        require(all(r["status"] == "failed" for r in reps.values()), "failure-status-conflict")
    if status == "inconclusive":
        require(bool(result["outcome"]["reason"].strip()), "inconclusive-needs-reason")
    if status not in {"not-run", "unsupported"}:
        p = result["provenance"]
        require(
            p["source_commit"] != "0" * 40
            and (p.get("execution_kind") == "local" or p["workflow_run"] > 0)
            and p["dependency_digest"] != "sha256:" + "0" * 64,
            "executed-provenance-placeholder",
        )
    units = {
        "time": "s",
        "memory": "byte",
        "communication": "byte",
        "quality": "ratio",
        "proof-bytes": "byte",
    }
    for rep in reps.values():
        require(not rep["timeout"] or rep["status"] == "failed", "timeout-status-conflict")
        require(rep["quality"] != "fail" or rep["status"] != "successful", "quality-conflict")
        keys = [(m["phase"], m["quantity"]) for m in rep["measurements"]]
        require(len(keys) == len(set(keys)), "duplicate-measurement")
        for m in rep["measurements"]:
            require(m["unit"] == units[m["quantity"]], "quantity-unit-mismatch")
            require(m["quantity"] != "quality" or m["value"] <= 1, "quality-range")
    metric_keys = [(m["phase"], m["quantity"]) for m in result["metrics"]]
    require(len(metric_keys) == len(set(metric_keys)), "duplicate-summary-metric")
    aggregations: dict[str, Callable[[list[float]], float]] = {
        "mean": statistics.mean,
        "median": statistics.median,
        "min": min,
        "max": max,
        "sum": sum,
    }
    for metric in result["metrics"]:
        values = []
        for rid in metric["repetition_ids"]:
            require(rid in reps, "dangling-repetition")
            rep = reps[rid]
            require(not rep["excluded"], "excluded-repetition-in-summary")
            matches = [
                m
                for m in rep["measurements"]
                if all(m[k] == metric[k] for k in ("phase", "quantity", "unit"))
            ]
            require(len(matches) == 1, "summary-without-raw-measurement")
            values.append(matches[0]["value"])
        expected = aggregations[metric["aggregation"]](values)
        require(math.isclose(expected, metric["value"], rel_tol=1e-12), "aggregation-mismatch")


def evidence_path(reference: str) -> Path:
    path = ROOT / reference.split("::")[0]
    require(not path.is_symlink(), "evidence-symlink")
    require(path.resolve().is_relative_to(ROOT), "evidence-outside-repository")
    require(path.is_file(), "dangling-evidence-path")
    return path


def validate_claims(registry: dict[str, Any]) -> dict[str, Any]:
    schema(registry, "claims")
    claims = unique(registry["claims"], "id")
    evidence = unique(registry["evidence"], "id")
    for entry in evidence.values():
        path = evidence_path(entry["path"])
        if entry["kind"] == "unit-test":
            pieces = entry["path"].split("::")
            require(len(pieces) == 2 and path.suffix == ".py", "test-reference-format")
            tree = ast.parse(path.read_text())
            names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            require(pieces[1].startswith("test_") and pieces[1] in names, "dangling-test")
    for claim in claims.values():
        require(set(claim["evidence_ids"]) <= evidence.keys(), "dangling-claim-evidence")
        require(
            claim["id"].split("-")[1] == claim["source"]["edition"]
            and int(claim["id"].split("-")[2][1:]) == claim["source"]["chapter"],
            "claim-source-id-mismatch",
        )
        for attribute, kind in (
            ("formal_proof", "formal-proof"),
            ("independent_review", "independent-review"),
        ):
            for eid in claim[attribute]["artifact_ids"]:
                require(eid in claim["evidence_ids"], "unmapped-special-evidence")
                require(eid in evidence and evidence[eid]["kind"] == kind, "evidence-kind-mismatch")
        # Status is authored and never promoted by test outcomes.
    return {
        "total": len(claims),
        "by_status": {
            status: sorted(c["id"] for c in claims.values() if c["status"] == status)
            for status in (
                "planned",
                "specified",
                "implemented",
                "tested",
                "replicated",
                "reviewed",
                "refuted",
                "inconclusive",
                "unsupported",
                "deferred",
            )
        },
        "unmapped": sorted(c["id"] for c in claims.values() if not c["evidence_ids"]),
        "extraction": "pending-R001",
    }


def validate_bundle(bundle: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    schema(bundle, "bundle")
    coverage = validate_claims(registry)
    unique(bundle["results"], "run_id")
    claims = {c["id"] for c in registry["claims"]}
    for result in bundle["results"]:
        validate_result(result)
        require(set(result["claim_ids"]) <= claims, "dangling-result-claim")
    return coverage


def validate_artifacts(directory: Path) -> None:
    require(directory.is_dir() and not directory.is_symlink(), "artifact-directory-required")
    require({p.name for p in directory.iterdir()} == ARTIFACTS, "artifact-path-allowlist")
    total = 0
    for path in directory.iterdir():
        data = bounded_file(path)
        total += len(data)
        require(not SECRET.search(data.decode("utf-8")), "artifact-secret-marker")
    require(total <= MAX_TOTAL, "artifact-total-size-limit")
    bundle = load(directory / "results.json")
    validate_bundle(bundle, load(directory / "claims.json"))
    require_publication(bundle)


def require_publication(bundle: dict[str, Any]) -> None:
    require(
        all(row["publication_review"]["approved"] is True for row in bundle["results"]),
        "publication-review-pending",
    )
