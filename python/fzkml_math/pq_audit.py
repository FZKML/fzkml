"""Fail-closed inventory checks, not an independent cryptographic certification."""

from __future__ import annotations

from typing import Any

ROLES = frozenset(
    {"proof", "commitment", "signature", "credential", "transport", "setup", "artifact"}
)


def audit(configuration: dict[str, Any]) -> dict[str, Any]:
    rows = configuration["primitives"]
    ids = [r["role"] for r in rows]
    if len(set(ids)) != len(ids) or set(ids) != ROLES:
        raise ValueError("incomplete-or-duplicate-stack-inventory")
    blockers = []
    for row in rows:
        if row["quantum_status"] not in {"vulnerable", "unknown", "candidate", "not-applicable"}:
            raise ValueError("unknown-assumption-class")
        if not row["source"] or not row["assumption"] or not row["replacement"]:
            raise ValueError("missing-evidence-or-migration-plan")
        if row["quantum_status"] in {"vulnerable", "unknown"}:
            blockers.append(row["role"] + ":" + row["quantum_status"])
    implemented = configuration["implemented"]
    approved = configuration["independent_review"] is True
    supported = not blockers and implemented and approved
    if configuration["claimed_full_stack_pq"] and not supported:
        raise ValueError("unsupported-full-stack-post-quantum-claim")
    return {
        "id": configuration["id"],
        "full_stack_pq_supported": supported,
        "blockers": blockers,
        "implemented": implemented,
        "performance_eligible": implemented,
        "review": "independent-review-required" if not approved else "recorded-review",
    }
