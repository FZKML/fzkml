"""Explicit public surface selection, shared with CI-10's public-tree validator."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fzkml_ci.validate import public_tree

from .histories import digest
from .integer import Vector, property_valid


@dataclass(repr=False)
class Witness:
    features: Vector = field(repr=False)
    label: int = field(repr=False)
    private_notes: str = field(repr=False)
    commitment_coins: bytes = field(repr=False)


def public_execution(witness: Witness, compute: Callable[[Witness], Vector]) -> dict[str, Any]:
    # No asdict/repr(witness), exception payloads, raw traces, witness digest or timing.
    try:
        delta = compute(witness)
        status = "accepted" if property_valid(delta) else "rejected"
    except Exception:
        status = "failed"
    event = {
        "version": 1,
        "operation": "synthetic-local-check",
        "status": status,
        "policy": digest("public-policy", {"bound_squared": 4608}),
        "proof_mode": "none",
        "limitations": ["No cryptographic proof or witness privacy."],
    }
    public_tree(event)
    return event


def validate_observers(inventory: dict[str, Any]) -> None:
    if set(inventory) != {"version", "roles", "flows", "public_surfaces", "limitations"}:
        raise ValueError("observer-inventory-fields")
    if inventory["version"] != 1 or not inventory["roles"] or not inventory["public_surfaces"]:
        raise ValueError("observer-inventory-version")
    roles = inventory["roles"]
    required = {
        "client",
        "trusted-cluster",
        "outsourced-prover",
        "collaborative-prover",
        "coordinator",
        "committee",
        "telemetry",
        "artifact-store",
        "attested-prover",
    }
    if set(roles) != required:
        raise ValueError("missing-computing-role")
    for role in roles.values():
        if not role.get("witness_view") or not role.get("assumption") or not role.get("status"):
            raise ValueError("uncovered-external-computing-role")
    for flow in inventory["flows"]:
        if (
            set(flow) != {"sender", "receiver", "data", "protection", "assumption"}
            or flow["sender"] not in roles
            or flow["receiver"] not in roles
            or not all(flow[k] for k in ["data", "protection", "assumption"])
        ):
            raise ValueError("uncovered-data-flow")
    public_tree(inventory)


def public_bytes(value: Any) -> bytes:
    public_tree(value)
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
