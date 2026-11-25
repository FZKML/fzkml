"""Two-party durable-state abstraction and a separate lock-based implementation."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from dataclasses import asdict, dataclass, replace
from typing import Any


def require(condition: object, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


@dataclass(frozen=True)
class State:
    phase: str = "open"
    pending: tuple[tuple[str, str], ...] = ()
    accepted: tuple[tuple[str, str], ...] = ()
    shares: tuple[str, ...] = ()
    charged: int = 0
    releases: int = 0
    cached: str = ""
    version: int = 0
    head: str = "h0"


Event = tuple[str, str, str, str]


def release_bytes(accepted: tuple[tuple[str, str], ...]) -> str:
    return hashlib.sha256(json.dumps(["synthetic-round-v1", "h0", accepted]).encode()).hexdigest()


def invariant(state: State) -> None:
    require(
        state.phase in {"open", "frozen", "reserved", "released", "aborted"}
        and type(state.version) is int
        and 0 <= state.version <= 8,
        "invalid-phase-or-version",
    )
    require(
        type(state.charged) is int and type(state.releases) is int and 0 <= state.releases <= 1,
        "invalid-counter",
    )
    require(state.shares == tuple(sorted(set(state.shares))), "duplicate-or-unsorted-share")
    require(state.head == "h0", "conflicting-head")
    require(len(dict(state.pending)) == len(state.pending) <= 2, "duplicate-nullifier")
    require(set(dict(state.pending)) <= {"c0", "c1"}, "unauthorized-slot")
    require(state.releases <= 1 and state.charged in (0, 1), "duplicate-release-or-charge")
    require(not state.shares or state.charged == 1, "partial-reveal-before-reservation")
    require(set(state.shares) <= {"s0", "s1"}, "unknown-share")
    if state.phase == "open":
        require(
            not state.accepted and not state.charged and not state.shares,
            "premature-disclosure-state",
        )
    if state.phase in {"frozen", "reserved", "released"}:
        require(bool(state.accepted), "missing-frozen-cohort")
    if state.phase == "frozen":
        require(not state.charged and not state.shares, "frozen-before-reservation")
    if state.phase == "reserved":
        require(state.charged == 1, "missing-reservation")
    if state.accepted:
        require(
            tuple(k for k, _ in state.accepted) == ("c0", "c1") and state.accepted == state.pending,
            "inconsistent-accepted-history",
        )
    if state.phase == "released":
        require(
            state.accepted
            and state.shares == ("s0", "s1")
            and state.charged == 1
            and state.releases == 1
            and state.cached == release_bytes(state.accepted),
            "release-without-complete-state",
        )
    else:
        require(state.releases == 0 and state.cached == "", "premature-cached-release")


def model_step(state: State, event: Event, unsafe_release: bool = False) -> State:
    op, identity, payload, head = event
    if head != "h0":
        return state
    result = state
    if op == "admit" and identity in ("c0", "c1"):
        existing = dict(state.pending)
        if identity not in existing and state.phase == "open":
            result = replace(state, pending=tuple(sorted((*state.pending, (identity, payload)))))
    elif op == "freeze" and state.phase == "open" and len(state.pending) == 2:
        result = replace(state, phase="frozen", accepted=state.pending)
    elif op == "reserve" and state.phase == "frozen":
        result = replace(state, phase="reserved", charged=1)
    elif op == "share" and state.phase == "reserved" and identity in ("s0", "s1"):
        result = replace(state, shares=tuple(sorted(set(state.shares) | {identity})))
    elif op == "release":
        if state.phase == "reserved" and len(state.shares) == 2:
            result = replace(
                state, phase="released", releases=1, cached=release_bytes(state.accepted)
            )
        elif state.phase == "released" and unsafe_release:
            result = replace(state, releases=state.releases + 1)
    elif op == "timeout" and state.phase not in ("released", "aborted"):
        result = replace(state, phase="aborted")
    # restart is an identity operation only under authenticated latest atomic storage.
    if result != state:
        result = replace(result, version=state.version + 1)
    return result


ACTIONS: tuple[Event, ...] = (
    ("admit", "c0", "p0", "h0"),
    ("admit", "c0", "conflict", "h0"),
    ("admit", "c1", "p1", "h0"),
    ("admit", "c1", "p1", "wrong-head"),
    ("freeze", "", "", "h0"),
    ("reserve", "", "", "h0"),
    ("share", "s0", "", "h0"),
    ("share", "s1", "", "h0"),
    ("release", "", "", "h0"),
    ("timeout", "", "", "h0"),
    ("restart", "", "", "h0"),
)


def explore(max_states: int = 4096, unsafe_release: bool = False) -> dict[str, Any]:
    require(type(max_states) is int and 1 <= max_states <= 4096, "model-resource-bound")
    initial = State()
    queue: deque[tuple[State, tuple[Event, ...]]] = deque([(initial, ())])
    seen = {initial}
    edges = 0
    while queue:
        state, trace = queue.popleft()
        for action in ACTIONS:
            edges += 1
            candidate = model_step(state, action, unsafe_release)
            try:
                invariant(candidate)
            except ValueError:
                return {
                    "outcome": "failed",
                    "states": len(seen),
                    "edges": edges,
                    "counterexample": [list(e) for e in (*trace, action)],
                }
            if candidate not in seen:
                if len(seen) >= max_states or len(trace) >= 12:
                    return {
                        "outcome": "inconclusive",
                        "states": len(seen),
                        "edges": edges,
                        "counterexample": [],
                    }
                seen.add(candidate)
                queue.append((candidate, (*trace, action)))
    return {"outcome": "successful", "states": len(seen), "edges": edges, "counterexample": []}


class Authority:
    """Separate mutable reference, linearized by one trusted in-memory authority."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state = State()
        self.history: list[Event] = []

    def apply(self, event: Event) -> State:
        with self.lock:
            require(len(self.history) < 256, "reference-event-budget")
            op, identity, payload, head = event
            self.history.append(event)
            before = self.state
            values = asdict(before)
            pending = dict(before.pending)
            if head == "h0":
                if op == "admit" and identity in ("c0", "c1"):
                    if identity not in pending and before.phase == "open":
                        pending[identity] = payload
                        values["pending"] = tuple(sorted(pending.items()))
                elif op == "freeze" and before.phase == "open" and len(pending) == 2:
                    values["phase"], values["accepted"] = "frozen", before.pending
                elif op == "reserve" and before.phase == "frozen":
                    values["phase"], values["charged"] = "reserved", 1
                elif op == "share" and before.phase == "reserved" and identity in ("s0", "s1"):
                    values["shares"] = tuple(sorted(set(before.shares) | {identity}))
                elif op == "release" and before.phase == "reserved" and len(before.shares) == 2:
                    values.update(
                        phase="released", releases=1, cached=release_bytes(before.accepted)
                    )
                elif op == "timeout" and before.phase not in ("released", "aborted"):
                    values["phase"] = "aborted"
            result = State(**values)
            if result != before:
                result = replace(result, version=before.version + 1)
            invariant(result)
            self.state = result
            return result

    def snapshot(self) -> str:
        with self.lock:
            return json.dumps(asdict(self.state), sort_keys=True)

    @classmethod
    def restore(cls, payload: str, trusted_minimum_version: int) -> Authority:
        require(len(payload) <= 8192, "snapshot-resource-bound")
        data = json.loads(payload)
        data["pending"] = tuple(tuple(row) for row in data["pending"])
        data["accepted"] = tuple(tuple(row) for row in data["accepted"])
        data["shares"] = tuple(data["shares"])
        state = State(**data)
        invariant(state)
        require(state.version >= trusted_minimum_version, "rollback-below-trusted-head")
        result = cls()
        result.state = state
        return result


def replay(events: list[list[str]]) -> State:
    require(len(events) <= 64, "trace-resource-bound")
    authority = Authority()
    expected = State()
    for row in events:
        require(
            len(row) == 4 and all(isinstance(v, str) and len(v) <= 64 for v in row), "event-shape"
        )
        event: Event = (row[0], row[1], row[2], row[3])
        expected = model_step(expected, event)
        actual = authority.apply(event)
        require(actual == expected, "implementation-model-divergence")
        if event[0] == "restart":
            authority = Authority.restore(authority.snapshot(), expected.version)
    return authority.state


def classification(state: State) -> str:
    if state.phase == "released":
        return "released"
    if state.phase == "aborted":
        return "aborted-possible-disclosure" if state.charged else "aborted-before-disclosure"
    return "inconclusive"
