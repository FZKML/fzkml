"""Reject changed configuration declarations until a matching implementation is selected."""

from __future__ import annotations

from typing import Any

INPUT_PATHS = (
    "experiments/s02-data/config-v1.json",
    "tests/vectors/book/data-lineage-v1.json",
    "tests/vectors/synthetic/data-lineage-v1.json",
    "schemas/s02-data-run-1.0.0.json",
    "python/reference-sources.json",
    "Cargo.lock",
    "uv.lock",
    "scripts/run_s02_data.py",
    "scripts/generate_s02_data_vectors.py",
    "src/fzkml_transcript/ledger.py",
    "python/fzkml_math/data_experiment_contract.py",
    "python/fzkml_math/data_lineage.py",
    "python/fzkml_math/join_reference.py",
    "python/fzkml_math/streaming_data.py",
    "python/fzkml_math/summary_cache.py",
    "python/fzkml_math/toy_generation.py",
)


def validate_config(c: dict[str, Any]) -> None:
    expected = {
        "summary": {
            "records": [64, 256, 1024],
            "queries": [1, 4, 8],
            "features": 2,
            "serialized_statistic_scalars": 7,
            "feature": "[1,x]",
            "objective": "mean-half-squared-loss-plus-ridge",
            "lambda": "1",
            "approximation_grid": "1/2",
            "input_scale": 16,
            "dataset_generator": "x=((7i mod33)-16)/16; y=((11i mod33)-16)/16",
        },
        "join": {
            "organizations": 3,
            "public_fixed_cohort": 4,
            "joined_entity_cap": 2,
            "scalar_clip_cm": 3,
            "public_denominator": 8,
            "matching": "exact declared synthetic entity equality",
            "output": "clipped fixed-denominator aggregate only",
            "crypto_psi": "not-implemented",
        },
        "stream": {
            "rounds": 4,
            "window": "cumulative event-time [0,watermark]",
            "correction": "explicit trusted-operator revision; old/new snapshots bound",
            "release_classification": "explicitly-unprotected exact synthetic output",
            "storage": "SQLite WAL/FULL + existing ReferenceAccountant idempotent outbox",
            "max_release_slots": 4,
            "DP_guarantee": False,
        },
        "toy": {
            "denoising": {
                "shape": [2, 2],
                "steps": 3,
                "signal_scales": ["1", "4/5", "3/5", "5/13"],
                "noise_scales": ["0", "3/5", "4/5", "12/13"],
                "untrained_epsilon_predictor": "x/4",
                "initial_pixels": ["1/2", "-1/2", "1", "-1"],
                "proof": "not-run",
            },
            "control": {
                "steps": 6,
                "start": 3,
                "actions": [-1, 0, 1],
                "transition": "x+a",
                "reward": "-(x+a)^2",
                "reward_units": "negative-squared-grid-position",
                "real_world": False,
            },
            "training": "not-run",
            "environment_authenticity": "not-tested",
            "adaptive_transcript_DP": "not-implemented",
            "manuscript_specific_model_values": "pending-source-review",
        },
    }
    if (
        c.get("version") != "s02-data-experiments-1.0.0"
        or type(c.get("repetitions")) is not int
        or c["repetitions"] != 3
    ):
        raise ValueError("unsupported-experiment-version-or-repetitions")
    if any(c.get(k) != value for k, value in expected.items()):
        raise ValueError("configuration-has-no-matching-executable-profile")
    proof = c.get("proof_amortization", {})
    if (
        proof.get("status") != "not-run"
        or proof.get("break_even") is not None
        or proof.get("mock_proof_permitted") is not False
    ):
        raise ValueError("matching-proof-adapter-not-available")
