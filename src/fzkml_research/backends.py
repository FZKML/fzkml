"""Adequacy gates around CI-11's shared benchmark comparison; no vendor leaderboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fzkml_ci.benchmark import compare
from fzkml_ci.validate import Invalid, require, validate_result


@dataclass(frozen=True)
class Assurance:
    relation: str
    numerical_semantics: str
    guarantee: str
    observer: str
    mode: Literal[
        "specialized-property", "full-training", "recursion", "attestation", "arithmetic-only"
    ]
    security_assumptions: str
    setup_assumptions: str
    payload_binding: str


@dataclass(frozen=True)
class BackendEvidence:
    backend: str
    assurance: Assurance
    status: Literal["available", "not-run", "unsupported"]
    reason: str
    review_id: str | None
    result: dict[str, Any] | None


def compare_backends(required: Assurance, entries: list[BackendEvidence]) -> dict[str, Any]:
    require(bool(entries) and len(entries) <= 16, "backend-count")
    require(len({e.backend for e in entries}) == len(entries), "duplicate-backend")
    require(
        all(
            (
                required.relation,
                required.numerical_semantics,
                required.guarantee,
                required.observer,
                required.security_assumptions,
                required.setup_assumptions,
                required.payload_binding,
            )
        ),
        "assurance-scope-required",
    )
    report: dict[str, Any] = {
        "status": "inconclusive",
        "selection": None,
        "eligible": [],
        "excluded": [],
        "comparisons": [],
        "limitations": [
            "Security/setup equivalence needs independent domain review.",
            "A native arithmetic kernel is not a full-training proof backend.",
            "No selection is inferred from time alone without resource/workload policy.",
        ],
    }
    eligible = []
    for entry in entries:
        require(
            entry.status in {"available", "not-run", "unsupported"} and bool(entry.reason),
            "backend-availability",
        )
        reason = None
        if entry.status != "available":
            require(entry.result is None, "unrun-backend-has-results")
            reason = entry.status + ": " + entry.reason
        elif entry.assurance != required:
            reason = (
                "Different relation, guarantee, observer, security/setup or numerical semantics."
            )
        elif entry.assurance.mode == "arithmetic-only":
            reason = "Arithmetic-only kernel cannot satisfy a proof bakeoff."
        elif not entry.review_id:
            reason = "Equivalence and payload-binding review unavailable."
        elif entry.result is None:
            reason = "No retained result bundle."
        else:
            validate_result(entry.result)
            require(
                entry.result["scenario"]["security_mode"] == "research",
                "synthetic-record-is-not-proof-evidence",
            )
            require(
                all(
                    entry.result["scenario"][key] != "sha256:" + "0" * 64
                    for key in (
                        "parameters_digest",
                        "program_digest",
                        "circuit_digest",
                        "key_digest",
                    )
                ),
                "proof-backend-identity-unavailable",
            )
            require(entry.result["scenario"]["backend"] == entry.backend, "backend-identity")
            require(
                entry.result["scenario"]["relation_version"] == required.relation
                and entry.result["scenario"]["numerical_semantics"] == required.numerical_semantics,
                "backend-assurance-result-mismatch",
            )
        if reason:
            report["excluded"].append({"backend": entry.backend, "reason": reason})
        else:
            eligible.append(entry)
            report["eligible"].append(entry.backend)
    for i, left in enumerate(eligible):
        for right in eligible[i + 1 :]:
            assert left.result is not None and right.result is not None
            try:
                comparison = compare(left.result, right.result)
            except Invalid as error:
                report["comparisons"].append(
                    {
                        "left": left.backend,
                        "right": right.backend,
                        "status": "incomparable",
                        "reason": str(error),
                    }
                )
            else:
                report["comparisons"].append(
                    {
                        "left": left.backend,
                        "right": right.backend,
                        "status": "diagnostic",
                        "evidence": comparison,
                    }
                )
    if any(row["status"] == "diagnostic" for row in report["comparisons"]):
        report["status"] = "diagnostic"
    return report
