"""Independent exact/counterexample tests, not scientific or privacy approval."""

from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path
from unittest.mock import patch

from fzkml_ci.validate import Invalid, load, validate_claims
from fzkml_models import adapters as ad
from fzkml_models import capacity as cp
from fzkml_models import experiment as ex
from fzkml_models import ridge as rd
from fzkml_models.algebra import add, identity, multiply, norm2, rank, scale
from fzkml_models.algebra import matrix as m

ROOT = Path(__file__).resolve().parents[1]


def ridge_fixture() -> rd.Statistics:
    return rd.statistics(m([[1, 0], [0, 1]]), m([[2], [3]]), (Q(1), Q(2)), ("r1", "r2"))


def policy() -> ad.FixedFactor:
    return ad.FixedFactor(m([[1, 0]]), "basis1", "zero-B", Q(3), Q(3), Q(1))


class RidgeTests(unittest.TestCase):
    def test_independent_hand_solution_and_absolute_objective(self) -> None:
        stats = ridge_fixture()
        self.assertEqual(stats.s, m([[1, 0], [0, 2]]))
        self.assertEqual(stats.t, m([[2], [6]]))
        self.assertEqual(rd.fit(stats, Q(1)), m([[1], [2]]))
        self.assertEqual(rd.objective(stats, m([[1], [2]]), Q(1)), 4)

    def test_partition_and_permutation_preserve_exact_objective(self) -> None:
        parts = (
            rd.statistics(m([[1, 0]]), m([[2]]), (Q(1),), ("r1",)),
            rd.statistics(m([[0, 1]]), m([[3]]), (Q(2),), ("r2",)),
        )
        for ordered in [parts, tuple(reversed(parts))]:
            joined = rd.combine(ordered)
            self.assertEqual(
                (joined.s, joined.t, joined.q),
                (ridge_fixture().s, ridge_fixture().t, ridge_fixture().q),
            )
            self.assertEqual(rd.fit(joined, Q(1)), m([[1], [2]]))
        with self.assertRaises(ValueError):
            rd.combine((parts[0], parts[0]))

    def test_mean_regularization_tracks_weight_mass(self) -> None:
        stats = ridge_fixture()
        self.assertEqual(rd.fit(stats, Q(1), "weighted-mean"), m([[Q(1, 2)], [Q(6, 5)]]))
        self.assertNotEqual(rd.fit(stats, Q(1)), rd.fit(stats, Q(1), "weighted-mean"))
        for value in [Q(0), Q(-1)]:
            with self.assertRaises(ValueError):
                rd.fit(stats, value)

    def test_certificate_binds_statistic_model_lambda_residual_and_feature(self) -> None:
        stats, model = ridge_fixture(), m([[1], [2]])
        cert = rd.certificate(stats, model, Q(1))
        bound = rd.verify(stats, model, cert, Q(0), stats.id, Q(1))
        self.assertEqual(bound["parameter_error_squared_bound"], 0)
        for bad in [
            replace(cert, residual=m([[1], [0]])),
            replace(cert, regularization=Q(2)),
            replace(cert, model_id="wrong"),
        ]:
            with self.assertRaises(ValueError):
                rd.verify(stats, model, bad, Q(1), stats.id, Q(1))
        with self.assertRaises(ValueError):
            rd.verify(replace(stats, feature_version="other"), model, cert, Q(0), stats.id, Q(1))
        with self.assertRaises(ValueError):
            rd.combine((stats, replace(stats, records=("r3", "r4"), preprocessing="other")))

    def test_residual_bounds_cover_actual_parameter_and_loss_error(self) -> None:
        stats = ridge_fixture()
        best = rd.fit(stats, Q(1))
        for delta in [Q(-1), Q(-1, 3), Q(0), Q(1, 3), Q(1)]:
            candidate = add(best, m([[delta], [delta]]))
            cert = rd.certificate(stats, candidate, Q(1))
            bounds = rd.verify(stats, candidate, cert, cert.residual_squared, stats.id, Q(1))
            self.assertLessEqual(
                norm2(add(candidate, scale(best, Q(-1)))), bounds["parameter_error_squared_bound"]
            )
            self.assertLessEqual(
                rd.objective(stats, candidate, Q(1)) - rd.objective(stats, best, Q(1)),
                bounds["excess_objective_bound"],
            )
            if delta:
                with self.assertRaises(ValueError):
                    rd.verify(stats, candidate, cert, Q(0), stats.id, Q(1))

    def test_noisy_system_is_distinct_and_perturbation_is_conditional(self) -> None:
        stats = ridge_fixture()
        noisy_model = m([[Q(4, 3)], [Q(7, 3)]])
        bound = rd.perturbation_bound(stats, noisy_model, Q(1), m([[1, 0], [0, 0]]), m([[2], [1]]))
        actual = norm2(add(noisy_model, scale(rd.fit(stats, Q(1)), Q(-1))))
        self.assertLessEqual(actual, bound * bound)
        # A zero residual for altered statistics cannot satisfy the clean certificate.
        self.assertGreater(rd.certificate(stats, noisy_model, Q(1)).residual_squared, 0)

    def test_negative_curvature_or_unbounded_statistic_is_rejected(self) -> None:
        for bad in [m([[-1, 0], [0, 2]]), m([[0, 1], [1, 2]]), m([[1, 3], [3, 1]])]:
            with self.assertRaises(ValueError):
                rd.fit(replace(ridge_fixture(), s=bad), Q(1))

    def test_statistic_privacy_counts_and_crossover_source_values(self) -> None:
        fixture = json.loads((ROOT / "assets/public/model-capacity-v1.json").read_text())
        for row in fixture["source_numeric_vectors"]:
            if row["id"].startswith("ridge-statistic"):
                self.assertEqual(
                    4 * rd.statistic_scalars(row["d"], row["c"]), row["expected_bytes"]
                )
                self.assertEqual(rd.crossover(row["d"], row["c"]), Q(row["crossover_rounds"]))
        self.assertEqual(rd.statistic_scalars(2, 1, True), 6)
        self.assertEqual(rd.record_sensitivity_squared(Q(2), Q(1), False), 20)
        self.assertEqual(rd.record_sensitivity_squared(Q(2), Q(1), True), 80)


