"""Design and evidence checks; hypothetical/synthetic records never prove adoption."""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

from specifications.data_outcomes.reference import require


def validate_factorial(plan: dict[str, Any]) -> None:
    require(
        plan["status"] == "planned" and plan["training_runs_executed"] == 0,
        "unexecuted-factorial-overclaim",
    )
    expected = set(itertools.product((8, 32), (1, 4), ("exact", "quarter-corrupted")))
    rows = plan["cells"]
    require(
        len(rows) == 8
        and {(c["consumed_records"], c["source_diversity"], c["label_quality"]) for c in rows}
        == expected,
        "incomplete-factorial",
    )
    require(
        plan["arms"] == ["L", "F", "P", "Z"] and plan["seeds"] == list(range(20)),
        "unmatched-arms-or-seeds",
    )
    controls = {
        "same-honest-trace-F-P-Z",
        "P-Z-same-privacy-mechanism",
        "held-out-entity-time",
        "held-out-site",
        "source-fixed-count",
        "count-fixed-source",
        "eligible-population-denominator",
    }
    require(
        controls <= set(plan["controls"]) and plan["batch_relation_status"] == "pending",
        "missing-controls-or-unsupported-batch-relation",
    )
    require(
        plan["unique_entity_counts_required"] is True
        and plan["falsification_rule"]
        and plan["missing_failure_policy"],
        "missing-outcome-definition",
    )


def check_split(
    train: Sequence[Mapping[str, Any]], test: Sequence[Mapping[str, Any]], held_out_site: bool
) -> None:
    require(bool(train) and bool(test), "empty-evaluation-split")
    require(not {r["entity"] for r in train} & {r["entity"] for r in test}, "entity-overlap")
    require(
        not {r["duplicate_cluster"] for r in train} & {r["duplicate_cluster"] for r in test},
        "duplicate-cluster-overlap",
    )
    require(max(r["time"] for r in train) < min(r["time"] for r in test), "future-time-leakage")
    if held_out_site:
        require(not {r["site"] for r in train} & {r["site"] for r in test}, "site-overlap")


def validate_adoption(plan: dict[str, Any]) -> None:
    require(
        plan["status"] == "planned"
        and plan["recruitment_authorized"] is False
        and plan["observations"] == []
        and plan["claimed_effect"] is None,
        "unexecuted-field-study-overclaim",
    )
    require(
        plan["assignment_unit"] == "institution"
        and plan["comparison"] == ["locality-only", "secure-aggregate", "verified-protected"],
        "assignment-or-offer-contrast",
    )
    require(
        plan["primary_outcome"] == "authorized-transferred-validated-novel-contribution"
        and plan["estimand"]
        and plan["selection"]
        and plan["attrition"]
        and plan["interference"],
        "missing-causal-design",
    )
    require(
        plan["willingness_is_access"] is False and plan["benefit_claim_status"] == "hypothesis",
        "willingness-or-public-benefit-overclaim",
    )


def check_adoption_record(record: dict[str, Any]) -> None:
    if record["transferred"]:
        require(record["consented"] and record["authorized"], "unauthorized-transfer")
    if record["novelty_validated"]:
        require(record["transferred"], "novelty-without-data-validation")
    if record["claim_access_unlocked"]:
        require(
            record["origin"] == "observed-consented-study"
            and record["authorized"]
            and record["transferred"]
            and record["novelty_validated"],
            "synthetic-or-willingness-is-not-access-evidence",
        )


def check_sector_source(card: dict[str, Any]) -> None:
    require(
        card["local_replication_status"] == "not-replicated"
        and card["source_execution_status"] == "not-run-here"
        and card["FZKML_deployment_outcome"] is False,
        "sector-evidence-overclaim",
    )
    require(
        card["source_url"].startswith("https://")
        and card["source_version"]
        and card["inspection_scope"]
        and card["population"]
        and card["endpoints"]
        and card["data_adoption"] == "not-adopted",
        "incomplete-source-card",
    )


def classify_gain_reference(
    estimate: float,
    lower: float,
    upper: float,
    minimum: float,
    complete: bool,
    sufficiently_powered: bool,
) -> str:
    """Decision-rule reference only; no observed experiment is certified here."""
    import math

    require(
        all(math.isfinite(v) for v in (estimate, lower, upper, minimum))
        and lower <= estimate <= upper
        and minimum >= 0,
        "invalid-uncertainty-input",
    )
    if not complete or not sufficiently_powered:
        return "inconclusive"
    if upper < minimum:
        return "refuted-scoped-minimum-gain"
    if lower > minimum:
        return "supports-scoped-minimum-gain"
    return "inconclusive"
