"""Retain exact reference calculations with honest provenance and assurance limits."""

from __future__ import annotations

# ruff: noqa: E402
import hashlib
import json
import platform
import subprocess
import sys
import time
from fractions import Fraction as F
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from jsonschema import Draft202012Validator  # noqa: E402

from fzkml_research.evaluation import private_gap_certificate  # noqa: E402
from fzkml_research.statistics import lower_bound, upper_bound  # noqa: E402
from python.fzkml_math.arithmetic import rounded
from python.fzkml_math.distributions import (  # noqa: E402
    cyclic_geometric,
    hockey_stick,
    postprocess,
)
from python.fzkml_math.numeric import encode, evaluate  # noqa: E402
from python.fzkml_math.refinement import class_status, quadratic
from python.fzkml_math.sensitivity import FixedMean, rounded_change_bound  # noqa: E402


def report() -> dict[str, Any]:
    start = time.perf_counter()
    mean = FixedMean(2, (1, 1))
    observed, pair = mean.enumerate_sensitivity("add-remove-zero-slot")
    trace = evaluate(encode(1, [0, 0, 8], [0, 0, 8], [1, 1, 2]))
    updates = trace["updates"]
    if not isinstance(updates, list):
        raise AssertionError("reference-local-state-shape")
    delta_shortcut = 1 + rounded(
        sum(n * (u - 1) for n, u in zip((1, 1, 2), updates, strict=True)), 4
    )
    pmf = cyclic_geometric(2, 3, 7)
    shifted = postprocess(pmf, lambda k: (k + 1) % 7)
    p = lower_bound(100, 1000, 0.025)
    q = upper_bound(0, 1000, 0.025)
    import math

    observations = [
        {
            "id": "rne-full-state",
            "status": "counterexample-reproduced",
            "inputs": {"w": 1, "x": [0, 0, 8], "y": [0, 0, 8], "weights": [1, 1, 2]},
            "result": {"full_state": trace["output"], "delta_shortcut": delta_shortcut},
            "assumptions": ["fzknum-1.0.0 full-state RNE aggregation"],
            "limitations": [
                "Original synthetic counterexample; not a manuscript numerical example."
            ],
        },
        {
            "id": "rne-sensitivity",
            "status": "counterexample-reproduced",
            "inputs": {"cap": 2, "public_weights": [1, 1], "adjacency": "add-remove-zero-slot"},
            "result": {
                "observed_sensitivity": observed,
                "neighboring_witness": [list(row) for row in pair],
                "lattice_bound": rounded_change_bound(2, 2),
                "unadjusted_ceil_bound": 1,
            },
            "assumptions": ["Integer numerator lattice, fixed denominator, nearest-even rounding"],
            "limitations": [
                "Finite enumeration covers only this small domain; "
                "general bound has a separate derivation/review obligation."
            ],
        },
        {
            "id": "finite-noise-law",
            "status": "exact-finite-pair-analysis",
            "inputs": {
                "geometric_numerator": 2,
                "geometric_denominator": 3,
                "modulus": 7,
                "query_shift": 1,
                "exp_epsilon": "3/2",
            },
            "result": {
                "probability_sum": str(sum(pmf.values())),
                "hockey_stick_delta": str(hockey_stick(pmf, shifted, F(3, 2))),
            },
            "assumptions": ["Entire finite PMFs enumerated with exact rational arithmetic"],
            "limitations": [
                "No private noise sampler or entropy service implemented by this calculation; "
                "no empirical test or universal DP proof."
            ],
        },
        {
            "id": "book-privacy-audit",
            "status": "analytical-teaching-example",
            "inputs": {
                "D_events": 100,
                "D_trials": 1000,
                "D_prime_events": 0,
                "D_prime_trials": 1000,
                "one_sided_error": 0.025,
                "delta": 1e-6,
            },
            "result": {
                "p_lower": p,
                "q_upper": q,
                "epsilon_lower": math.log((p - 1e-6) / q),
                "simultaneous_confidence": 0.95,
                "real_training_executions": 0,
            },
            "assumptions": [
                "Hypothetical independent mechanism executions, fixed neighboring pair/event, "
                "no calibration overlap, two one-sided bounds"
            ],
            "limitations": [
                "Book hypothetical counts, not observations from model runs. "
                "No unsuccessful attack can certify DP; power is not estimated."
            ],
        },
        {
            "id": "book-small-group-certificate",
            "status": "conditional-analytic-confidence",
            "inputs": {
                "noisy_denominators": [1000, 100],
                "noisy_gap": 0.04,
                "epsilon": 1,
                "alpha": 0.04,
                "beta": 0.01,
            },
            "result": private_gap_certificate(
                (1000, 100),
                0.04,
                epsilon=1,
                alpha=0.04,
                beta=0.01,
                fixed_classifier=True,
                iid_units=True,
                ideal_laplace_assumption=True,
            ),
            "assumptions": [
                "Fixed classifier/groups, independent IID evaluation units, "
                "ideal real-valued Laplace law"
            ],
            "limitations": [
                "Hypothetical book inputs; no finite-Laplace implementation "
                "or deployment fairness claim."
            ],
        },
        {
            "id": "small-denominator",
            "status": "inconclusive",
            "inputs": {"noisy_denominators": [10, 10]},
            "result": private_gap_certificate(
                (10, 10),
                0.04,
                epsilon=1,
                alpha=0.04,
                beta=0.01,
                fixed_classifier=True,
                iid_units=True,
                ideal_laplace_assumption=True,
            ),
            "assumptions": ["Same conditional certificate domain"],
            "limitations": [
                "No denominator repair or fairness certification; evidence insufficient."
            ],
        },
    ]
    observations.append(
        {
            "id": "original-quadratic-precision",
            "status": "numerical-reference-experiment",
            "inputs": {
                "analytic_optimum": "1/3",
                "scales": [1, 2, 4, 8, 16, 32],
                "rate": "1/2",
                "steps": 16,
                "origin": "original-synthetic-not-book",
            },
            "result": {
                "precisions": [quadratic(scale) for scale in (1, 2, 4, 8, 16, 32)],
                "unsafe_rate": quadratic(16, rate=F(3)),
                "observed_but_uncertified_class": class_status(
                    (F(1, 10), F(0)), (F(1, 10), F(0)), F(1, 10)
                ),
            },
            "assumptions": [
                "Declared one-dimensional quadratic has L=mu=1; "
                "rate1/2 is contractive; rate3 is outside that condition."
            ],
            "limitations": [
                "Original finite CPU reference trajectory, not manuscript numerical inputs "
                "or global model convergence evidence.",
                "Circuit constraint cost and general attention/optimizer refinement "
                "remain not measured.",
            ],
        }
    )
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    names = [
        "Cargo.lock",
        "uv.lock",
        "specs/numeric-contract-v1.json",
        "tests/vectors/book/manuscript-v1.json",
        "tests/vectors/synthetic/s02-boundaries-v1.json",
        "tests/vectors/synthetic/s02-data-v1.json",
        "python/reference-sources.json",
        "tests/vectors/synthetic/private-transition-v2.json",
    ]
    return {
        "schema_version": "s02-math-run-1.0.0",
        "run_id": "synthetic:s02-math-" + source[:12],
        "kind": "deterministic-reference-calculations",
        "claim_ids": [],
        "source_commit": source,
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT
            )
        ),
        "execution": {
            "kind": "local",
            "workflow_run": None,
            "python": platform.python_version(),
            "os": platform.system(),
            "machine": platform.machine(),
            "public_experiment_seed": 20261124,
            "private_randomness": "not-used-or-recorded",
            "reproduction_command": (
                "./scripts/validate-s02; PYTHONPATH=.:src .venv/bin/python "
                "scripts/run_s02_experiments.py .tools/s02"
            ),
        },
        "digests": {
            name: "sha256:" + hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in names
        },
        "observations": observations,
        "repetitions": [
            {
                "id": "rep1",
                "status": "completed",
                "excluded": False,
                "reference_checks_seconds": time.perf_counter() - start,
            }
        ],
        "limitations": [
            "Original reference artifact only; no public-report publication approval "
            "or claim-status promotion.",
            "Timing is a calculation-runtime diagnostic, not a performance benchmark.",
            "Statistical confidence is conditional; empirical statistical tests do not prove DP.",
            "Books use MS20261124 snapshot metadata, not an author-declared edition.",
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("output-directory-required")
    result = report()
    schema = json.loads((ROOT / "schemas/s02-math-run-1.0.0.json").read_text())
    Draft202012Validator(schema).validate(result)
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    (output / "math-run.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        "S02 exact/reference calculations retained; small-group denominator outcome "
        "inconclusive; no DP proof claimed."
    )
