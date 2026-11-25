"""Finite reference/design checks are separate from study or security evidence."""

from __future__ import annotations

import copy
import json
import unittest
from fractions import Fraction as F
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from specifications.data_outcomes.design import (
    check_adoption_record,
    check_sector_source,
    check_split,
    classify_gain_reference,
    validate_adoption,
    validate_factorial,
)
from specifications.data_outcomes.pilot import run_pilot
from specifications.data_outcomes.reference import (
    Row,
    check_lifecycle,
    coalitions,
    removal,
    shapley,
    statistics,
    surrogate_bound,
    valuation_examples,
)
from specifications.data_outcomes.run import ROOT, removal_examples

FOLDER = ROOT / "specifications/data_outcomes"


def read(name: str) -> dict[str, Any]:
    return json.loads((FOLDER / name).read_text())  # type: ignore[no-any-return]


class DataOutcomeTests(unittest.TestCase):
    def test_ridge_removal_matches_recompute(self) -> None:
        rows = (Row("a", (F(1), F(0)), F(1)), Row("b", (F(0), F(1)), F(1)))
        result = removal(rows, {"a"}, {"a", "b"}, F(1))
        self.assertEqual(result["old"], (F(1, 2), F(1, 2)))
        self.assertEqual(result["new"], (F(0), F(1, 2)))
        self.assertEqual((result["matrix"], result["rhs"]), statistics((rows[1],), F(1)))
        self.assertEqual(result["new_residual_squared"], 0)

    def test_residual_parameter_bound_and_nontrivial_perturbation(self) -> None:
        result = removal_examples()
        original = result["original_perturbation_reference"]
        self.assertEqual(original["parameter_change_squared"], "9/32")
        self.assertEqual(original["old_candidate_residual_bound_squared"], "9/8")
        self.assertLessEqual(
            F(result["approximate_error_squared"]), F(result["lambda1_residual_bound_squared"])
        )

    def test_ridge_requires_fixed_positive_lambda_and_authorization(self) -> None:
        row = Row("a", (F(1), F(0)), F(1))
        with self.assertRaises(ValueError):
            statistics((row,), F(0))
        with self.assertRaises(ValueError):
            statistics((row, row), F(1))
        with self.assertRaises(ValueError):
            removal((row,), {"a"}, set(), F(1))

    def test_lifecycle_rejects_tombstone_and_refund(self) -> None:
        trusted: dict[str, Any] = {
            "parent_model": "old",
            "expected_retained_model": "new",
            "known_artifacts": ["source", "cache", "checkpoint"],
            "prior_releases": ["released-old-model"],
            "privacy_spent_before": "1/4",
        }
        record: dict[str, Any] = {
            "claim_scope": "current-model-and-known-inventory-only",
            "parent_model": "old",
            "new_model": "new",
            "known_artifacts": list(trusted["known_artifacts"]),
            "artifact_actions": {
                "source": "removed",
                "cache": "quarantined-not-erased",
                "checkpoint": "removed",
            },
            "prior_releases": list(trusted["prior_releases"]),
            "retained_release_history": list(trusted["prior_releases"]),
            "privacy_spent_after": "1/4",
            "unobserved_copy_status": "unknown",
            "certificate_kind": "transparent-reference-not-cryptographic-proof",
        }
        check_lifecycle(record, trusted)
        for field, value in (
            ("claim_scope", "all-copies-erased"),
            ("new_model", "old"),
            ("privacy_spent_after", "0"),
            ("retained_release_history", []),
            ("unobserved_copy_status", "erased"),
        ):
            bad = copy.deepcopy(record)
            bad[field] = value
            with self.assertRaises(ValueError):
                check_lifecycle(bad, trusted)
        bad = copy.deepcopy(record)
        bad["known_artifacts"].remove("cache")
        del bad["artifact_actions"]["cache"]
        with self.assertRaisesRegex(ValueError, "omitted-known-artifact"):
            check_lifecycle(bad, trusted)

    def test_shapley_source_table_and_replication(self) -> None:
        result = valuation_examples()
        self.assertEqual(result["allocation"], {"A": "13/30", "B": "1/3", "C": "2/15"})
        self.assertEqual(sum(map(F, result["allocation"].values())), F(9, 10))
        self.assertEqual(result["original_entity_allocation"], "1/2")
        self.assertEqual(result["cloned_entity_allocation"], "2/3")
        self.assertEqual(result["payments_executed"], 0)
        with self.assertRaises(ValueError):
            coalitions(("same", "same"))

    def test_surrogate_requires_uniform_premise(self) -> None:
        players = ("A", "B", "C")
        utility = {s: F(len(s), 3) for s in coalitions(players)}
        surrogate = dict(utility)
        surrogate[frozenset(players)] += F(1, 100)
        errors = surrogate_bound(players, utility, surrogate, F(1, 100))
        self.assertTrue(all(error <= F(1, 50) for error in errors.values()))
        with self.assertRaisesRegex(ValueError, "uniform-error"):
            surrogate_bound(players, utility, surrogate, F(1, 1000))
        surrogate.pop(frozenset())
        with self.assertRaisesRegex(ValueError, "uniform-coalition"):
            surrogate_bound(players, utility, surrogate, F(1, 100))

    def test_visible_allocation_can_reveal_private_utility(self) -> None:
        for secret in (F(1, 3), F(2, 3)):
            payout = shapley(("one",), {frozenset(): F(0), frozenset({"one"}): secret})
            self.assertEqual(payout["one"], secret)

    def test_factorial_requires_all_cells_and_controls(self) -> None:
        plan = read("factorial-v1.json")
        validate_factorial(plan)
        bad = copy.deepcopy(plan)
        bad["cells"][0] = copy.deepcopy(bad["cells"][1])
        with self.assertRaisesRegex(ValueError, "incomplete-factorial"):
            validate_factorial(bad)
        bad = copy.deepcopy(plan)
        bad["arms"].remove("Z")
        with self.assertRaises(ValueError):
            validate_factorial(bad)
        bad = copy.deepcopy(plan)
        bad["controls"].remove("same-honest-trace-F-P-Z")
        with self.assertRaises(ValueError):
            validate_factorial(bad)
        bad = copy.deepcopy(plan)
        bad["training_runs_executed"] = 1
        with self.assertRaisesRegex(ValueError, "overclaim"):
            validate_factorial(bad)

    def test_entity_duplicate_time_and_site_leakage(self) -> None:
        train = [{"entity": "a", "duplicate_cluster": "a", "site": 0, "time": 1}]
        test = [{"entity": "b", "duplicate_cluster": "b", "site": 1, "time": 2}]
        check_split(train, test, True)
        for field, value in (("entity", "a"), ("duplicate_cluster", "a"), ("time", 1), ("site", 0)):
            bad = copy.deepcopy(test)
            bad[0][field] = value
            with self.assertRaises(ValueError):
                check_split(train, bad, True)

    def test_gain_decision_retains_refuted_and_underpowered_results(self) -> None:
        self.assertEqual(
            classify_gain_reference(0, -0.01, 0.005, 0.01, True, True),
            "refuted-scoped-minimum-gain",
        )
        self.assertEqual(
            classify_gain_reference(0.03, 0.02, 0.04, 0.01, True, False), "inconclusive"
        )
        self.assertEqual(
            classify_gain_reference(0.03, 0.02, 0.04, 0.01, False, True), "inconclusive"
        )
        with self.assertRaises(ValueError):
            classify_gain_reference(0.03, 0.04, 0.02, 0.01, True, True)

    def test_synthetic_pilot_has_disjoint_holdouts(self) -> None:
        result = run_pilot()
        self.assertEqual((result["train_records"], result["train_unique_entities"]), (96, 32))
        self.assertEqual(result["temporal_holdout"]["records"], 16)
        self.assertEqual(result["site_holdout"]["records"], 24)
        self.assertGreaterEqual(F(result["site_holdout"]["mse"]), 0)
        self.assertFalse(result["paper_replication"])
        self.assertEqual(result["FZKML_gain"], "not-tested")

    def test_pilot_denied_or_missing_data_cannot_run(self) -> None:
        with self.assertRaises(ValueError):
            run_pilot(available=False)
        with self.assertRaises(ValueError):
            run_pilot(rights_approved=False)

    def test_sector_source_cannot_inherit_pilot_success(self) -> None:
        cards = read("sector-cards-v1.json")["cards"]
        for card in cards:
            check_sector_source(card)
        clinical = next(card for card in cards if card["id"] == "exam-2021")
        self.assertEqual(clinical["population"]["source_sites"], 20)
        self.assertEqual(clinical["population"]["independent_test_sites"], 3)
        self.assertEqual(clinical["population"]["selected_metric_sites"], 18)
        bad = copy.deepcopy(cards[0])
        bad["local_replication_status"] = "replicated"
        with self.assertRaises(ValueError):
            check_sector_source(bad)

    def test_planned_adoption_cannot_claim_effect(self) -> None:
        plan = read("adoption-v1.json")
        validate_adoption(plan)
        for field, value in (
            ("claimed_effect", 0.1),
            ("observations", [{"willing": True}]),
            ("willingness_is_access", True),
        ):
            bad = copy.deepcopy(plan)
            bad[field] = value
            with self.assertRaises(ValueError):
                validate_adoption(bad)

    def test_willingness_and_synthetic_records_are_not_access(self) -> None:
        record: dict[str, Any] = {
            "origin": "synthetic",
            "willing": True,
            "consented": False,
            "authorized": False,
            "transferred": False,
            "novelty_validated": False,
            "claim_access_unlocked": False,
        }
        check_adoption_record(record)
        bad = dict(record, claim_access_unlocked=True)
        with self.assertRaisesRegex(ValueError, "not-access-evidence"):
            check_adoption_record(bad)
        bad = dict(
            record,
            consented=True,
            authorized=True,
            transferred=True,
            novelty_validated=True,
            claim_access_unlocked=True,
        )
        with self.assertRaisesRegex(ValueError, "not-access-evidence"):
            check_adoption_record(bad)
        with self.assertRaisesRegex(ValueError, "unauthorized-transfer"):
            check_adoption_record(dict(record, transferred=True))

    def test_report_schema_retains_unexecuted_study_boundaries(self) -> None:
        schema = read("report-schema-v1.json")["properties"]
        for field, value in (
            ("factorial_training_status", "successful"),
            ("adoption_study_status", "successful"),
            ("sector_replication_status", "replicated"),
            ("genuine_proofs_verified", 1),
            ("payments_executed", 1),
        ):
            with self.assertRaises(ValidationError):
                Draft202012Validator(schema[field]).validate(value)


if __name__ == "__main__":
    unittest.main()