class AdapterTests(unittest.TestCase):
    def test_quality_evaluation_counts_frozen_backbone_work(self) -> None:
        result = ad.evaluate_frozen_layer(
            identity(2), m([[1], [0]]), m([[1, 0]]), identity(2), m([[2, 0], [0, 2]])
        )
        self.assertEqual(result["mean_squared_vector_error"], Q(1, 2))
        self.assertEqual(result["backbone_multiplications"], 8)
        self.assertEqual(result["adapter_multiplications"], 8)
        self.assertEqual(result["trainable_parameters"], 2)
        self.assertEqual(result["backbone_parameters"], 4)

    def test_fixed_common_factor_matches_dense_products(self) -> None:
        p = policy()
        b = (m([[1], [0]]), m([[1], [2]]))
        total, dense = ad.fixed_aggregate(p, b, (Q(1, 2), Q(1, 2)), (p.id, p.id))
        self.assertEqual(total, m([[1], [1]]))
        self.assertEqual(dense, m([[1, 0], [1, 0]]))
        self.assertEqual(ad.delivery_sensitivity_squared(p, Q(1, 2)), 9)

    def test_scalar_cross_terms_and_exact_rank_growth(self) -> None:
        mean_products = (Q(1) * Q(1) + Q(-1) * Q(-1)) / 2
        product_means = ((Q(1) + Q(-1)) / 2) ** 2
        self.assertEqual((mean_products, product_means), (1, 0))
        a, b = m([[1, 0], [0, 0]]), m([[0, 0], [0, 1]])
        self.assertEqual((rank(a), rank(b), rank(add(a, b))), (1, 1, 2))
        approximation, error2 = ad.rank_one_approximation(add(a, b))
        self.assertAlmostEqual(error2, 1)
        self.assertAlmostEqual(
            approximation[0][0] * approximation[1][1] - approximation[0][1] * approximation[1][0], 0
        )

    def test_full_gram_identity_has_expected_squared_norm(self) -> None:
        for v in range(-2, 3):
            a, b = m([[1, v], [v, 2]]), m([[v, 1], [-1, 2]])
            self.assertEqual(ad.gram_squared(b, a), norm2(multiply(b, a)))

    def test_wrong_basis_version_or_initialization_is_not_accepted(self) -> None:
        p, b = policy(), (m([[1], [0]]), m([[1], [2]]))
        for changed in [
            replace(p, a=m([[0, 1]])),
            replace(p, version="basis2"),
            replace(p, initialization="different"),
        ]:
            with self.assertRaises(ValueError):
                ad.fixed_aggregate(p, b, (Q(1, 2), Q(1, 2)), (changed.id, p.id))

    def test_rounding_order_and_actual_dense_bound(self) -> None:
        p = ad.FixedFactor(m([[1]]), "a", "zero", Q(1), Q(1), Q(1))
        b1, b2 = m([[Q(2, 5)]]), m([[Q(3, 5)]])
        _, exact = ad.fixed_aggregate(p, (b1, b2), (Q(1, 2), Q(1, 2)), (p.id, p.id))
        rounded_before = scale(add(ad.delivered(p, b1), ad.delivered(p, b2)), Q(1, 2))
        rounded_after = ad.delivered(p, scale(add(b1, b2), Q(1, 2)))
        self.assertEqual(exact, m([[Q(1, 2)]]))
        self.assertNotEqual(rounded_before, rounded_after)
        with self.assertRaises(ValueError):
            ad.delivered(replace(p, dense_bound=Q(7, 10)), b2)
        with self.assertRaises(ValueError):
            ad.delivered(policy(), m([[3], [1]]))

    def test_restricted_row_span_cannot_fit_full_rank_target(self) -> None:
        dense = multiply(m([[1], [0]]), policy().a)
        self.assertEqual(norm2(add(dense, scale(identity(2), Q(-1)))), 1)
        self.assertEqual(norm2(add(identity(2), scale(identity(2), Q(-1)))), 0)


