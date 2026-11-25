"""Independent-mechanism-run audits with explicit observer and multiplicity scope."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from fzkml_ci.validate import require

from .statistics import lower_bound, upper_bound


@dataclass(frozen=True)
class Trial:
    trial_id: str
    model_run_id: str
    randomization_id: str
    side: Literal["D", "D-prime"]
    status: Literal["completed", "failed", "timed-out"]
    event: bool | None


@dataclass(frozen=True)
class AuditPlan:
    attack_id: str
    observer: str
    adjacency: str
    privacy_unit: str
    threshold_id: str
    preregistered: bool
    independent_mechanism_runs: bool
    calibration_run_ids: tuple[str, ...]
    registered_tests: int = 1
    family_error: float = 0.05
    delta: float = 1e-6
    claimed_epsilon: float = 1.0
    power_declaration: str = "Joint audit power not estimated; insufficient power remains possible."


def audit(plan: AuditPlan, trials: list[Trial]) -> dict[str, Any]:
    require(bool(trials) and len(trials) <= 40_000, "audit-size")
    require(plan.preregistered and plan.independent_mechanism_runs, "audit-independence-plan")
    require(
        type(plan.registered_tests) is int and 1 <= plan.registered_tests <= 1000,
        "audit-multiplicity",
    )
    require(math.isfinite(plan.family_error) and 0 < plan.family_error < 1, "audit-error-budget")
    require(
        math.isfinite(plan.delta)
        and 0 <= plan.delta < 1
        and math.isfinite(plan.claimed_epsilon)
        and plan.claimed_epsilon >= 0,
        "audit-privacy-parameters",
    )
    require(
        all(
            (
                plan.attack_id,
                plan.observer,
                plan.adjacency,
                plan.privacy_unit,
                plan.threshold_id,
                plan.power_declaration,
            )
        ),
        "audit-scope-required",
    )
    for field in ("trial_id", "model_run_id", "randomization_id"):
        values = [getattr(t, field) for t in trials]
        require(all(values) and len(set(values)) == len(values), "correlated-or-duplicate-run")
    require(
        not set(plan.calibration_run_ids) & {t.model_run_id for t in trials},
        "audit-calibration-overlap",
    )
    for t in trials:
        require(
            t.side in {"D", "D-prime"} and t.status in {"completed", "failed", "timed-out"},
            "audit-trial-type",
        )
        require(
            (t.status == "completed" and type(t.event) is bool)
            or (t.status != "completed" and t.event is None),
            "audit-outcome",
        )
    counts = {
        side: {
            "invited": sum(t.side == side for t in trials),
            "completed": sum(t.side == side and t.status == "completed" for t in trials),
            "events": sum(t.side == side and t.event is True for t in trials),
        }
        for side in ("D", "D-prime")
    }
    require(all(0 < c["invited"] <= 20_000 for c in counts.values()), "audit-both-sides-required")
    result: dict[str, Any] = {
        "attack": plan.attack_id,
        "observer": plan.observer,
        "adjacency": plan.adjacency,
        "privacy_unit": plan.privacy_unit,
        "threshold": plan.threshold_id,
        "counts": counts,
        "registered_tests": plan.registered_tests,
        "confidence": 1 - plan.family_error,
        "power": plan.power_declaration,
        "status": "inconclusive",
        "epsilon_lower_bound": None,
        "limitations": [
            "An unsuccessful attack cannot certify DP.",
            "Identifiers and declared independence require experiment-design review.",
            "This tests one fixed event and neighboring input pair, in one direction.",
        ],
    }
    if any(c["invited"] != c["completed"] for c in counts.values()):
        result["reason"] = "Incomplete trials retained; no complete-case binomial inference."
        return result
    error = plan.family_error / (2 * plan.registered_tests)
    p = lower_bound(counts["D"]["events"], counts["D"]["completed"], error)
    q = upper_bound(counts["D-prime"]["events"], counts["D-prime"]["completed"], error)
    bound = max(0.0, math.log((p - plan.delta) / q)) if p > plan.delta and q > 0 else 0.0
    result.update(
        p_lower=p,
        q_upper=q,
        epsilon_lower_bound=bound,
        status="contradiction-under-assumptions"
        if bound > plan.claimed_epsilon
        else "inconclusive",
        reason="Compare this lower bound to the claimed upper bound under the declared design.",
    )
    return result
