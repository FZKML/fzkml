"""Typed public API; mathematical reference code lives outside this package."""

from __future__ import annotations

from dataclasses import dataclass

from . import _native

CONTRACT_VERSION: str = _native.CONTRACT_VERSION
CONTRACT_SHA256: str = _native.CONTRACT_SHA256


@dataclass(frozen=True)
class CanonicalBatch:
    data: bytes

    def __post_init__(self) -> None:
        if type(self.data) is not bytes:
            raise TypeError("canonical input must be immutable bytes")
        _native.evaluate_batch(self.data)

    def evaluate(self) -> int:
        return _native.evaluate_batch(self.data)


@dataclass(frozen=True)
class ProofResult:
    output: int
    proof: bytes
    contract_version: str
    key_id: str
    witness_seconds: float
    proving_seconds: float


class ResearchSession:
    """Owns one ephemeral research keypair; no imported/untrusted verifying keys."""

    def __init__(self) -> None:
        self._session = _native.ResearchSession()

    @property
    def key_id(self) -> str:
        return self._session.key_id

    @property
    def parameters_id(self) -> str:
        return self._session.parameters_id

    def prove(self, batch: CanonicalBatch) -> ProofResult:
        output, proof, witness, proving = self._session.prove(batch.data)
        return ProofResult(output, proof, CONTRACT_VERSION, self.key_id, witness, proving)

    def verify(self, batch: CanonicalBatch, result: ProofResult) -> bool:
        if result.contract_version != CONTRACT_VERSION or result.key_id != self.key_id:
            return False
        return self._session.verify(batch.data, result.output, result.proof)