class EligibilityTests(unittest.TestCase):
    def messages(self) -> tuple[ad.ComponentMessage, ...]:
        return (
            ad.ComponentMessage("A", (Q(2), None), "full-state", "i", None),
            ad.ComponentMessage("B", (Q(4), Q(8)), "full-state", "i", None),
        )

    def aggregate(self, messages: tuple[ad.ComponentMessage, ...]) -> tuple[Q, ...]:
        return ad.heterogeneous(
            messages,
            ((True, False), (True, True)),
            (Q(1), Q(1)),
            (Q(0), Q(0)),
            "i",
            (None, None),
            "record",
        )

    def test_source_denominators_and_padding_counterexample(self) -> None:
        self.assertEqual(self.aggregate(self.messages()), (3, 8))
        self.assertNotEqual(self.aggregate(self.messages()), (3, 4))

    def test_silent_mixed_state_delta_wrong_mask_and_initialization_reject(self) -> None:
        a, b = self.messages()
        for bad in [
            replace(a, kind="initialization-delta"),
            replace(a, initialization="other"),
            replace(a, values=(Q(2), Q(0))),
            replace(a, hidden_state="unbound"),
        ]:
            with self.assertRaises(ValueError):
                self.aggregate((bad, b))

    def test_delta_initialization_and_hidden_client_unit_are_explicit(self) -> None:
        messages = tuple(
            replace(m, kind="initialization-delta", hidden_state="state") for m in self.messages()
        )
        args = (
            messages,
            ((True, False), (True, True)),
            (Q(1), Q(1)),
            (Q(10), Q(20)),
            "i",
            ("state", "state"),
        )
        self.assertEqual(ad.heterogeneous(*args, "client", whole_client_bound=Q(16)), (13, 28))
        self.assertEqual(ad.heterogeneous_sensitivity_squared(args[1], args[2], Q(16)), 1024)
        with self.assertRaises(ValueError):
            ad.heterogeneous(*args, "record")

    def test_hidden_state_can_change_all_gradients(self) -> None:
        row = ad.hidden_state_counterexample(4, Q(1))
        self.assertEqual(row["actual_change"], 2)
        self.assertEqual(row["invalid_one_gradient_bound"], Q(1, 2))


