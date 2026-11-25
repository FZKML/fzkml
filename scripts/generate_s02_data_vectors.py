#!/usr/bin/env python3
"""Regenerate only original synthetic fixtures; never generate book source facts."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from python.fzkml_math.data_lineage import Policy, snapshot, synthetic_parts
from python.fzkml_math.summary_cache import FeatureModel, evaluate, examples, stats
from python.fzkml_math.toy_generation import control, denoise

ROOT = Path(__file__).resolve().parents[1]


def generate() -> dict[str, Any]:
    parts = synthetic_parts()
    policy = Policy()
    state = snapshot(parts, policy)
    m = FeatureModel()
    summary = stats(examples(23), m)
    result = evaluate(summary, (F(1, 2), F(1)), m)
    return {
        "version": "s02-data-lineage-vectors-1.0.0",
        "provenance": "original deterministic synthetic examples; not book numeric inputs",
        "snapshot": {
            "parts": parts,
            "policy": asdict(policy),
            "expected_identity": state["identity"],
            "expected_selected_count": 12,
            "expected_schema_digest": state["manifest"]["schema_digest"],
            "expected_preprocessing_digest": state["manifest"]["preprocessing_digest"],
        },
        "summary": {
            "records": 23,
            "model": m.descriptor,
            "expected_statistics": summary,
            "theta": ["1/2", "1"],
            "objective": str(result["objective"]),
            "gradient": [str(v) for v in result["gradient"]],
        },
        "denoising": denoise(),
        "quantized_denoising": denoise(scale=16),
        "control": control(),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    path = ROOT / "tests/vectors/synthetic/data-lineage-v1.json"
    raw = json.dumps(generate(), indent=2, allow_nan=False) + "\n"
    if a.check:
        if path.read_text() != raw:
            raise SystemExit("synthetic-data-vector-drift")
        print("S02 synthetic data/summary/toy vectors verified")
    else:
        path.write_text(raw)
