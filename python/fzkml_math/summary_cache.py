"""Exact frozen-feature mean-ridge statistics and trusted local cache, not a proof backend."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from .data_lineage import canonical, digest


@dataclass(frozen=True)
class FeatureModel:
    version: str = "affine-rational-1"
    gain: F = F(1)
    ridge: F = F(1)

    def validate(self) -> None:
        if (
            self.version not in ("affine-rational-1", "affine-rational-2")
            or type(self.gain) is not F
            or not 0 < self.gain <= 2
            or type(self.ridge) is not F
            or self.ridge <= 0
        ):
            raise ValueError("frozen-rational-feature-model")

    @property
    def descriptor(self) -> dict[str, str]:
        self.validate()
        return {
            "version": self.version,
            "gain": str(self.gain),
            "ridge": str(self.ridge),
            "feature_map": "[1,gain*x]",
            "objective": "mean-half-squared-loss-plus-ridge",
        }

    def feature(self, x: F) -> tuple[F, F]:
        self.validate()
        if type(x) is not F or abs(x) > 2:
            raise ValueError("bounded-feature-input")
        return F(1), self.gain * x


def examples(n: int) -> tuple[tuple[F, F], ...]:
    if type(n) is not int or not 1 <= n <= 4096:
        raise ValueError("bounded-synthetic-size")
    return tuple((F((i * 7) % 33 - 16, 16), F((i * 11) % 33 - 16, 16)) for i in range(n))


def stats(
    rows: tuple[tuple[F, F], ...], model: FeatureModel, grid: F | None = None
) -> dict[str, str | int]:
    if not rows or len(rows) > 4096:
        raise ValueError("nonempty-bounded-records")
    s00 = s01 = s11 = t0 = t1 = q = F(0)
    if grid is not None and grid != F(1, 2):
        raise ValueError("declared-approximation-grid")
    for x, y in rows:
        if type(y) is not F or abs(y) > 2:
            raise ValueError("bounded-label")
        a, b = model.feature(x)
        if grid is not None:
            b, y = F(round(b / grid)) * grid, F(round(y / grid)) * grid
        s00 += a * a
        s01 += a * b
        s11 += b * b
        t0 += a * y
        t1 += b * y
        q += y * y
    return {
        "n": len(rows),
        "s00": str(s00),
        "s01": str(s01),
        "s11": str(s11),
        "t0": str(t0),
        "t1": str(t1),
        "q": str(q),
    }


def evaluate(summary: dict[str, Any], theta: tuple[F, F], model: FeatureModel) -> dict[str, Any]:
    model.validate()
    if len(theta) != 2 or any(type(v) is not F or abs(v) > 2 for v in theta):
        raise ValueError("bounded-head-parameters")
    if (
        set(summary) != {"n", "s00", "s01", "s11", "t0", "t1", "q"}
        or type(summary["n"]) is not int
        or not 0 < summary["n"] <= 4096
    ):
        raise ValueError("summary-schema")
    s00, s01, s11, t0, t1, q = (F(summary[k]) for k in ("s00", "s01", "s11", "t0", "t1", "q"))
    if s00 != summary["n"] or s11 < 0 or q < 0 or s00 * s11 < s01 * s01:
        raise ValueError("invalid-gram-summary")
    a, b = theta
    n = summary["n"]
    objective = (a * a * s00 + 2 * a * b * s01 + b * b * s11 - 2 * (a * t0 + b * t1) + q) / (
        2 * n
    ) + model.ridge * (a * a + b * b) / 2
    gradient = (
        (a * s00 + b * s01 - t0) / n + model.ridge * a,
        (a * s01 + b * s11 - t1) / n + model.ridge * b,
    )
    return {"objective": objective, "gradient": gradient}


def direct(
    rows: tuple[tuple[F, F], ...], theta: tuple[F, F], model: FeatureModel
) -> dict[str, Any]:
    model.validate()
    if (
        not rows
        or len(rows) > 4096
        or len(theta) != 2
        or any(type(v) is not F or abs(v) > 2 for v in theta)
    ):
        raise ValueError("bounded-full-data-query")
    if any(type(y) is not F or abs(y) > 2 for _, y in rows):
        raise ValueError("bounded-label")
    a, b = theta
    errors = [a + b * model.feature(x)[1] - y for x, y in rows]
    objective = (
        sum((e * e for e in errors), F(0)) / (2 * len(rows)) + model.ridge * (a * a + b * b) / 2
    )
    g0 = sum(errors, F(0)) / len(rows) + model.ridge * a
    g1 = (
        sum((e * model.feature(x)[1] for e, (x, _) in zip(errors, rows, strict=True)), F(0))
        / len(rows)
        + model.ridge * b
    )
    return {"objective": objective, "gradient": (g0, g1)}


def approximation_bound(theta: tuple[F, F], model: FeatureModel) -> dict[str, F]:
    a, b = theta
    delta = F(1, 4) * (abs(b) + 1)
    feature_bound = 2 * model.gain
    residual = abs(a) + abs(b) * feature_bound + 2
    return {
        "objective": residual * delta + delta * delta / 2,
        "gradient0": delta,
        "gradient1": delta * feature_bound + (residual + delta) * F(1, 4),
    }


def cache_key(
    snapshot_id: str, model: FeatureModel, preprocessing: str, policy: str, schema: str
) -> str:
    return digest(
        "summary-cache-key",
        {
            "snapshot": snapshot_id,
            "frozen_model": model.descriptor,
            "preprocessing": preprocessing,
            "policy": policy,
            "schema": schema,
            "numeric": "exact-fraction-mean-ridge-1",
        },
    )


def query_witness_key(summary_key: str, theta: tuple[F, F]) -> str:
    return digest(
        "mathematical-witness-key",
        {
            "summary": summary_key,
            "theta": [str(v) for v in theta],
            "proof_status": "unavailable-not-a-cached-proof",
        },
    )


class SummaryCache:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, payload: dict[str, Any]) -> None:
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("cache-key")
        record = {
            "key": key,
            "payload": payload,
            "payload_digest": digest("cache-payload", payload),
        }
        path = self.root / (key + ".json")
        if path.exists():
            if self.get(key) != payload:
                raise ValueError("conflicting-cache-entry")
            return
        with path.open("xb") as f:
            f.write(canonical(record))

    def get(self, key: str) -> dict[str, Any]:
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("cache-key")
        path = self.root / (key + ".json")
        if path.is_symlink():
            raise ValueError("cache-symlink")
        raw = path.read_bytes()
        if len(raw) > 10000:
            raise ValueError("bounded-cache-record")
        row = json.loads(raw)
        if (
            set(row) != {"key", "payload", "payload_digest"}
            or row["key"] != key
            or canonical(row) != raw
            or row["payload_digest"] != digest("cache-payload", row["payload"])
        ):
            raise ValueError("cache-context-or-payload-integrity")
        return dict(row["payload"])


def break_even(
    setup_seconds: float, full_query_seconds: float, cached_query_seconds: float
) -> int | None:
    if any(
        not math.isfinite(v) or v < 0
        for v in (setup_seconds, full_query_seconds, cached_query_seconds)
    ):
        raise ValueError("finite-nonnegative-measurements")
    saving = full_query_seconds - cached_query_seconds
    return math.floor(setup_seconds / saving) + 1 if saving > 0 else None
