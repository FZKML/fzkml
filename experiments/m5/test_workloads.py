"""Run with python -m unittest discover -s experiments/m5."""

from __future__ import annotations

import unittest

from workloads import (
    Interaction,
    authorized_edges,
    correspondence,
    cosine_gate,
    graph,
    language,
    neural,
    robust,
    time_series,
    transfer,
)


class WorkloadTests(unittest.TestCase):
    def test_sum_is_insufficient_and_median_can_change_by_diameter(self) -> None:
        result = robust()
        self.assertEqual(result["same_sum"], [0, 0])
        self.assertEqual(result["different_medians"], [0, -2])
        self.assertEqual(result["adjacent_medians"], [-4, 4])
        self.assertTrue(result["outlier_hits_target_with_mean"])
        self.assertFalse(result["outlier_hits_target_with_median"])
        self.assertEqual(result["expected_output"], [1, 0])
        self.assertFalse(cosine_gate((0, 0), (1, 0)))
        self.assertFalse(cosine_gate((-1, 1), (1, 0)))
        self.assertFalse(cosine_gate((4, 4), (1, 0)))

    def test_independent_neural_fixture_backpropagates_in_both_layers(self) -> None:
        result = neural()
        self.assertEqual(result["expected_inference_output"], [-2])
        self.assertEqual(result["raw_gradient"], [12, -6, -6, -6])
        self.assertEqual(result["expected_training_output"], [-2, 3, 0, 3])
        self.assertEqual(result["integer_class_correct"], {"-1": 0, "1": 1})
        self.assertEqual(result["rational_class_correct"], {"-1": 2, "1": 1})

    def test_adaptation_and_retrieval_have_distinct_outputs(self) -> None:
        result = language()
        self.assertLess(result["baseline_correct"], result["adapted_correct"])
        self.assertEqual(result["public_query_matches"], ("public-1",))
        self.assertEqual(result["restricted_query_matches"], ("public-1", "internal-1"))
        self.assertTrue(result["unfiltered_canary_visible"])
        self.assertFalse(result["public_canary_visible"])

    def test_generated_canary_is_retained_under_naive_release(self) -> None:
        result = transfer()
        self.assertTrue(result["synthetic_generation_memorized_canary"])
        self.assertTrue(result["distillation"]["raw_unique_canary_disclosed"])
        self.assertFalse(result["distillation"]["cohort_release_canary_disclosed"])
        self.assertEqual(result["privacy_mechanism"], "none")

    def test_unpaired_views_cannot_select_the_predictor(self) -> None:
        result = correspondence()
        self.assertTrue(result["marginals_equal"])
        self.assertEqual(result["paired_correct"], {"equal": 2, "opposite": 2})
        self.assertEqual(result["fixed_identity_correct"], {"equal": 2, "opposite": 0})
        self.assertEqual(result["best_deterministic_unpaired_worst_case_correct"], 1)
        self.assertTrue(result["swapped_ids_change_optimum"])
        self.assertEqual(result["missing_modality_rows_abstained"], 1)

    def test_graph_enforces_user_cap_and_rejects_unknown_links(self) -> None:
        row = Interaction("u", "a", "a")
        with self.assertRaisesRegex(ValueError, "duplicate-edge"):
            authorized_edges([row, row], {"u": "a"})
        with self.assertRaisesRegex(ValueError, "user-contribution-cap"):
            authorized_edges(
                [row, Interaction("u", "a", "b"), Interaction("u", "a", "c")], {"u": "a"}
            )
        with self.assertRaisesRegex(ValueError, "unauthorized-edge"):
            authorized_edges([row], {"u": "b"})
        self.assertEqual(graph()["top1_hits"], 2)
        self.assertEqual(graph()["unauthorized_join_rejected"], "unauthorized-edge")

    def test_forecasting_counts_nonparticipation_and_leaves_temporal_gap(self) -> None:
        result = time_series()
        self.assertEqual((result["invited"], result["completed"], result["admitted"]), (4, 3, 2))
        self.assertEqual(result["sources"]["mountain"]["payload_bytes"], 0)
        self.assertTrue(result["sources"]["south"]["completed"])
        self.assertFalse(result["sources"]["south"]["admitted"])
        self.assertLess(result["training_times"][1], result["test_times"][0])


if __name__ == "__main__":
    unittest.main()