class CapacityTests(unittest.TestCase):
    def workload(self) -> cp.Workload:
        return cp.Workload(
            10_000_000, 20_000, 65_536, 32, 40, 2048, Q(1, 200), 64, Q(60), 1_000_000_000, 32
        )

    def test_source_capacity_assumptions_and_conditional_partials(self) -> None:
        x = self.workload().metrics()
        self.assertEqual(x["client_upload_bytes"], 5_242_880_000)
        self.assertEqual(x["conditional_partial_bytes"], 10_485_760)
        self.assertFalse(x["accumulator_range_certified"])
        self.assertEqual(x["proof_traffic_bytes"], 40_960_000)
        self.assertEqual(x["verification_cpu_seconds"], 100)
        self.assertEqual(x["ideal_verification_seconds"], Q(25, 16))
        self.assertEqual(x["ideal_ingress_seconds"], Q(131072, 3125))

    def test_width_replication_and_scale_axes_are_distinct(self) -> None:
        base = self.workload()
        with self.assertRaises(ValueError):
            replace(base, weighted_coordinate_bound=2**31 - 1).metrics()
        wide = replace(base, weighted_coordinate_bound=2**31 - 1, accumulator_bits=64, replicas=3)
        x = wide.metrics()
        self.assertTrue(x["accumulator_range_certified"])
        self.assertEqual(
            x["conditional_partial_bytes"], 2 * base.metrics()["conditional_partial_bytes"]
        )
        self.assertEqual(x["replicated_upload_bytes"], 3 * x["client_upload_bytes"])
        records = replace(base, records_per_client=5).metrics()
        self.assertEqual(records["client_upload_bytes"], base.metrics()["client_upload_bytes"])
        self.assertEqual(records["records"], 100_000)

    def test_burst_straggler_dropout_and_invalid_work_are_retained(self) -> None:
        jobs = tuple(cp.Job(str(i), Q(0), Q(1), Q(1)) for i in range(4))
        results = cp.simulate(jobs + (cp.Job("d", Q(0), Q(1), Q(1), dropout=True),), (Q(1), Q(1)))
        self.assertEqual([r["status"] for r in results].count("accepted"), 2)
        self.assertEqual([r["status"] for r in results].count("deadline"), 2)
        self.assertEqual([r["status"] for r in results].count("dropout"), 1)
        overloaded = cp.simulate(jobs, (Q(1),), queue_limit=1)
        self.assertEqual([r["status"] for r in overloaded].count("overload"), 2)
        invalid = cp.simulate((cp.Job("x", Q(0), Q(2), Q(4), valid=False),), (Q(1),))
        self.assertEqual(invalid[0]["status"], "invalid")
        self.assertEqual(invalid[0]["latency"], 2)

    def test_restart_idempotence_missing_payload_and_changed_roster(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.sqlite"
            ledger = cp.ReleaseLedger(path, "s", ("a", "b"), "context")
            ledger.submit("a", 2)
            with self.assertRaises(ValueError):
                ledger.finalize()
            ledger.submit("b", 3)
            with self.assertRaises(RuntimeError):
                ledger.finalize(interrupt_before_commit=True)
            self.assertEqual(ledger.db.execute("SELECT COUNT(*) FROM output").fetchone(), (0,))
            expected = ledger.finalize()
            ledger.close()
            replay = cp.ReleaseLedger(path, "s", ("a", "b"), "context")
            replay.submit("a", 2)
            self.assertEqual(replay.finalize(), expected)
            with self.assertRaises(ValueError):
                replay.submit("a", 4)
            replay.close()
            with self.assertRaises(ValueError):
                cp.ReleaseLedger(path, "s", ("a",), "context")

    def test_two_authority_connections_do_not_duplicate_local_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.sqlite"
            ledger = cp.ReleaseLedger(path, "s", ("a",), "c")
            ledger.submit("a", 7)
            ledger.close()

            def finalize(_: int) -> tuple[str, int]:
                other = cp.ReleaseLedger(path, "s", ("a",), "c")
                try:
                    return other.finalize()
                finally:
                    other.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                outputs = list(pool.map(finalize, [0, 1]))
            self.assertEqual(outputs[0], outputs[1])


class ReceiptTests(unittest.TestCase):
    def test_required_ci_does_not_substitute_reference_only(self) -> None:
        import yaml

        workflow = yaml.load(
            (ROOT / ".github/workflows/cpu.yml").read_text(), Loader=yaml.BaseLoader
        )
        steps = workflow["jobs"]["proof"]["steps"]
        model_steps = [s["run"] for s in steps if "scripts/models" in s.get("run", "")]
        self.assertEqual(model_steps, ["./scripts/models"])

    def test_reference_only_cannot_satisfy_genuine_or_publication(self) -> None:
        import copy

        (ROOT / ".tools").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".tools") as temporary:
            path = Path(temporary) / "manifest.json"
            with patch.object(ex, "MANIFEST", path):
                self.assertEqual(ex.run(references_only=True), 0)
            record = load(path)
            ex.validate_manifest(record)
            for change in ["genuine", "publication", "fake-workflow", "nonfinite", "missing-trial"]:
                bad = copy.deepcopy(record)
                if change == "genuine":
                    bad.update(mode="genuine-and-reference", status="completed")
                elif change == "publication":
                    bad["publication_review"]["approved"] = True
                elif change == "fake-workflow":
                    bad["provenance"]["execution_kind"] = "local"
                    bad["provenance"]["workflow_run"] = 1
                elif change == "nonfinite":
                    bad["repetitions"][0]["reference_seconds"] = float("nan")
                else:
                    bad["requested_repetitions"] = 2
                with self.assertRaises(Invalid):
                    ex.validate_manifest(bad)

    def test_failed_native_attempt_retains_elapsed_and_unrun_repetitions(self) -> None:
        (ROOT / ".tools").mkdir(exist_ok=True)
        provenance = ex.provenance()
        with tempfile.TemporaryDirectory(dir=ROOT / ".tools") as temporary:
            path = Path(temporary) / "manifest.json"
            with (
                patch.object(ex, "MANIFEST", path),
                patch.object(ex, "provenance", return_value=provenance),
            ):
                with patch("fzkml_models.experiment.subprocess.run", side_effect=FileNotFoundError):
                    self.assertEqual(ex.run(repetitions=2), 1)
            record = load(path)
            self.assertEqual(record["status"], "failed")
            self.assertIsNotNone(record["repetitions"][0]["native_seconds"])
            self.assertEqual(record["repetitions"][1]["status"], "pending")
            self.assertIsNone(record["repetitions"][1]["native_seconds"])
            ex.validate_manifest(record)

    def test_scoped_engineering_claims_reuse_shared_schema(self) -> None:
        validate_claims(load(ROOT / "claims/models-v1.json"))
        with self.assertRaises(Invalid):
            ex.validate_native({"version": 1, "proof_mode": "mock"})


if __name__ == "__main__":
    unittest.main()
