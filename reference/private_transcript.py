"""Independent stdlib transcript/commitment reference; never imports Rust or torch."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "specs/private-transition-v1.json").read_text())


def digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def identifier(name: str) -> bytes:
    return digest(SPEC[name + "_preimage"].encode())


@dataclass(frozen=True)
class Context:
    session: bytes
    round: int
    parent: bytes
    roster: tuple[bytes, bytes, bytes]
    counts: tuple[int, int, int]
    model_version: bytes
    data_policy: bytes
    optimizer: bytes
    relation: bytes
    contract: bytes
    key_id: bytes

    def encode(self) -> bytes:
        identifiers = (
            self.parent,
            self.model_version,
            self.data_policy,
            self.optimizer,
            self.relation,
            self.contract,
            self.key_id,
        )
        if (
            len(self.session) != 16
            or self.session == bytes(16)
            or any(len(v) != 32 for v in identifiers)
        ):
            raise ValueError("identifier-size")
        if type(self.round) is not int or not 1 <= self.round <= 2**32 - 1:
            raise ValueError("round")
        if (
            len(self.roster) != 3
            or len(set(self.roster)) != 3
            or any(len(v) != 16 or v == bytes(16) for v in self.roster)
        ):
            raise ValueError("roster")
        if len(self.counts) != 3 or any(type(n) is not int or not 1 <= n <= 4 for n in self.counts):
            raise ValueError("count")
        if (self.model_version, self.data_policy, self.optimizer) != (
            identifier("model_id"),
            identifier("data_policy"),
            identifier("optimizer_id"),
        ):
            raise ValueError("unsupported-policy")
        if self.relation != digest(
            (ROOT / "specs/numeric-contract-v1.json").read_bytes()
        ) or self.contract != digest((ROOT / "specs/private-transition-v1.json").read_bytes()):
            raise ValueError("unsupported-version")
        return (
            b"FZKCTX01"
            + self.session
            + struct.pack("<Q", self.round)
            + self.parent
            + b"".join(self.roster)
            + struct.pack("<III", *self.counts)
            + b"".join(identifiers[1:])
        )


def synthetic(key_id: bytes = bytes([5]) * 32) -> Context:
    return Context(
        bytes([7]) * 16,
        1,
        digest(b"synthetic-genesis"),
        (bytes([1]) * 16, bytes([2]) * 16, bytes([3]) * 16),
        (1, 2, 1),
        identifier("model_id"),
        identifier("data_policy"),
        identifier("optimizer_id"),
        digest((ROOT / "specs/numeric-contract-v1.json").read_bytes()),
        digest((ROOT / "specs/private-transition-v1.json").read_bytes()),
        key_id,
    )


def commitment(domain: bytes, blinding: bytes, context: Context, payload: bytes) -> bytes:
    if domain not in (b"FZKMOD01", b"FZKDAT01") or len(blinding) != 32:
        raise ValueError("commitment-format")
    if len(payload) != (8 if domain == b"FZKMOD01" else 48):
        raise ValueError("commitment-payload")
    return digest(domain + blinding + digest(context.encode()) + payload)


def public_vector() -> dict[str, object]:
    context = synthetic()
    model = commitment(b"FZKMOD01", bytes([11]) * 32, context, struct.pack("<q", 8))
    data = struct.pack("<qqqqqq", 16, 16, -8, -16, 24, 8)
    data_root = commitment(b"FZKDAT01", bytes([19]) * 32, context, data)
    statement = b"FZKSTA01" + context.encode() + model + data_root + struct.pack("<q", 9)
    return {
        "contract_version": "fzk-private-1.0.0",
        "fixture_version": "private-transcript-v1",
        "context_hex": context.encode().hex(),
        "context_sha256": digest(context.encode()).hex(),
        "model_commitment": model.hex(),
        "data_commitment": data_root.hex(),
        "statement_hex": statement.hex(),
        "statement_sha256": digest(statement).hex(),
        "backend_id": identifier("backend_id").hex(),
        "public_test_openings": {
            "model_blinding_byte": 11,
            "data_blinding_byte": 19,
            "warning": "Published deterministic test openings; never operational randomness.",
        },
    }


def leakage_example() -> dict[str, object]:
    context = synthetic()
    candidates = list(range(-4, 5))
    target = 3
    deterministic = digest(b"FZKMOD01" + digest(context.encode()) + struct.pack("<q", target))
    recovered = [
        v
        for v in candidates
        if digest(b"FZKMOD01" + digest(context.encode()) + struct.pack("<q", v)) == deterministic
    ]
    public_nonce = bytes([11]) * 32
    published = commitment(b"FZKMOD01", public_nonce, context, struct.pack("<q", target))
    recovered_with_public_nonce = [
        v
        for v in candidates
        if commitment(b"FZKMOD01", public_nonce, context, struct.pack("<q", v)) == published
    ]
    return {
        "candidate_count": len(candidates),
        "target": target,
        "deterministic_root_recovered": recovered,
        "published_blinding_recovered": recovered_with_public_nonce,
        "naive_concatenation_collision": b"a" + b"bc" == b"ab" + b"c",
        "limitation": (
            "Exact enumeration counterexamples only; no empirical proof of hiding, "
            "collision resistance, SNARK security or DP."
        ),
    }
