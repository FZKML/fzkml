"""Trusted plaintext ideal-join reference with entity-local caps, not cryptographic PSI."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from fractions import Fraction as F
from typing import Any

from .data_lineage import ORGS, Row, digest


@dataclass(frozen=True)
class JoinPolicy:
    cohort: tuple[str, ...] = ("synthetic:p0", "synthetic:p1", "synthetic:p2", "synthetic:p3")
    cap: int = 2
    clip: int = 3
    denominator: int = 8
    purpose: str = "synthetic:clipped-joined-sum"
    recipient: str = "synthetic:analyst"
    entity_map: tuple[tuple[str, str], ...] = ()
    unit: str = "cm"

    def validate(self) -> None:
        if (
            type(self.cohort) is not tuple
            or len(set(self.cohort)) != len(self.cohort)
            or not 1 <= len(self.cohort) <= 8
            or any(type(e) is not str or not e.startswith("synthetic:") for e in self.cohort)
            or any(type(v) is not int or v <= 0 for v in (self.cap, self.clip, self.denominator))
            or self.cap > 4
            or self.clip > 8
            or self.denominator != self.cap * len(self.cohort)
            or self.purpose != "synthetic:clipped-joined-sum"
            or self.recipient != "synthetic:analyst"
            or self.unit != "cm"
            or type(self.entity_map) is not tuple
            or any(
                type(pair) is not tuple
                or len(pair) != 2
                or type(pair[0]) is not str
                or not pair[0].startswith("synthetic:")
                or pair[1] not in self.cohort
                for pair in self.entity_map
            )
            or len({pair[0] for pair in self.entity_map}) != len(self.entity_map)
        ):
            raise ValueError("join-fixed-public-policy")

    def sensitivity(self, adjacency: str) -> F:
        self.validate()
        if adjacency not in ("add-remove-entity", "replace-entity"):
            raise ValueError("entity-adjacency")
        return F(
            self.cap * self.clip * (2 if adjacency == "replace-entity" else 1), self.denominator
        )


def authorized_join(
    rows: tuple[Row, ...],
    policy: JoinPolicy,
    *,
    recipient: str,
    purpose: str,
    require_private_psi: bool = False,
) -> dict[str, Any]:
    policy.validate()
    if require_private_psi:
        raise ValueError("cryptographic-PSI-backend-unavailable")
    if purpose != policy.purpose or recipient not in (
        policy.recipient,
        "synthetic:trusted-operator",
    ):
        raise ValueError("unauthorized-join-output")
    if len(rows) > 96:
        raise ValueError("bounded-join-input")
    grouped: dict[str, dict[str, list[Row]]] = {e: {o: [] for o in ORGS} for e in policy.cohort}
    seen = set()
    for r in rows:
        r.validate()
        if (r.org, r.id) in seen:
            raise ValueError("duplicate-source-row-identity")
        seen.add((r.org, r.id))
        canonical_entity = dict(policy.entity_map).get(r.entity, r.entity)
        if canonical_entity not in grouped:
            raise ValueError("entity-outside-fixed-authorized-cohort")
        grouped[canonical_entity][r.org].append(r)
        if len(grouped[canonical_entity][r.org]) > 8:
            raise ValueError("bounded-per-entity-input-multiplicity")
    values = []
    counts = {}
    dropped = 0
    for entity in policy.cohort:
        inputs = [sorted(grouped[entity][o], key=lambda r: r.id) for o in ORGS]
        matches = list(itertools.product(*inputs))
        counts[entity] = len(matches)
        chosen = matches[: policy.cap]
        dropped += len(matches) - len(chosen)
        contribution = [
            max(-policy.clip, min(policy.clip, sum(r.value for r in combination)))
            for combination in chosen
        ]
        values.extend(contribution + [0] * (policy.cap - len(contribution)))
    output = F(sum(values), policy.denominator)
    # The public functionality exports no identifiers, unmatched rows, or debug cardinalities.
    result = {
        "public_output": {
            "value": str(output),
            "function": "fixed-public-denominator-clipped-entity-join",
        },
        "privileged_synthetic_diagnostics": {
            "matched_pairs": counts,
            "dropped_by_cap": dropped,
            "slot_values": values,
            "entity_count": len(grouped),
        },
        "policy_digest": digest("join-policy", policy.__dict__),
        "assurance": "trusted-plaintext-reference-not-PSI-or-DP",
    }
    if recipient != "synthetic:trusted-operator":
        del result["privileged_synthetic_diagnostics"]
    return result


def binary_correspondence() -> dict[str, Any]:
    equal = {(0, 0): F(1, 2), (1, 1): F(1, 2)}
    opposite = {(0, 1): F(1, 2), (1, 0): F(1, 2)}

    def marginals(law: dict[tuple[int, int], F]) -> tuple[tuple[F, F], tuple[F, F]]:
        return tuple(
            tuple(sum((v for pair, v in law.items() if pair[i] == j), F(0)) for j in range(2))
            for i in range(2)
        )  # type: ignore[return-value]

    return {
        "equal": equal,
        "opposite": opposite,
        "same_marginals": marginals(equal) == marginals(opposite),
        "equal_predictor": (0, 1),
        "opposite_predictor": (1, 0),
        "cross_world_prediction_error": F(1),
        "identification": "missing-correspondence-not-identifiable-from-unpaired-marginals",
    }
