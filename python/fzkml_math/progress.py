"""Certified dependency closure and exact, explicitly simulated pipeline clocks."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from fractions import Fraction as F
from math import comb
from typing import Any


def miss_probability(total: int, bad: int, samples: int) -> F:
    if any(type(v) is not int for v in (total, bad, samples)) or not (
        1 <= total <= 100_000 and 0 <= bad <= total and 0 <= samples <= min(total, 10_000)
    ):
        raise ValueError("bounded-fixed-trace-without-replacement")
    return F(0) if samples > total - bad else F(comb(total - bad, samples), comb(total, samples))


def capacity(compute: F, prove: F, workers: int) -> F:
    if compute <= 0 or prove <= 0 or type(workers) is not int or workers < 1:
        raise ValueError("positive-independent-resource-capacities")
    return min(1 / compute, workers / prove)


@dataclass(frozen=True)
class Node:
    parent: str
    height: int
    context: str


class Frontier:
    """Single-writer in-memory reference. Boolean evidence is simulation-only.

    It cannot issue a cryptographic release authorization, durable receipt,
    consensus decision, or privacy-ledger debit.
    """

    def __init__(self, context: str = "synthetic-halving-v1") -> None:
        self.context = context
        self.nodes = {"genesis": Node("", 0, context)}
        self.checked = {"genesis"}
        self.certified = {"genesis"}
        self.available = {"genesis"}
        self.invalid: set[str] = set()
        self.released = "genesis"
        self.rollbacks = 0

    def add(self, name: str, parent: str, height: int, context: str) -> None:
        if (
            not name
            or name in self.nodes
            or parent not in self.nodes
            or parent in self.invalid
            or height != self.nodes[parent].height + 1
            or context != self.context
        ):
            raise ValueError("duplicate-parent-height-or-context")
        self.nodes[name] = Node(parent, height, context)
        self.available.add(name)

    def evidence(self, name: str, parent: str, context: str, valid: bool) -> None:
        if name not in self.nodes or name == "genesis" or name in self.invalid:
            raise ValueError("unknown-or-invalid-transition")
        node = self.nodes[name]
        if parent != node.parent or context != node.context or type(valid) is not bool:
            raise ValueError("stale-or-unbound-evidence")
        if not valid:
            if name in self.certified:
                raise ValueError("cannot-revoke-accepted-evidence")
            self.invalid.add(name)
            changed = True
            while changed:
                old = len(self.invalid)
                self.invalid.update(k for k, n in self.nodes.items() if n.parent in self.invalid)
                changed = old != len(self.invalid)
            self.rollbacks += 1
            return
        self.checked.add(name)
        changed = True
        while changed:
            old = len(self.certified)
            self.certified.update(
                k
                for k, n in self.nodes.items()
                if k not in self.invalid
                and k in self.checked
                and k in self.available
                and n.parent in self.certified
            )
            changed = old != len(self.certified)

    def release(self, name: str, *, require_real_proof: bool = True) -> dict[str, str]:
        if require_real_proof:
            raise ValueError("simulation-evidence-cannot-authorize-real-release")
        if name not in self.certified or name not in self.available or name in self.invalid:
            raise ValueError("uncertified-or-unavailable")
        ancestor = name
        while ancestor != self.released and ancestor != "genesis":
            ancestor = self.nodes[ancestor].parent
        if ancestor != self.released:
            raise ValueError("conflicting-single-state-release")
        self.released = name
        return {"state": name, "assurance": "simulation-only"}


def client_admission(start: int, head: int, age_limit: int, available: bool) -> str:
    if any(type(v) is not int for v in (start, head, age_limit)) or not (
        0 <= start <= head and age_limit >= 0
    ):
        raise ValueError("invalid-staleness-domain")
    return "unavailable" if not available else "stale" if head - start > age_limit else "admitted"


def pipeline(window: int, *, fail_height: int | None = None, rounds: int = 16) -> dict[str, Any]:
    """Exact deterministic discrete-event simulation, not hardware measurements.

    Serial halving updates take1/5s; each proof job occupies one of8 workers for2s.
    The quality target is the synthetic quadratic gap at the final halving state.
    Invalid transition injected at most once; pending descendants are discarded.
    """
    if window not in (1, 2, 4, 8) or not 1 <= rounds <= 128:
        raise ValueError("bounded-pipeline-profile")
    if fail_height is not None and not 1 <= fail_height <= rounds:
        raise ValueError("failure-height")
    f = Frontier()
    now = F(0)
    workers = [F(0)] * 8
    events: list[tuple[F, int, str]] = []
    serial = 0
    computing = False
    tip = "genesis"
    values = {"genesis": F(1)}
    backpressure = F(0)
    completed: dict[str, F] = {}
    certified_at: dict[str, F] = {"genesis": F(0)}
    issued = 0
    injected = False
    wasted = 0
    max_depth = 0
    trace: list[dict[str, str | int]] = []
    while True:
        frontier_height = max(f.nodes[k].height for k in f.certified)
        if frontier_height == rounds:
            break
        depth = f.nodes[tip].height - frontier_height
        max_depth = max(max_depth, depth)
        if not computing and f.nodes[tip].height < rounds and depth < window:
            serial += 1
            heapq.heappush(events, (now + F(1, 5), serial, "compute:" + tip))
            computing = True
        if not events:
            raise RuntimeError("stalled-simulation")
        was_paused = not computing and depth >= window
        previous_time = now
        now, sequence, action = heapq.heappop(events)
        if was_paused:
            backpressure += now - previous_time
        kind, name = action.split(":", 1)
        if kind == "compute":
            computing = False
            if name in f.invalid:
                wasted += 1
                continue
            height = f.nodes[name].height + 1
            state = f"state-{sequence}"
            f.add(state, name, height, f.context)
            tip = state
            values[state] = values[name] / 2
            completed[state] = now
            worker = min(range(8), key=workers.__getitem__)
            finish = max(now, workers[worker]) + F(2)
            workers[worker] = finish
            issued += 1
            serial += 1
            heapq.heappush(events, (finish, serial, "proof:" + state))
        elif name not in f.invalid:
            valid = injected or f.nodes[name].height != fail_height
            prior = set(f.certified)
            f.evidence(name, f.nodes[name].parent, f.context, valid)
            if not valid:
                injected = True
                wasted += len(f.invalid.intersection(completed))
                tip = max(f.certified, key=lambda k: f.nodes[k].height)
            for state in f.certified - prior:
                certified_at[state] = now
            head = max(f.certified, key=lambda k: f.nodes[k].height)
            f.release(head, require_real_proof=False)
        height = max(f.nodes[k].height for k in f.certified)
        trace.append(
            {
                "time": str(now),
                "computed_tip": f.nodes[tip].height,
                "certified_height": height,
                "invalid_nodes": len(f.invalid),
            }
        )
    final_weight = values[f.released]
    if final_weight**2 / 2 != F(1, 2 ** (2 * rounds + 1)):
        raise RuntimeError("wrong-synthetic-quadratic-target")
    latencies = sorted(certified_at[k] - completed[k] for k in certified_at if k != "genesis")
    return {
        "kind": "exact-discrete-event-simulation",
        "window": window,
        "rounds": rounds,
        "proof_workers": 8,
        "compute_seconds": "1/5",
        "prove_worker_seconds": "2",
        "capacity_upper_bound_per_second": "4",
        "time_to_certified_quality_seconds": str(now),
        "final_weight": str(final_weight),
        "backpressure_seconds": str(backpressure),
        "release_delay_seconds": "0",
        "admission_fixture_scope": "separate-original-stale-and-unavailable-client-cases",
        "quality_target_quadratic_gap": str(F(1, 2 ** (2 * rounds + 1))),
        "certified_per_second": str(F(rounds) / now),
        "p50_certificate_delay_seconds": str(latencies[(len(latencies) - 1) // 2]),
        "p95_certificate_delay_seconds": str(latencies[(95 * len(latencies) + 99) // 100 - 1]),
        "maximum_speculative_depth": max_depth,
        "rollback_count": f.rollbacks,
        "discarded_computations": wasted,
        "issued_proof_jobs": issued,
        "proving_work_worker_seconds": str(2 * issued),
        "trace": trace,
        "excluded_clients": [
            {
                "id": "slow-client",
                "start_round": 0,
                "head_round": 4,
                "age_limit": 2,
                "reason": client_admission(0, 4, 2, True),
            },
            {
                "id": "missing-state",
                "start_round": 4,
                "head_round": 4,
                "age_limit": 2,
                "reason": client_admission(4, 4, 2, False),
            },
        ],
        "limitations": [
            "Original synthetic halving objective; not a model-quality benchmark.",
            "Independent resources; no shared GPU contention or network simulation.",
            "Boolean evidence cannot satisfy an actual proof/release requirement.",
        ],
    }
