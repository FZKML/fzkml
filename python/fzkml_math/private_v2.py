"""Independent public-test byte and arithmetic oracle for S01's v2 candidate.

No proof verification is implemented here. A previous statement must already
have been accepted by the real verifier before applying the lineage predicate.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from .numeric import decode, evaluate

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SHA256 = "820850561fb327bd6c267ca5fc1c31078a20e05ed8b32b77c6775161572a9cd3"


def digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def configuration(name: str) -> bytes:
    preimages = {
        "model": "fzkml.model.linear-1x1.no-bias.v1",
        "preprocessing": "fzkml.preprocessing.identity.v1",
        "initialization": "fzkml.initialization.authorized-parent-value.v1",
        "data_policy": "fzkml.data.synthetic-identity-three-client.v1",
        "optimizer": "fzkml.optimizer.fixed16.sgd-1of4.v1",
    }
    return digest(preimages[name].encode())


@dataclass(frozen=True)
class ContextV2:
    session: bytes
    round: int
    parent_value: int
    parent: bytes
    roster: tuple[bytes, bytes, bytes]
    counts: tuple[int, int, int]
    model_version: bytes
    preprocessing: bytes
    initialization: bytes
    local_step_count: int
    data_policy: bytes
    optimizer: bytes
    relation: bytes
    contract: bytes
    key_id: bytes

    def encode(self) -> bytes:
        ids = (
            self.parent,
            self.model_version,
            self.preprocessing,
            self.initialization,
            self.data_policy,
            self.optimizer,
            self.relation,
            self.contract,
            self.key_id,
        )
        if (
            type(self.session) is not bytes
            or len(self.session) != 16
            or self.session == bytes(16)
            or any(type(v) is not bytes or len(v) != 32 for v in ids)
        ):
            raise ValueError("identifier-domain")
        if (
            type(self.round) is not int
            or not 1 <= self.round <= 2**32 - 1
            or type(self.parent_value) is not int
            or not -80 <= self.parent_value <= 80
        ):
            raise ValueError("round-or-parent-format-domain")
        if (
            type(self.roster) is not tuple
            or len(self.roster) != 3
            or len(set(self.roster)) != 3
            or any(type(v) is not bytes or len(v) != 16 or v == bytes(16) for v in self.roster)
        ):
            raise ValueError("ordered-roster-domain")
        if (
            type(self.counts) is not tuple
            or len(self.counts) != 3
            or any(type(v) is not int or not 1 <= v <= 4 for v in self.counts)
            or type(self.local_step_count) is not int
            or self.local_step_count != 1
        ):
            raise ValueError("counts-or-local-step")
        expected = tuple(
            configuration(n)
            for n in ("model", "preprocessing", "initialization", "data_policy", "optimizer")
        )
        if (
            (
                self.model_version,
                self.preprocessing,
                self.initialization,
                self.data_policy,
                self.optimizer,
            )
            != expected
            or self.relation != digest((ROOT / "specs/numeric-contract-v1.json").read_bytes())
            or self.contract.hex() != CONTRACT_SHA256
        ):
            raise ValueError("unsupported-v2-configuration")
        result = (
            b"FZKCTX02"
            + self.session
            + struct.pack("<Qq", self.round, self.parent_value)
            + self.parent
            + b"".join(self.roster)
            + struct.pack("<III", *self.counts)
            + b"".join(ids[1:4])
            + struct.pack("<I", self.local_step_count)
            + b"".join(ids[4:])
        )
        if len(result) != 392:
            raise AssertionError("v2-context-layout")
        return result

    @classmethod
    def decode(cls, raw: bytes) -> ContextV2:
        if type(raw) is not bytes or len(raw) != 392 or raw[:8] != b"FZKCTX02":
            raise ValueError("canonical-context-v2")
        round_id, parent_value = struct.unpack_from("<Qq", raw, 24)
        result = cls(
            raw[8:24],
            round_id,
            parent_value,
            raw[40:72],
            (raw[72:88], raw[88:104], raw[104:120]),
            struct.unpack_from("<III", raw, 120),
            raw[132:164],
            raw[164:196],
            raw[196:228],
            struct.unpack_from("<I", raw, 228)[0],
            raw[232:264],
            raw[264:296],
            raw[296:328],
            raw[328:360],
            raw[360:392],
        )
        if result.encode() != raw:
            raise ValueError("noncanonical-context-v2")
        return result


def synthetic(parent_value: int = 8) -> ContextV2:
    return ContextV2(
        bytes([7]) * 16,
        1,
        parent_value,
        digest(b"synthetic-genesis"),
        (bytes([1]) * 16, bytes([2]) * 16, bytes([3]) * 16),
        (1, 2, 1),
        configuration("model"),
        configuration("preprocessing"),
        configuration("initialization"),
        1,
        configuration("data_policy"),
        configuration("optimizer"),
        digest((ROOT / "specs/numeric-contract-v1.json").read_bytes()),
        bytes.fromhex(CONTRACT_SHA256),
        bytes([5]) * 32,
    )


@dataclass(frozen=True)
class StatementV2:
    context: ContextV2
    model_commitment: bytes
    data_commitment: bytes
    output: int

    def encode(self) -> bytes:
        if (
            any(
                type(v) is not bytes or len(v) != 32
                for v in (self.model_commitment, self.data_commitment)
            )
            or type(self.output) is not int
            or not -80 <= self.output <= 80
        ):
            raise ValueError("statement-domain")
        return (
            b"FZKSTA02"
            + self.context.encode()
            + self.model_commitment
            + self.data_commitment
            + struct.pack("<q", self.output)
        )

    @classmethod
    def decode(cls, raw: bytes) -> StatementV2:
        if type(raw) is not bytes or len(raw) != 472 or raw[:8] != b"FZKSTA02":
            raise ValueError("canonical-statement-v2")
        result = cls(
            ContextV2.decode(raw[8:400]),
            raw[400:432],
            raw[432:464],
            struct.unpack_from("<q", raw, 464)[0],
        )
        result.encode()
        return result


def arithmetic(context: ContextV2, batch: bytes) -> dict[str, int | list[int]]:
    context.encode()
    w, _, _, counts = decode(batch)
    if w != context.parent_value or tuple(counts) != context.counts:
        raise ValueError("parent-or-count-binding")
    return evaluate(batch)


def public_test_commitment(
    domain: bytes, blinding: bytes, context: ContextV2, payload: bytes
) -> bytes:
    """Published test openings only; never an operational blinding generator."""
    if (
        domain not in (b"FZKMOD02", b"FZKDAT02")
        or type(blinding) is not bytes
        or len(blinding) != 32
        or len(payload) != (8 if domain == b"FZKMOD02" else 48)
    ):
        raise ValueError("test-opening-format")
    return digest(domain + blinding + digest(context.encode()) + payload)


def require_next(previous: StatementV2, next_context: ContextV2) -> None:
    previous.encode()
    next_context.encode()
    if (
        next_context.parent != digest(previous.encode())
        or next_context.parent_value != previous.output
        or next_context.round != previous.context.round + 1
    ):
        raise ValueError("stale-or-wrong-parent")
    for name in (
        "session",
        "roster",
        "model_version",
        "preprocessing",
        "initialization",
        "local_step_count",
        "data_policy",
        "optimizer",
        "relation",
        "contract",
        "key_id",
    ):
        if getattr(previous.context, name) != getattr(next_context, name):
            raise ValueError("pinned-lineage-configuration")


def envelope_layout(statement: StatementV2, opaque_proof: bytes) -> bytes:
    """Structural framing only. Arbitrary 128-byte input is NOT a valid proof."""
    if type(opaque_proof) is not bytes or len(opaque_proof) != 128:
        raise ValueError("opaque-proof-size")
    backend = digest(b"fzkml.backend.ark-groth16-0.5.0.bn254.private-v2.local-research")
    return (
        b"FZKPRF02\x02\x00\x00\x00"
        + backend
        + struct.pack("<I", 472)
        + statement.encode()
        + struct.pack("<I", 128)
        + opaque_proof
    )
