"""Bounded synthetic content addressing and preprocessing; hashes are not private PSI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

ORGS = ("synthetic:A", "synthetic:B", "synthetic:C")
SCHEMA = {
    "version": "raw-row-1",
    "fields": ["id", "entity", "org", "time", "value", "label", "unit", "split"],
    "integers": "time[0,1000]; value,label[-32,32]",
    "raw_unit": "cm",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(domain: str, value: Any) -> str:
    return hashlib.sha256(
        b"FZK-S02-DATA-01\0" + domain.encode() + b"\0" + canonical(value)
    ).hexdigest()


@dataclass(frozen=True)
class Row:
    id: str
    entity: str
    org: str
    time: int
    value: int
    label: int
    unit: str
    split: str

    def validate(self) -> None:
        if not all(
            type(v) is str and v.startswith("synthetic:") and len(v) <= 100
            for v in (self.id, self.entity, self.org)
        ):
            raise ValueError("synthetic-identifiers-only")
        if self.org not in ORGS or any(
            type(v) is not int for v in (self.time, self.value, self.label)
        ):
            raise ValueError("row-schema")
        if not (0 <= self.time <= 1000 and abs(self.value) <= 32 and abs(self.label) <= 32):
            raise ValueError("row-integer-domain")
        if self.unit != "cm" or self.split not in ("train", "holdout"):
            raise ValueError("row-unit-or-split")


@dataclass(frozen=True)
class Policy:
    version: str = "synthetic-policy-1"
    schema_version: str = "raw-row-1"
    preprocessing_version: str = "exact-cm-mm-v1"
    cutoff: int = 10
    holdout: tuple[str, ...] = ("synthetic:p3",)
    organizations: tuple[str, ...] = ORGS

    def validate(self) -> None:
        if (
            type(self.holdout) is not tuple
            or type(self.organizations) is not tuple
            or self.organizations != ORGS
            or len(set(self.holdout)) != len(self.holdout)
            or self.schema_version not in ("raw-row-1", "raw-row-2")
            or self.preprocessing_version not in ("exact-cm-mm-v1", "exact-cm-mm-v2")
            or type(self.cutoff) is not int
            or not 0 <= self.cutoff <= 1000
            or not self.version.startswith("synthetic-policy-")
        ):
            raise ValueError("bounded-policy-contract")

    @property
    def identity(self) -> str:
        self.validate()
        return digest("authorization-policy", asdict(self))

    @property
    def dag(self) -> list[dict[str, Any]]:
        self.validate()
        operations = [
            (
                "validate",
                self.schema_version,
                {"schema": SCHEMA | {"version": self.schema_version}},
            ),
            ("units", self.preprocessing_version, {"from": "cm", "to": "mm", "factor": 10}),
            ("split", "entity-time-1", {"cutoff": self.cutoff, "holdout": list(self.holdout)}),
        ]
        result = []
        parent = "raw-partitions"
        for op, version, parameters in operations:
            node = {"op": op, "version": version, "parameters": parameters, "parent": parent}
            identity = digest("preprocessing-node", node)
            result.append(node | {"id": identity})
            parent = identity
        return result


def partition(rows: tuple[Row, ...], org: str, source_version: str = "source-1") -> dict[str, Any]:
    if type(rows) is not tuple or org not in ORGS or not source_version.startswith("source-"):
        raise ValueError("partition-contract")
    for r in rows:
        r.validate()
        if r.org != org:
            raise ValueError("wrong-partition-owner")
    if len({r.id for r in rows}) != len(rows) or len(rows) > 4096:
        raise ValueError("duplicate-row-or-partition-bound")
    value = {
        "organization": org,
        "source_version": source_version,
        "rows": [asdict(r) for r in sorted(rows, key=lambda r: r.id)],
    }
    return value | {"digest": digest("raw-partition", value)}


def verify_partition(p: dict[str, Any]) -> tuple[Row, ...]:
    if set(p) != {"organization", "source_version", "rows", "digest"}:
        raise ValueError("partition-fields")
    rows = tuple(Row(**r) for r in p["rows"])
    if partition(rows, p["organization"], p["source_version"]) != p:
        raise ValueError("partition-content-or-canonical-order")
    return rows


def snapshot(parts: tuple[dict[str, Any], ...], policy: Policy) -> dict[str, Any]:
    policy.validate()
    if not parts or len(parts) > 3 or len({p["organization"] for p in parts}) != len(parts):
        raise ValueError("unique-nonempty-source-partitions")
    selected = []
    excluded = []
    for p in sorted(parts, key=lambda p: p["organization"]):
        for r in verify_partition(p):
            expected = "holdout" if r.entity in policy.holdout else "train"
            if r.split != expected:
                raise ValueError("forged-entity-split")
            transformed = asdict(r) | {"value": 10 * r.value, "unit": "mm"}
            if r.time > policy.cutoff:
                excluded.append(
                    {"row_digest": digest("raw-row", asdict(r)), "reason": "future-event"}
                )
            else:
                selected.append(transformed)
    selected.sort(key=lambda r: (r["org"], r["id"]))
    if len({(r["org"], r["id"]) for r in selected}) != len(selected):
        raise ValueError("duplicate-selected-row")
    manifest = {
        "version": "snapshot-1",
        "schema_digest": digest("schema", SCHEMA | {"version": policy.schema_version}),
        "policy_digest": policy.identity,
        "preprocessing_digest": digest("dag", policy.dag),
        "dag": policy.dag,
        "partition_inventory": {p["organization"]: p["digest"] for p in parts},
        "selected_row_digests": [digest("processed-row", r) for r in selected],
        "selected_count": len(selected),
        "excluded": excluded,
    }
    return {"manifest": manifest, "identity": digest("snapshot", manifest), "rows": selected}


def verify_snapshot(
    state: dict[str, Any],
    parts: tuple[dict[str, Any], ...],
    policy: Policy,
    expected_inventory: dict[str, str] | None = None,
) -> str:
    if snapshot(parts, policy) != state:
        raise ValueError("snapshot-or-preprocessing-lineage-mismatch")
    if expected_inventory is None:
        return "selection-membership-only"
    if state["manifest"]["partition_inventory"] != expected_inventory:
        raise ValueError("incomplete-approved-source-inventory")
    return "complete-relative-to-trusted-inventory-not-real-world-population"


def synthetic_parts() -> tuple[dict[str, Any], ...]:
    parts = []
    for i, org in enumerate(ORGS):
        rows = tuple(
            Row(
                f"synthetic:r{i}-{j}",
                f"synthetic:p{j}",
                org,
                2 + j,
                1 + i + j,
                2 * j - i,
                "cm",
                "holdout" if j == 3 else "train",
            )
            for j in range(4)
        )
        parts.append(partition(rows, org))
    return tuple(parts)
