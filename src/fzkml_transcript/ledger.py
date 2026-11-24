"""Durable synthetic observer ledger with declared basic-composition budgets.

The journal is a local conformance reference. External authenticated durability,
mechanism theorems and complete-view simulation are not implemented here.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, BinaryIO, Literal

from .algebra import exact
from .entropy import EntropyPolicy

Classification = Literal[
    "accounted-release", "post-processing", "computationally-hidden", "explicitly-unprotected"
]
KINDS = {
    "aggregate",
    "participation",
    "proof-public-input",
    "diagnostic",
    "failure",
    "evaluation",
    "recovery",
}


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def identifier(value: str) -> None:
    if not re.fullmatch(r"synthetic:[A-Za-z0-9._:-]{1,100}", value):
        raise ValueError("synthetic identifier required")


@dataclass(frozen=True)
class MechanismContract:
    mechanism_id: str
    epsilon: Fraction
    delta: Fraction
    finite_arithmetic_theorem: str
    entropy_reference: str
    availability: str = "unavailable"
    entropy_policy: EntropyPolicy | None = None

    def record(self) -> dict[str, Any]:
        identifier(self.mechanism_id)
        if exact(self.epsilon) < 0 or not 0 <= exact(self.delta) < 1:
            raise ValueError("invalid declared mechanism cost")
        if self.availability == "synthetic-conformance-only":
            if self.entropy_policy is None:
                raise ValueError("honest entropy dependency unavailable")
            self.entropy_policy.require_available()
        return {
            "id": self.mechanism_id,
            "epsilon": str(self.epsilon),
            "delta": str(self.delta),
            "finite_arithmetic_theorem": self.finite_arithmetic_theorem,
            "entropy_reference": self.entropy_reference,
            "availability": self.availability,
            "entropy_policy": asdict(self.entropy_policy) if self.entropy_policy else None,
        }


@dataclass(frozen=True)
class LedgerPolicy:
    observer: str
    privacy_unit: str
    policy_digest: str
    fixed_cohort: tuple[str, ...]
    epsilon_limit: Fraction
    delta_limit: Fraction
    mechanisms: tuple[MechanismContract, ...]

    def record(self) -> dict[str, Any]:
        identifier(self.observer)
        if self.privacy_unit != "synthetic-record":
            raise ValueError("synthetic-record reference scope required")
        if not re.fullmatch(r"[a-f0-9]{64}", self.policy_digest):
            raise ValueError("policy digest required")
        if not self.fixed_cohort or len(set(self.fixed_cohort)) != len(self.fixed_cohort):
            raise ValueError("fixed unique cohort required; no amplification implemented")
        for client in self.fixed_cohort:
            identifier(client)
        if exact(self.epsilon_limit) < 0 or not 0 <= exact(self.delta_limit) < 1:
            raise ValueError("invalid composition budget")
        ids = [m.mechanism_id for m in self.mechanisms]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate mechanism contract")
        return {
            "version": 1,
            "mode": "synthetic-conformance-only",
            "observer": self.observer,
            "privacy_unit": self.privacy_unit,
            "policy_digest": self.policy_digest,
            "fixed_cohort": sorted(self.fixed_cohort),
            "amplification": "none",
            "epsilon_limit": str(self.epsilon_limit),
            "delta_limit": str(self.delta_limit),
            "mechanisms": [m.record() for m in self.mechanisms],
        }


@dataclass(frozen=True)
class Observation:
    event_id: str
    output_id: str
    kind: str
    classification: Classification
    payload_digest: str
    justification: str
    mechanism_id: str | None = None
    application_id: str | None = None
    parents: tuple[str, ...] = ()
    no_new_protected_access: bool = False
    crypto_kappa: str = "0"

    def record(self) -> dict[str, Any]:
        return asdict(self) | {"parents": list(self.parents)}


class ReferenceAccountant:
    def __init__(
        self,
        path: Path,
        policy: LedgerPolicy,
        *,
        create: bool = False,
        expected_root: str | None = None,
    ):
        self.path = path
        self.policy = policy.record()
        self._anchor = expected_root
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "r+b") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                self._append(stream, {"header": self.policy})
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        # Recovery never initializes a missing/empty journal or resets its budget.
        with self._locked() as stream:
            self._read(stream)

    @contextmanager
    def _locked(self) -> Iterator[BinaryIO]:
        fd = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW)
        with os.fdopen(fd, "r+b") as stream:
            if os.fstat(stream.fileno()).st_nlink != 1:
                raise ValueError("single-link journal required")
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield stream
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    @staticmethod
    def _append(stream: BinaryIO, row: dict[str, Any]) -> None:
        stream.seek(0, os.SEEK_END)
        payload = canonical(row)
        if stream.tell() + len(payload) > 4_000_000:
            raise ValueError("reference journal size limit")
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())

    def _read(self, stream: BinaryIO) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        stream.seek(0)
        raw = stream.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("reference journal size limit")
        try:
            lines = raw.splitlines(keepends=True)
            records = [json.loads(line) for line in lines]
            if any(canonical(row) != line for row, line in zip(records, lines, strict=True)):
                raise ValueError("noncanonical or truncated journal")
            if not records or records[0] != {"header": self.policy}:
                raise ValueError("journal policy/observer mismatch")
            state: dict[str, Any] = {
                "epsilon": Fraction(0),
                "delta": Fraction(0),
                "crypto_kappa": Fraction(0),
                "unprotected": False,
                "outputs": {},
                "applications": set(),
                "events": {},
            }
            previous = digest(records[0])
            roots = {previous}
            for seq, row in enumerate(records[1:], 1):
                if set(row) != {"sequence", "previous", "observation", "hash"}:
                    raise ValueError("invalid journal row")
                core = {k: v for k, v in row.items() if k != "hash"}
                if (
                    row["sequence"] != seq
                    or row["previous"] != previous
                    or digest(core) != row["hash"]
                ):
                    raise ValueError("journal hash/sequence mismatch")
                self._apply(state, row["observation"])
                previous = row["hash"]
                roots.add(previous)
            if self._anchor is not None and self._anchor not in roots:
                raise ValueError("journal rollback or wrong trusted anchor")
            self._anchor = previous
            state["root"] = previous
            return records, state
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("malformed reference journal") from error

    def _apply(self, state: dict[str, Any], row: dict[str, Any]) -> None:
        if set(row) != set(Observation.__dataclass_fields__):
            raise ValueError("unclassified observation fields")
        for field in ("event_id", "output_id"):
            identifier(row[field])
        if row["kind"] not in KINDS or not row["justification"]:
            raise ValueError("observation kind/justification required")
        if len(row["justification"]) > 256 or any(ord(c) < 32 for c in row["justification"]):
            raise ValueError("bounded public justification reference required")
        if not re.fullmatch(r"[a-f0-9]{64}", row["payload_digest"]):
            raise ValueError("payload digest required; raw data prohibited")
        if row["event_id"] in state["events"]:
            raise ValueError("duplicate event in journal")
        if not isinstance(row["parents"], list) or len(set(row["parents"])) != len(row["parents"]):
            raise ValueError("unique parent outputs required")
        if any(parent not in state["outputs"] for parent in row["parents"]):
            raise ValueError("unknown prior output")
        classification = row["classification"]
        kappa = Fraction(row["crypto_kappa"])
        if not 0 <= kappa <= 1:
            raise ValueError("invalid separate computational advantage")
        if classification == "accounted-release":
            if state["unprotected"]:
                raise ValueError("unprotected transcript blocks a protected-release claim")
            contracts = {m["id"]: m for m in self.policy["mechanisms"]}
            contract = contracts.get(row["mechanism_id"])
            if (
                contract is None
                or contract["availability"] != "synthetic-conformance-only"
                or not contract["finite_arithmetic_theorem"]
                or not contract["entropy_reference"]
            ):
                raise ValueError("mechanism/theorem/entropy dependency unavailable")
            if row["application_id"] is None:
                raise ValueError("unique mechanism application required")
            identifier(row["application_id"])
            if row["application_id"] in state["applications"]:
                raise ValueError("reused mechanism application; replay the original event instead")
            eps = Fraction(contract["epsilon"])
            delta = Fraction(contract["delta"])
            if state["epsilon"] + eps > Fraction(self.policy["epsilon_limit"]) or state[
                "delta"
            ] + delta > Fraction(self.policy["delta_limit"]):
                raise ValueError("privacy composition budget exhausted")
            state["epsilon"] += eps
            state["delta"] += delta
            state["applications"].add(row["application_id"])
        elif classification == "post-processing":
            if row["no_new_protected_access"] is not True:
                raise ValueError("post-processing cannot read new protected information")
            if not row["parents"] and row["justification"] != "public-context-only":
                raise ValueError("post-processing needs prior outputs or fixed public context")
            if row["justification"] == "identical-redelivery":
                if (
                    len(row["parents"]) != 1
                    or state["outputs"][row["parents"][0]] != row["payload_digest"]
                ):
                    raise ValueError("redelivery payload differs from stored output")
        elif classification == "computationally-hidden":
            if not row["parents"] or row["no_new_protected_access"] is not True:
                raise ValueError("classify all public inputs before claiming hidden proof/payload")
            if kappa == 0:
                raise ValueError("explicit nonzero declared computational bound required")
        elif classification == "explicitly-unprotected":
            state["unprotected"] = True
        else:
            raise ValueError("unknown observation classification")
        if classification != "accounted-release" and (row["application_id"] or row["mechanism_id"]):
            raise ValueError("non-mechanism observation cannot hide a mechanism application")
        if classification != "computationally-hidden" and kappa:
            raise ValueError("computational advantage is not a DP cost")
        existing = state["outputs"].get(row["output_id"])
        if existing is not None and (
            classification != "post-processing"
            or row["justification"] != "identical-redelivery"
            or existing != row["payload_digest"]
        ):
            raise ValueError("output identity collision")
        state["crypto_kappa"] += kappa
        state["outputs"][row["output_id"]] = row["payload_digest"]
        state["events"][row["event_id"]] = row

    def authorize(self, observation: Observation) -> str:
        """Persist authorization before the caller could publish; no publisher is supplied."""
        row = observation.record()
        with self._locked() as stream:
            records, state = self._read(stream)
            old = state["events"].get(observation.event_id)
            if old is not None:
                if old != row:
                    raise ValueError("conflicting event retry")
                return str(
                    next(
                        r["hash"]
                        for r in records[1:]
                        if r["observation"]["event_id"] == observation.event_id
                    )
                )
            self._apply(state, row)
            core = {"sequence": len(records), "previous": state["root"], "observation": row}
            receipt = digest(core)
            self._append(stream, core | {"hash": receipt})
            self._anchor = receipt
            return receipt

    def summary(self) -> dict[str, Any]:
        with self._locked() as stream:
            _, state = self._read(stream)
        return {
            "observer": self.policy["observer"],
            "events": len(state["events"]),
            "epsilon": str(state["epsilon"]),
            "delta": str(state["delta"]),
            "separate_crypto_kappa": str(state["crypto_kappa"]),
            "unprotected_transcript": state["unprotected"],
            "root": state["root"],
            "assurance": "synthetic declared-contract accounting only; no deployed DP guarantee",
        }
