"""Workflow receipts and tier policy; scientific results remain CI-04 records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .validate import ROOT, bounded_file, load, public_tree, require, require_publication, schema

COMMANDS = {
    "contract": ["./scripts/validate"],
    "proof": ["./scripts/research", "proof"],
    "oracle": ["./scripts/s04-conformance"],
    "adversarial": ["./scripts/s04-adversarial"],
    "integration": ["./scripts/validate-language"],
}
NEGATIVES = {
    "changed-output",
    "changed-public-count",
    "wrong-verifying-key",
    "malformed-proof",
    "trailing-proof-byte",
}
DIGESTS = {
    "adapter_digest",
    "contract_digest",
    "program_digest",
    "circuit_digest",
    "native_extension_digest",
    "parameters_digest",
    "key_digest",
}
PROOF_FIELDS = {
    "version",
    "backend",
    "proof_mode",
    "assurance",
    "source_commit",
    "source_dirty",
    "verified",
    "proof_bytes",
    "expected_output",
    "oracle_matches",
    "negatives",
    "seconds",
    "workflow_run",
    "limitations",
} | DIGESTS


def proof_receipt(value: Any, expected_source: str | None = None) -> None:
    schema(value, "ci-proof")
    public_tree(value)
    require(isinstance(value, dict) and set(value) == PROOF_FIELDS, "proof-receipt-fields")
    require(
        value["version"] == 1
        and value["backend"] == "ark-groth16-0.5.0-bn254"
        and value["proof_mode"] == "research-real"
        and value["assurance"] == "public-arithmetic-only",
        "genuine-backend-or-assurance-required",
    )
    require(
        value["verified"] is True
        and value["oracle_matches"] is True
        and value["expected_output"] == 9
        and value["proof_bytes"] == 128,
        "proof-verdict",
    )
    require(
        isinstance(value["negatives"], dict)
        and set(value["negatives"]) == NEGATIVES
        and all(v is True for v in value["negatives"].values()),
        "mandatory-negative-proof-cases",
    )
    require(re.fullmatch(r"[a-f0-9]{40}", value["source_commit"]) is not None, "proof-source")
    require(
        expected_source is None or value["source_commit"] == expected_source, "stale-proof-receipt"
    )
    require(
        value["workflow_run"] is None or value["source_dirty"] is False,
        "dirty-hosted-proof-receipt",
    )
    for name in DIGESTS:
        require(
            isinstance(value[name], str)
            and re.fullmatch(r"sha256:[a-f0-9]{64}", value[name]) is not None
            and value[name] != "sha256:" + "0" * 64,
            "proof-identity-unavailable",
        )
    require(
        set(value["seconds"])
        == {
            "prove",
            "prepare",
            "verify",
            "witness",
            "setup",
            "end-to-end",
            "negative-verify",
            "negative-setup",
        },
        "proof-phase-fields",
    )
    require(
        all(type(v) in {int, float} and 0 <= v <= 900 for v in value["seconds"].values()),
        "proof-phase-range",
    )
    require(
        value["workflow_run"] is None
        or (type(value["workflow_run"]) is int and value["workflow_run"] > 0),
        "proof-workflow-identity",
    )
    require(
        isinstance(value["limitations"], list) and bool(value["limitations"]), "proof-limitations"
    )


def journal(value: Any) -> None:
    schema(value, "ci-run")
    public_tree(value)
    require(
        set(value)
        == {
            "version",
            "profile",
            "source_sha",
            "workflow_run",
            "attempt",
            "status",
            "repetitions",
            "limitations",
        },
        "journal-fields",
    )
    require(
        value["version"] == 1 and re.fullmatch(r"[a-f0-9]{40}", value["source_sha"]) is not None,
        "journal-source-or-version",
    )
    require(
        value["profile"]
        in {
            "contract",
            "tiny-reference",
            "conformance",
            "nightly-adversarial",
            "weekly-proof",
            "integration",
            "protocol-invariants",
        },
        "journal-profile",
    )
    statuses = {
        "initialized",
        "running",
        "completed",
        "failed",
        "unavailable",
        "skipped",
        "inconclusive",
    }
    require(value["status"] in statuses, "journal-status")
    require(
        isinstance(value["repetitions"], list) and 1 <= len(value["repetitions"]) <= 5,
        "journal-repetitions",
    )
    for index, repetition in enumerate(value["repetitions"]):
        require(
            set(repetition) == {"index", "status", "seconds"} and repetition["index"] == index,
            "journal-repetition-fields",
        )
        require(
            repetition["status"]
            in {
                "not-started",
                "running",
                "completed",
                "failed",
                "timed-out",
                "cancelled",
                "not-run",
                "skipped",
                "inconclusive",
            },
            "repetition-status",
        )
        seconds = repetition["seconds"]
        require(
            seconds is None or (type(seconds) in {int, float} and 0 <= seconds <= 1800),
            "journal-time-range",
        )
    if value["status"] == "completed":
        require(
            all(
                r["status"] == "completed" and r["seconds"] is not None
                for r in value["repetitions"]
            ),
            "completed-with-unexecuted-repetitions",
        )
    if value["status"] == "unavailable":
        require(
            all(r["status"] == "not-run" and r["seconds"] is None for r in value["repetitions"]),
            "unavailable-with-measurements",
        )


def artifact_tree(directory: Path = ROOT / "research") -> None:
    from .research import proof_results

    require(directory.is_dir() and not directory.is_symlink(), "journal-directory")
    require((directory / "journal.json").exists(), "initial-journal-required")
    state = load(directory / "journal.json")
    journal(state)
    require(len(list(directory.iterdir())) <= 12, "journal-artifact-count")
    total = 0
    for path in directory.iterdir():
        allowed = {"journal.json", "reproducer.json", "proof-check.json", "proof-results.json"}
        require(
            path.name in allowed
            or re.fullmatch(r"rep-[0-4]-proof-results.json", path.name) is not None,
            "journal-artifact-allowlist",
        )
        total += len(bounded_file(path))
        value = load(path)
        if path.name == "journal.json":
            journal(value)
        elif path.name == "proof-check.json":
            proof_receipt(value, state["source_sha"])
        elif "proof-results" in path.name:
            proof_results(value)
            require_publication(value)
            require(
                all(
                    row["provenance"]["source_commit"] == state["source_sha"]
                    and str(row["provenance"]["workflow_run"]) == state["workflow_run"]
                    for row in value["results"]
                ),
                "stale-journal-proof-results",
            )
        else:
            require(
                set(value)
                == {
                    "profile",
                    "repetition",
                    "command",
                    "source_sha",
                    "public_seed",
                    "fixture_digest",
                },
                "reproducer-fields",
            )
            require(
                value["profile"]
                in {
                    "contract",
                    "tiny-reference",
                    "conformance",
                    "nightly-adversarial",
                    "weekly-proof",
                    "integration",
                    "protocol-invariants",
                },
                "reproducer-profile",
            )
            require(
                value["command"] == f"./scripts/research run {value['profile']}",
                "reproducer-command",
            )
            require(
                value["public_seed"] == 20261125
                and type(value["repetition"]) is int
                and 0 <= value["repetition"] < 5,
                "reproducer-seed-or-index",
            )
            require(
                re.fullmatch(r"[a-f0-9]{40}", value["source_sha"]) is not None
                and re.fullmatch(r"sha256:[a-f0-9]{64}", value["fixture_digest"]) is not None,
                "reproducer-provenance",
            )
    require(total <= 4_000_000, "journal-total-size")


def summary(path: Path) -> str:
    if not path.exists():
        return (
            "### Research status: inconclusive\nNo journal survived; reconcile workflow metadata.\n"
        )
    value = load(path)
    journal(value)
    lines = [
        f"### {value['profile']}: {value['status']}",
        f"Source: `{value['source_sha']}`",
        "",
        "| Repetition | Outcome | Wall seconds |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| {r['index']} | {r['status']} | "
        f"{r['seconds'] if r['seconds'] is not None else 'unavailable'} |"
        for r in value["repetitions"]
    )
    lines += [
        "",
        "Operational wall times include setup/build/cache work. Shared CPU timings are diagnostic.",
        "Skipped, unavailable, incomplete and failed runs do not establish success.",
        "Scientific claims require the separate CI-04 records and domain review.",
    ]
    receipt_path = path.parent / "proof-check.json"
    if receipt_path.exists():
        receipt = load(receipt_path)
        proof_receipt(receipt, value["source_sha"])
        lines += [
            "",
            f"Backend: `{receipt['backend']}`; mode: `{receipt['proof_mode']}`.",
            f"Assurance: {receipt['assurance']}.",
            f"Program: `{receipt['program_digest']}`.",
            f"Circuit: `{receipt['circuit_digest']}`.",
            "Last verified receipt: five negatives rejected; ephemeral research keys.",
        ]
    return "\n".join(lines) + "\n"


def verify_required(outcomes: dict[str, str]) -> bool:
    return set(outcomes) == {"foundation", "proof", "conformance", "registry"} and all(
        value == "success" for value in outcomes.values()
    )
