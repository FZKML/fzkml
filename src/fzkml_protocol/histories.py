"""Connected histories with an explicit verifier and trusted selection service.

Hashes bind public complete state. They are not hiding commitments, signatures,
proofs, consensus, a durable ledger, or a certificate availability service.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .integer import Vector, vector


def digest(domain: str, value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(domain.encode() + b"\x00" + encoded).hexdigest()


def identifier(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is None:
        raise ValueError("public-identifier")


@dataclass(frozen=True)
class State:
    sid: str
    sequence: int
    policy_digest: str
    relation_digest: str
    model: Vector
    optimizer: tuple[int, ...]
    model_version: int
    key_epoch: int
    roster: tuple[str, ...]
    phase: str
    release_ids: tuple[str, ...]
    release_ledger_digest: str

    def __post_init__(self) -> None:
        identifier(self.sid)
        for counter in (self.sequence, self.model_version, self.key_epoch):
            if type(counter) is not int or not 0 <= counter <= 1000:
                raise ValueError("state-counter")
        for value in (self.policy_digest, self.relation_digest, self.release_ledger_digest):
            if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
                raise ValueError("state-digest")
        vector(self.model, 2**31 - 1)
        if self.optimizer != ():
            raise ValueError("optimizer-state-unsupported")
        if self.phase not in {"ready", "released"}:
            raise ValueError("history-phase-unsupported")
        if not isinstance(self.roster, tuple) or self.roster != ("C0", "C1", "C2", "C3"):
            raise ValueError("fixed-roster")
        if not isinstance(self.release_ids, tuple) or len(self.release_ids) > 1000:
            raise ValueError("release-ledger-shape")
        for release in self.release_ids:
            identifier(release)
        if len(set(self.release_ids)) != len(self.release_ids):
            raise ValueError("duplicate-release")
        if (
            len(self.release_ids) != self.sequence
            or self.release_ledger_digest != digest("fzkml-release-ledger-v1", self.release_ids)
            or (self.phase == "ready") != (self.sequence == 0)
        ):
            raise ValueError("release-ledger-state")

    @property
    def root(self) -> str:
        return digest("fzkml-complete-state-v1", asdict(self))


@dataclass(frozen=True)
class Certificate:
    sid: str
    sequence: int
    parent: str
    child: str
    relation_digest: str
    evidence_digest: str

    def __post_init__(self) -> None:
        identifier(self.sid)
        if type(self.sequence) is not int or not 1 <= self.sequence <= 1000:
            raise ValueError("certificate-sequence")
        for value in (self.parent, self.child, self.relation_digest, self.evidence_digest):
            if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
                raise ValueError("certificate-digest")

    @property
    def root(self) -> str:
        return digest("fzkml-transition-certificate-v1", asdict(self))


@dataclass(frozen=True)
class Assessment:
    local_validity: str
    connected: bool
    global_consistency: str
    certificate_availability: str
    liveness: str
    reason: str


class TrustedLedger:
    """Thread-safe in-memory ideal single-writer CAS. No persistence/consensus."""

    def __init__(self, genesis: State):
        self.genesis = genesis.root
        self._successors: dict[str, str] = {}
        self._lock = threading.Lock()

    def select(self, genesis: str, edges: list[tuple[str, str]]) -> bool:
        with self._lock:
            if genesis != self.genesis:
                return False
            expected = genesis
            for parent, child in edges:
                if parent != expected or parent == child:
                    return False
                expected = child
            pending = dict(self._successors)
            for parent, child in edges:
                if parent in pending and pending[parent] != child:
                    return False
                pending[parent] = child
            self._successors = pending
            return True


def assess(
    genesis: State,
    states: tuple[State, ...],
    certificate_ids: tuple[str, ...],
    available: Mapping[str, Certificate],
    verifier: Callable[[Certificate], bool],
    ledger: TrustedLedger | None = None,
) -> Assessment:
    def rejected(reason: str) -> Assessment:
        return Assessment("invalid", False, "unresolved", "available", "not-guaranteed", reason)

    if not states or len(states) > 1001 or len(certificate_ids) != len(states) - 1:
        return rejected("history-shape")
    if states[0] != genesis:
        return rejected("untrusted-genesis")
    edges = []
    for index, (parent, child) in enumerate(zip(states, states[1:], strict=False)):
        certificate = available.get(certificate_ids[index])
        if certificate is None:
            return Assessment(
                "unavailable", False, "unresolved", "withheld", "stalled", "certificate-unavailable"
            )
        if certificate.root != certificate_ids[index]:
            return rejected("certificate-content-mismatch")
        if (
            certificate.parent != parent.root
            or certificate.child != child.root
            or certificate.sid != parent.sid
            or child.sid != parent.sid
            or certificate.sequence != child.sequence
            or child.sequence != parent.sequence + 1
            or certificate.relation_digest != parent.relation_digest
            or child.relation_digest != parent.relation_digest
            or child.policy_digest != parent.policy_digest
            or child.key_epoch != parent.key_epoch
            or child.model_version != parent.model_version + 1
            or child.roster != parent.roster
            or child.phase != "released"
            or child.release_ids[:-1] != parent.release_ids
            or len(child.release_ids) != len(parent.release_ids) + 1
        ):
            return rejected("disconnected-or-incompatible-state")
        try:
            if verifier(certificate) is not True:
                return rejected("local-certificate-invalid")
        except Exception:
            return rejected("verifier-failure")
        edges.append((parent.root, child.root))
    if ledger is not None and not ledger.select(genesis.root, edges):
        return Assessment(
            "valid", True, "conflict", "available", "not-guaranteed", "ledger-conflict"
        )
    return Assessment(
        "valid",
        True,
        "ledger-selected" if ledger else "unresolved",
        "available",
        "observed-complete",
        "trusted-ledger-required-for-uniqueness"
        if ledger is None
        else "selected-under-trusted-single-writer-assumption",
    )
