"""Bounded synthetic reference checks; no cryptographic verifier or production ledger."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any


def require(condition: object, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def word(index: int) -> bytes:
    return ((index * 6364136223846793005 + 17) % (1 << 64)).to_bytes(8, "little")


def checkpoint(
    context: dict[str, Any], sequence: int, offset: int, prefix: bytes
) -> dict[str, Any]:
    return {
        "context": digest(context),
        "sequence": sequence,
        "offset": offset,
        "prefix_sha256": hashlib.sha256(prefix).hexdigest(),
    }


def check_checkpoint(
    record: dict[str, Any], context: dict[str, Any], sequence: int, offset: int, prefix: bytes
) -> None:
    require(0 <= offset <= context["n"] and len(prefix) == offset * 8, "checkpoint-offset")
    require(record == checkpoint(context, sequence, offset, prefix), "checkpoint-binding-or-replay")


def check_external(payload: bytes, count: int, expected_hash: str) -> None:
    require(
        len(payload) == count * 8 and hashlib.sha256(payload).hexdigest() == expected_hash,
        "external-witness-truncated-or-changed",
    )


@dataclass
class Job:
    payload: str
    cost: int
    state: str = "queued"
    token: int = 0
    cancel_requested: bool = False


class AdmissionReference:
    """Linearizable in-memory model; adapters must use the canonical durable ledger."""

    def __init__(
        self, workers: int = 2, waiting: int = 4, work: int = 12, identities: int = 256
    ) -> None:
        require(workers > 0 and waiting > 0 and work > 0 and identities > 0, "queue-policy")
        self.workers, self.waiting, self.work, self.identities = workers, waiting, work, identities
        self.lock = threading.RLock()
        self.jobs: dict[str, Job] = {}
        self.queue: deque[str] = deque()
        self.accepted: dict[str, str] = {}
        self.reserved = self.running = self.peak_reserved = self.peak_queue = 0
        self.generation = 0

    def submit(self, key: str, payload: bytes, cost: int, authorized: bool = True) -> str:
        require(type(cost) is int and 0 < cost <= self.work, "invalid-cost")
        require(
            authorized is True
            and isinstance(key, str)
            and 0 < len(key) <= 128
            and isinstance(payload, bytes)
            and len(payload) <= 256,
            "cheap-admission-rejected",
        )
        fingerprint = hashlib.sha256(payload).hexdigest()
        with self.lock:
            existing = self.jobs.get(key)
            if existing:
                require(existing.payload == fingerprint, "conflicting-retry")
                return "retransmission" if key in self.accepted else "joined-or-terminal-retry"
            if len(self.jobs) >= self.identities:
                return "identity-capacity"
            if len(self.queue) >= self.waiting or self.reserved + cost > self.work:
                return "backpressure"
            self.jobs[key] = Job(fingerprint, cost)
            self.queue.append(key)
            self.reserved += cost
            self.peak_reserved = max(self.peak_reserved, self.reserved)
            self.peak_queue = max(self.peak_queue, len(self.queue))
            return "queued"

    def start(self) -> tuple[str, int] | None:
        with self.lock:
            if self.running >= self.workers or not self.queue:
                return None
            key = self.queue.popleft()
            job = self.jobs[key]
            self.generation += 1
            job.state, job.token = "running", self.generation
            self.running += 1
            return key, job.token

    def cancel(self, key: str) -> str:
        with self.lock:
            job = self.jobs[key]
            if key in self.accepted:
                return "already-committed"
            if job.state == "queued":
                self.queue.remove(key)
                self.reserved -= job.cost
                job.state = "cancelled"
            elif job.state == "running":
                # A noninterruptible verifier still occupies actual work until exit.
                job.cancel_requested = True
            return job.state

    def finish(self, key: str, token: int, synthetic_valid: bool) -> bool:
        with self.lock:
            job = self.jobs[key]
            if job.state != "running" or token != job.token:
                return False
            self.running -= 1
            self.reserved -= job.cost
            if job.cancel_requested:
                job.state = "cancelled"
            elif synthetic_valid:
                self.accepted.setdefault(key, job.payload)
                job.state = "committed"
            else:
                job.state = "rejected"
            return key in self.accepted


def context() -> dict[str, Any]:
    return {
        "sid": "synthetic:m4",
        "round": 1,
        "parent": "parent0",
        "relation": "integer-sum-v1",
        "key": "fixture-key",
        "accepted_root": "fixture-roster-root",
        "model": "synthetic-model",
        "optimizer_state": "empty",
        "parameters": "fixture-v1",
        "payload_type": "weighted-numerator",
        "release_id": "release1",
        "roster": [[f"c{i}", 1] for i in range(4)],
    }


def certificate() -> dict[str, Any]:
    bound = context()
    leaves = [
        {
            "kind": "leaf",
            "id": f"c{i}",
            "weight": 1,
            "value": i + 1,
            "context": dict(bound),
            "available": True,
        }
        for i in range(4)
    ]
    branches = [
        {
            "kind": "branch",
            "children": leaves[i : i + 2],
            "sum": sum(j + 1 for j in range(i, i + 2)),
            "weight": 2,
        }
        for i in (0, 2)
    ]
    return {"kind": "branch", "children": branches, "sum": 10, "weight": 4}


def check_certificate_structure(tree: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """Check transparent fixture semantics; never label this a recursive proof."""
    expected_weights = dict(expected["roster"])
    seen: set[str] = set()
    order: list[str] = []

    def walk(node: dict[str, Any], depth: int) -> tuple[int, int, int]:
        require(depth <= 4, "certificate-depth-bound")
        if node.get("kind") == "leaf":
            require(
                node["id"] in expected_weights and node["id"] not in seen,
                "duplicate-or-unknown-leaf",
            )
            seen.add(node["id"])
            order.append(node["id"])
            require(node["context"] == expected, "disconnected-state-or-wrong-key")
            require(node["available"] is True, "missing-data-availability")
            require(
                type(node["weight"]) is int
                and 1 <= node["weight"] <= 4
                and type(node["value"]) is int
                and abs(node["value"]) <= 80
                and node["weight"] == expected_weights[node["id"]],
                "leaf-domain-or-weight-policy",
            )
            return node["weight"] * node["value"], node["weight"], depth
        require(
            node.get("kind") == "branch" and 1 <= len(node["children"]) <= 4,
            "certificate-node-shape",
        )
        values = [walk(child, depth + 1) for child in node["children"]]
        total, weight = sum(v[0] for v in values), sum(v[1] for v in values)
        require(node["sum"] == total and node["weight"] == weight, "wrong-sum-or-weight")
        return total, weight, max(v[2] for v in values)

    total, weight, depth = walk(tree, 0)
    require(order == [row[0] for row in expected["roster"]], "wrong-ordered-roster")
    return {
        "sum": total,
        "weight": weight,
        "depth": depth,
        "leaves": len(order),
        "proof_backend": "not-integrated",
        "zero_knowledge": "not-established",
    }


def check_topology(
    groups: list[list[str]],
    available: set[str],
    views: dict[str, list[str]],
    colluding_recipients: int = 1,
) -> None:
    require(1 <= len(groups) <= 12 and all(groups), "topology-shape")
    roster = [f"c{i}" for i in range(12)]
    flattened = [client for group in groups for client in group]
    require(
        sorted(flattened) == sorted(roster) and len(set(flattened)) == 12,
        "changed-cohort-or-duplicate-route",
    )
    require(available == set(roster), "partition-or-dropout-requires-abort")
    roles = {"coordinator"} | (
        {f"relay{i}" for i in range(len(groups))} if len(groups) > 1 else set()
    )
    require(set(views) == roles, "missing-role-observer-view")
    require(
        all(
            set(view) <= {"routing-metadata", "opaque-payloads", "global-release"}
            for view in views.values()
        ),
        "unauthorized-relay-observation",
    )
    require(
        type(colluding_recipients) is int and 0 <= colluding_recipients < 2,
        "reconstruction-threshold-exceeded",
    )


def subgroup_counterexample() -> dict[str, Any]:
    left = list(range(1, 13))
    right = list(left)
    right[0] += 1
    right[4] -= 1
    groups = [list(range(i, i + 4)) for i in (0, 4, 8)]
    return {
        "global_left": sum(left),
        "global_right": sum(right),
        "subgroups_left": [sum(left[i] for i in g) for g in groups],
        "subgroups_right": [sum(right[i] for i in g) for g in groups],
        "scope": "same global output, distinguishable clear relay sums; no DP theorem",
    }
