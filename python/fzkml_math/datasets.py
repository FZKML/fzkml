"""Original deterministic small synthetic records and entity/time/duplicate-safe splits."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Record:
    id: str
    entity: str
    source: str
    time: int
    x: int
    y: int
    duplicate_of: str | None = None


def synthetic(seed: int = 20261124) -> tuple[Record, ...]:
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("public-experiment-seed")
    rng = random.Random(seed)
    rows = []
    for entity in range(8):
        for time in (1, 5, 11):
            rows.append(
                Record(
                    f"synthetic:e{entity}-t{time}",
                    f"synthetic:e{entity}",
                    f"synthetic:source{entity % 2}",
                    time,
                    rng.randint(-16, 16),
                    rng.randint(-16, 16),
                )
            )
    original = rows[0]
    rows.append(
        Record(
            "synthetic:duplicate",
            original.entity,
            "synthetic:source1",
            6,
            original.x,
            original.y,
            original.id,
        )
    )
    return tuple(rows)


def representation_digest(rows: tuple[Record, ...]) -> str:
    # Binds a representation only, not truth, consent, completeness or sampling.
    return hashlib.sha256(
        json.dumps([asdict(r) for r in rows], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def split(
    rows: tuple[Record, ...], held_out: frozenset[str], train_cutoff: int, eval_cutoff: int
) -> dict[str, tuple[Record, ...]]:
    if (
        type(train_cutoff) is not int
        or type(eval_cutoff) is not int
        or train_cutoff > eval_cutoff
        or len({r.id for r in rows}) != len(rows)
    ):
        raise ValueError("split-time-or-record-identity")
    by_id = {r.id: r for r in rows}
    seen = set()
    train: list[Record] = []
    evaluation: list[Record] = []
    excluded: list[Record] = []
    for r in sorted(rows, key=lambda r: (r.time, r.id)):
        if (
            not all(v.startswith("synthetic:") for v in (r.id, r.entity, r.source))
            or type(r.time) is not int
            or type(r.x) is not int
            or type(r.y) is not int
        ):
            raise ValueError("synthetic-record-domain")
        if r.duplicate_of is not None:
            if r.duplicate_of not in by_id:
                raise ValueError("unknown-duplicate-parent")
            parent = by_id[r.duplicate_of]
            if (parent.x, parent.y) != (r.x, r.y):
                raise ValueError("duplicate-content-mismatch")
            excluded.append(r)
            continue
        # Repeated payloads also cannot cross the split under forged duplicate metadata.
        payload = (r.x, r.y)
        if (
            payload in seen
            or r.time > eval_cutoff
            or (r.entity not in held_out and r.time > train_cutoff)
        ):
            excluded.append(r)
            continue
        seen.add(payload)
        (evaluation if r.entity in held_out else train).append(r)
    return {"train": tuple(train), "evaluation": tuple(evaluation), "excluded": tuple(excluded)}
