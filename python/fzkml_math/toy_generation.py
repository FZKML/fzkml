"""Exact tiny DDIM-shaped denoising and simulated control, never real-world evidence."""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any

from .data_lineage import digest


def denoise(
    initial: tuple[F, ...] = (F(1, 2), F(-1, 2), F(1), F(-1)), *, scale: int | None = None
) -> dict[str, Any]:
    if (
        type(initial) is not tuple
        or len(initial) != 4
        or any(type(x) is not F or abs(x) > 4 for x in initial)
    ):
        raise ValueError("four-bounded-rational-synthetic-pixels")
    if scale not in (None, 16):
        raise ValueError("declared-toy-numeric-profile")
    signal = (F(1), F(4, 5), F(3, 5), F(5, 13))
    noise = (F(0), F(3, 5), F(4, 5), F(12, 13))
    state: tuple[F, ...] = initial
    trace = []
    for t in (3, 2, 1):
        prediction = tuple(x / 4 for x in state)
        clean = tuple(
            (x - noise[t] * e) / signal[t] for x, e in zip(state, prediction, strict=True)
        )
        next_state = tuple(
            signal[t - 1] * x + noise[t - 1] * e for x, e in zip(clean, prediction, strict=True)
        )
        if scale is not None:
            next_state = tuple(F(round(x * scale), scale) for x in next_state)
        if any(abs(x) > 4 for x in next_state):
            raise ValueError("toy-denoising-domain-overflow")
        trace.append(
            {
                "step": t,
                "input": [str(x) for x in state],
                "noise_prediction": [str(x) for x in prediction],
                "output": [str(x) for x in next_state],
            }
        )
        state = next_state
    return {
        "workload": "untrained-linear-epsilon-DDIM-shaped-2x2",
        "trace": trace,
        "model_digest": digest("toy-score", {"epsilon": "x/4", "trained": False}),
        "sampling_steps": 3,
        "pixel_updates": 12,
        "training_steps": 0,
        "proof_status": "not-run",
        "zero_target_mse": str(sum((x * x for x in state), F(0)) / 4),
        "output": [str(x) for x in state],
        "limitations": [
            "Fixed public initial tape, not a Gaussian sampling experiment.",
            "No trained image model, FID/IS, distributional or safety claim.",
            "No denoising/training proof or DP/memorization guarantee.",
        ],
    }


def verify_denoising(trace: dict[str, Any], *, scale: int | None = None) -> None:
    if trace != denoise(scale=scale):
        raise ValueError("incomplete-or-altered-denoising-path")


def control(steps: int = 6) -> dict[str, Any]:
    if type(steps) is not int or not 1 <= steps <= 8:
        raise ValueError("bounded-simulation-horizon")
    state = 3
    trajectory = []
    total = 0
    for i in range(steps):
        action = -1 if state > 0 else 1 if state < 0 else 0
        next_state = state + action
        reward = -(next_state**2)
        trajectory.append(
            {
                "step": i,
                "state": state,
                "action": action,
                "next_state": next_state,
                "reward": reward,
                "reward_unit": "negative-squared-grid-position",
                "provenance": "synthetic-simulator",
            }
        )
        total += reward
        state = next_state
    return {
        "kind": "bounded-simulated-control",
        "steps": steps,
        "trajectory": trajectory,
        "simulated_return": total,
        "environment_digest": digest(
            "toy-env", {"transition": "x+a", "reward": "-(x+a)^2", "unit": "grid-position"}
        ),
        "proof_status": "not-run",
        "real_environment_authenticity": "untested",
        "observer": "all synthetic states/actions/rewards visible; no adaptive-transcript DP",
        "real_world_exclusion": True,
    }


def verify_control(run: dict[str, Any], *, expected_steps: int = 6) -> None:
    if run != control(expected_steps):
        raise ValueError("wrong-units-world-model-event-or-altered-trajectory")


def require_real_claim(claim: str) -> None:
    if claim in (
        "training-proof",
        "inference-proof",
        "environment-authenticity",
        "adaptive-DP",
        "model-family-safety",
    ):
        raise ValueError("toy-result-does-not-support-real-claim")
    raise ValueError("unknown-claim")


def copied_training_sample(sample: tuple[int, ...], training: tuple[tuple[int, ...], ...]) -> bool:
    return sample in training
