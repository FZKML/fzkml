from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import unittest
from dataclasses import replace
from fractions import Fraction as F
from typing import Any, Literal

from fzkml_ci.benchmark import summarize_times
from fzkml_ci.validate import ROOT, Invalid
from fzkml_research.audit import AuditPlan, Trial, audit
from fzkml_research.backends import Assurance, BackendEvidence, compare_backends
from fzkml_research.compression import (
    CompressionChain,
    Compressor,
    dense_bound_from_projection,
    encode,
    kernel_vector,
    norm_squared,
    replacement_l2_bound,
)
from fzkml_research.evaluation import (
    Classifier,
    HoldoutLedger,
    SyntheticRecord,
    counts,
    measured_gap,
    private_gap_certificate,
)
from fzkml_research.experiment import worker
from fzkml_research.kernels import Matrix, reference, transposed
from fzkml_research.profiling import Event, LiveSample, QualityEvent, amdahl, batch_cost, summarize
from fzkml_research.statistics import binomial_tail, lower_bound, rate_test_power, upper_bound

GOLDEN = json.loads((ROOT / "assets/public/privacy-performance-golden-v1.json").read_text())


def golden(identifier: str) -> dict[str, Any]:
    return next(v for v in GOLDEN["vectors"] if v["id"] == identifier)


def vector(*values: str | int) -> tuple[F, ...]:
    return tuple(map(F, values))


class StatisticalTests(unittest.TestCase):
    def test_exact_fraction_distribution_and_coverage(self) -> None:
        # Independent rational PMF oracle: no implementation tail/inversion reuse.
        for n in range(1, 9):
            for p in (F(1, 10), F(1, 2), F(9, 10)):
                masses = [math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)]
                for k in range(n + 1):
                    self.assertAlmostEqual(
                        binomial_tail(k, n, float(p)), float(sum(masses[k:])), places=14
                    )
                lower_failure = sum(
                    masses[k] for k in range(n + 1) if lower_bound(k, n, 0.05) > float(p)
                )
                upper_failure = sum(
                    masses[k] for k in range(n + 1) if upper_bound(k, n, 0.05) < float(p)
                )
                self.assertLessEqual(lower_failure, F(1, 20))
                self.assertLessEqual(upper_failure, F(1, 20))

    def test_manuscript_audit_golden(self) -> None:
        case = golden("audit-ch48-2")
        inputs, expected, tol = case["verified_inputs"], case["expected"], case["tolerances"]
        p = lower_bound(inputs["events_D"], inputs["n_D"], inputs["one_sided_error"])
        q = upper_bound(inputs["events_D_prime"], inputs["n_D_prime"], inputs["one_sided_error"])
        self.assertAlmostEqual(p, expected["p_lower"], delta=tol["probability"])
        self.assertAlmostEqual(q, expected["q_upper"], delta=tol["probability"])
        self.assertAlmostEqual(q, 1 - 0.025 ** (1 / 1000), places=14)
        self.assertAlmostEqual(
            math.log((p - inputs["delta"]) / q), expected["epsilon_lower"], delta=tol["epsilon"]
        )

    def test_bound_edges_and_invalid_inputs(self) -> None:
        self.assertEqual(lower_bound(0, 5, 0.025), 0)
        self.assertEqual(upper_bound(5, 5, 0.025), 1)
        self.assertAlmostEqual(lower_bound(5, 5, 0.025), 0.025**0.2, places=14)
        for k, n, error in [
            (1, 0, 0.05),
            (-1, 10, 0.05),
            (11, 10, 0.05),
            (True, 1, 0.05),
            (1, 10, 0),
            (1, 10, float("nan")),
        ]:
            with self.assertRaises(Invalid):
                lower_bound(k, n, error)
        power = rate_test_power(10, 0.1, 0.5, 0.05)
        self.assertEqual(power["critical_events"], 4)
        self.assertEqual(power["power"], 53 / 64)


def trials(n: int = 20) -> list[Trial]:
    sides: tuple[Literal["D"], Literal["D-prime"]] = ("D", "D-prime")
    return [
        Trial(
            f"synthetic:t-{side}-{i}",
            f"synthetic:model-{side}-{i}",
            f"synthetic:rng-{side}-{i}",
            side,
            "completed",
            i < n // 2 if side == "D" else False,
        )
        for side in sides
        for i in range(n)
    ]


def plan() -> AuditPlan:
    return AuditPlan(
        "synthetic:fixed-attack",
        "released-model-observer",
        "add-remove-one-record",
        "record",
        "synthetic:predeclared-threshold",
        True,
        True,
        (),
    )


class AuditTests(unittest.TestCase):
    def test_failed_trials_and_inconclusive_outcome_retained(self) -> None:
        data = trials()
        data[0] = replace(data[0], status="failed", event=None)
        report = audit(plan(), data)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["counts"]["D"]["invited"], 20)
        self.assertEqual(report["counts"]["D"]["completed"], 19)
        self.assertIsNone(report["epsilon_lower_bound"])
        report = audit(replace(plan(), claimed_epsilon=100), trials())
        self.assertEqual(report["status"], "inconclusive")
        self.assertIn("cannot certify DP", report["limitations"][0])

    def test_correlated_models_rng_calibration_and_adaptive_threshold_rejected(self) -> None:
        for field in ("trial_id", "model_run_id", "randomization_id"):
            data = trials()
            data[1] = replace(data[1], **{field: getattr(data[0], field)})
            with self.assertRaises(Invalid):
                audit(plan(), data)
        for bad in [
            replace(plan(), preregistered=False),
            replace(plan(), independent_mechanism_runs=False),
            replace(plan(), calibration_run_ids=(trials()[0].model_run_id,)),
        ]:
            with self.assertRaises(Invalid):
                audit(bad, trials())

    def test_multiplicity_and_power_are_visible(self) -> None:
        first = audit(plan(), trials())
        adjusted = audit(replace(plan(), registered_tests=10), trials())
        self.assertLessEqual(adjusted["epsilon_lower_bound"], first["epsilon_lower_bound"])
        self.assertEqual(adjusted["registered_tests"], 10)
        self.assertIn("not estimated", adjusted["power"])


class CompressionTests(unittest.TestCase):
    def test_manuscript_error_feedback_and_postclip(self) -> None:
        case = golden("error-feedback-ch54-4")
        update = tuple(map(F, case["verified_inputs"]["fresh"]))
        chain = CompressionChain(Compressor("top1-v1", "top1", 2, F(1)), "synthetic:model-v1")
        first = chain.step(
            update,
            expected_digest=chain.snapshot.digest(),
            round_id=0,
            model_lineage="synthetic:model-v1",
        )
        self.assertEqual(first, tuple(map(F, case["expected"]["first_sent"])))
        self.assertEqual(chain.snapshot.residual, tuple(map(F, case["expected"]["first_residual"])))
        sent = chain.step(
            update,
            expected_digest=chain.snapshot.digest(),
            round_id=1,
            model_lineage="synthetic:model-v1",
        )
        self.assertEqual(sent, tuple(map(F, case["expected"]["second_sent"])))
        self.assertGreater(norm_squared(sent), 1)
        safe = CompressionChain(
            Compressor("postclip-v1", "top1-postclip", 2, F(1)), "synthetic:model-v1"
        )
        for i in range(10):
            before = safe.snapshot.residual
            y = safe.step(
                update,
                expected_digest=safe.snapshot.digest(),
                round_id=i,
                model_lineage="synthetic:model-v1",
            )
            self.assertLessEqual(norm_squared(y), 1)
            self.assertEqual(
                tuple(a + b - c for a, b, c in zip(before, update, y, strict=True)),
                safe.snapshot.residual,
            )

    def test_noninjective_kernel_and_dense_bound_rejected(self) -> None:
        matrix = (vector(1, 1, 0), vector(0, 0, 1))
        kernel = kernel_vector(matrix)
        self.assertGreater(norm_squared(kernel), 0)
        for scale in [1, 100, 10000]:
            large = tuple(scale * v for v in kernel)
            self.assertFalse(any(encode(matrix, large)))
            self.assertEqual(norm_squared(large), scale**2 * norm_squared(kernel))
        with self.assertRaises(ValueError):
            dense_bound_from_projection(matrix)
        with self.assertRaises(Invalid):
            kernel_vector((vector(1, 0), vector(0, 1)))

    def test_state_lineage_version_and_randomness_bound(self) -> None:
        c = Compressor("random-v1", "unbiased-random1", 2, F(1), (0, 1))
        chain = CompressionChain(c, "synthetic:model")
        initial = chain.snapshot.digest()
        y = chain.step(
            vector(1, 0), expected_digest=initial, round_id=0, model_lineage="synthetic:model"
        )
        self.assertEqual(y, vector(2, 0))
        self.assertEqual(replacement_l2_bound(c, 0, False), 4)
        self.assertEqual(replacement_l2_bound(c, 1, True), 8)
        with self.assertRaises(Invalid):
            chain.step(
                vector(0, 0), expected_digest=initial, round_id=0, model_lineage="synthetic:model"
            )
        with self.assertRaises(Invalid):
            chain.step(
                vector(0, 0),
                expected_digest=chain.snapshot.digest(),
                round_id=1,
                model_lineage="other",
            )
        chain.compressor = replace(c, version="changed")
        with self.assertRaises(Invalid):
            chain.step(
                vector(0, 0),
                expected_digest=chain.snapshot.digest(),
                round_id=1,
                model_lineage="synthetic:model",
            )


def classifier_records() -> tuple[Classifier, tuple[SyntheticRecord, ...]]:
    classifier = Classifier(vector(1), F(0))
    data = (
        SyntheticRecord("synthetic:a", 0, True, vector(1)),
        SyntheticRecord("synthetic:b", 0, True, vector(-1)),
        SyntheticRecord("synthetic:c", 1, True, vector(1)),
    )
    return classifier, data


class EvaluationTests(unittest.TestCase):
    def test_manuscript_fairness_golden_and_allowances(self) -> None:
        case = golden("fairness-ch56-4")
        x = case["verified_inputs"]
        kwargs = dict(
            epsilon=x["epsilon"],
            alpha=x["alpha"],
            beta=x["beta"],
            fixed_classifier=True,
            iid_units=True,
            ideal_laplace_assumption=True,
        )
        base = private_gap_certificate(tuple(x["noisy_denominators"]), x["noisy_gap"], **kwargs)
        self.assertAlmostEqual(
            base["noise_bound"],
            case["expected"]["noise_bound"],
            delta=case["tolerances"]["noise_bound"],
        )
        self.assertAlmostEqual(
            base["upper_bound"],
            case["expected"]["upper_bound"],
            delta=case["tolerances"]["upper_bound"],
        )
        self.assertEqual(base["confidence"], 0.95)
        more = private_gap_certificate(
            (1000, 100),
            0.04,
            missing_fractions=(0.01, 0.02),
            distribution_shift_tv=(0.03, 0.04),
            **kwargs,
        )
        self.assertAlmostEqual(more["upper_bound"], base["upper_bound"] + 0.1)
        for changed in [
            dict(fixed_classifier=False),
            dict(iid_units=False),
            dict(ideal_laplace_assumption=False),
        ]:
            opts = {**kwargs, **changed}
            self.assertEqual(
                private_gap_certificate((1000, 100), 0.04, **opts)["status"], "inconclusive"
            )
        self.assertIsNone(private_gap_certificate((1000, 1), 0.04, **kwargs)["upper_bound"])
        with self.assertRaises(Invalid):
            private_gap_certificate((1000, 100, 100), 0.04, **kwargs)  # type: ignore[arg-type]

    def test_frozen_model_holdout_query_budget_and_idempotence(self) -> None:
        classifier, data = classifier_records()
        with self.assertRaises(Invalid):
            Classifier((1.0,), F(0))  # type: ignore[arg-type]
        with self.assertRaises(Invalid):
            classifier.predict((float("nan"),))  # type: ignore[arg-type]
        self.assertEqual(counts(classifier, data), (1, 2, 1, 1))
        self.assertEqual(measured_gap((1, 2, 1, 1)), F(1, 2))
        ledger = HoldoutLedger(
            "model-observer", "synthetic:holdout-v1", "synthetic-record", classifier.digest(), F(2)
        )
        first = ledger.release("synthetic:q1", classifier, data, F(1), lambda: 0.0)
        cached = ledger.release("synthetic:q1", classifier, data, F(1), lambda: 999.0)
        self.assertEqual(first, cached)
        self.assertEqual(ledger.spent, 1)
        ledger.release("synthetic:q2", classifier, data, F(1), lambda: 0.0)
        self.assertEqual(ledger.spent, 2)
        with self.assertRaises(Invalid):
            ledger.release("synthetic:q3", classifier, data, F(1), lambda: 0.0)
        with self.assertRaises(Invalid):
            ledger.release(
                "synthetic:q1", replace(classifier, threshold=F(2)), data, F(1), lambda: 0.0
            )
        with self.assertRaises(Invalid):
            ledger.release("synthetic:q-new", classifier, data[:-1], F(1), lambda: 0.0)
        with self.assertRaises(Invalid):
            counts(classifier, (data[0], data[0]))

    def test_failed_noise_does_not_refund_privacy_reservation(self) -> None:
        classifier, data = classifier_records()
        ledger = HoldoutLedger(
            "observer", "synthetic:v1", "synthetic-record", classifier.digest(), F(1)
        )
        with self.assertRaises(Invalid):
            ledger.release("synthetic:q", classifier, data, F(1), lambda: float("nan"))
        self.assertEqual(ledger.spent, 1)
        with self.assertRaises(Invalid):
            ledger.release("synthetic:q", classifier, data, F(1), lambda: 0.0)

    def test_count_vector_l1_sensitivity_two_on_add_remove(self) -> None:
        classifier, data = classifier_records()
        base = counts(classifier, data)
        for group in (0, 1):
            for positive in (False, True):
                for feature in (-1, 1):
                    neighbor = counts(
                        classifier,
                        data
                        + (SyntheticRecord("synthetic:new", group, positive, vector(feature)),),
                    )
                    self.assertLessEqual(
                        sum(abs(a - b) for a, b in zip(base, neighbor, strict=True)), 2
                    )


class ProfileTests(unittest.TestCase):
    def test_manuscript_amdahl_and_batch_golden(self) -> None:
        a = golden("amdahl-ch64-2")
        self.assertEqual(
            amdahl(F(a["verified_inputs"]["f"]), F(a["verified_inputs"]["k"])),
            F(a["expected"]["speedup"]),
        )
        case = golden("batch-ch64-2")
        x = case["verified_inputs"]
        result = batch_cost(F(x["a"]), F(x["c"]), x["b"], F(x["spacing"]))
        for key, value in result.items():
            self.assertEqual(value, F(case["expected"][key]))
        self.assertEqual(
            batch_cost(F(x["a"]), F(x["c"]), 1, F(x["spacing"]))["compute"],
            F(case["expected"]["single_completion"]),
        )

    def test_wall_work_retries_shared_setup_and_joint_memory(self) -> None:
        events = [
            Event("setup", "setup", "a", "setup", 0, 2, 1, setup_mode="cold"),
            Event("bad", "try1", "a", "prove", 2, 6, 3, status="failed", reuse_cost_ids=("setup",)),
            Event("good", "try2", "b", "prove", 2, 8, 5, reuse_cost_ids=("setup",)),
            Event("release", "try2", "b", "release", 8, 10, 1, bytes_sent=12),
        ]
        samples = [LiveSample(0, "a", 10, 3), LiveSample(0, "b", 8, 1), LiveSample(6, "a", 0, 0)]
        result = summarize(
            events,
            samples,
            [QualityEvent(10, F(1, 10), True, True)],
            budget_ns=20,
            quality_target=F(1, 5),
        )
        self.assertEqual(result["wall_ns"], 10)
        self.assertEqual(result["aggregate_worker_occupied_ns"], 14)
        self.assertEqual(result["aggregate_cpu_ns"], 10)
        self.assertEqual(result["retries"], 1)
        self.assertEqual(result["sampled_joint_live_peaks"]["ram_bytes"], 18)
        self.assertIsNone(result["sampled_joint_live_peaks"]["vram_bytes"])
        self.assertEqual(result["failed_cost_ids"], ["bad"])
        self.assertEqual(result["time_to_certified_quality"]["time_ns"], 10)
        censored = summarize(events, [], [], budget_ns=20, quality_target=F(1, 5))
        self.assertIsNone(censored["time_to_certified_quality"]["time_ns"])
        self.assertIsNone(censored["sampled_joint_live_peaks"]["ram_bytes"])

    def test_double_counting_overlap_and_fake_quality_rejected(self) -> None:
        event = Event("a", "one", "worker", "train", 0, 10, 8)
        for events in [
            [event, event],
            [event, replace(event, cost_id="b", start_ns=5, end_ns=15)],
            [replace(event, reuse_cost_ids=("absent",))],
        ]:
            with self.assertRaises(Invalid):
                summarize(events, [], [], budget_ns=20, quality_target=F(0))
        with self.assertRaises(Invalid):
            summarize(
                [event], [], [QualityEvent(10, F(0), True, True)], budget_ns=20, quality_target=F(0)
            )


class KernelTests(unittest.TestCase):
    def test_actual_worker_interface_without_performance_threshold(self) -> None:
        first, second = worker("reference"), worker("transposed")
        self.assertEqual(first["result_digest"], second["result_digest"])
        self.assertGreater(first["rss_bytes"], 0)
        self.assertEqual(first["profile"]["complete_protected_path"]["prove"], "not-run")
        self.assertEqual(first["profile"]["time_to_certified_quality"]["status"], "right-censored")
        self.assertIsNone(first["profile"]["sampled_joint_live_peaks"]["ram_bytes"])

    def test_independent_hand_vectors_and_exhaustive_small_ring(self) -> None:
        a: Matrix = ((1, 2), (3, 4))
        b: Matrix = ((5, 6), (7, 8))
        expected: Matrix = ((19, 22), (43, 50))
        self.assertEqual(reference(a, b, 97), expected)
        self.assertEqual(transposed(a, b, 97), expected)
        for modulus in (97, 2**61 - 1):
            edge = (((modulus - 1,),), ((modulus - 1,),))
            self.assertEqual(transposed(*edge, modulus), ((1,),))
            self.assertEqual(reference(*edge, modulus), ((1,),))
        # Independent 1x2 by 2x1 polynomial, including negative and residue boundaries.
        for x in range(-4, 5):
            for y in range(-4, 5):
                expected = (((x * (y - 1) + (x + 1) * y) % 7,),)
                self.assertEqual(transposed(((x, x + 1),), ((y - 1,), (y,)), 7), expected)
        rng = random.Random(20261124)
        for _ in range(30):
            a = tuple(tuple(rng.randint(-1000, 1000) for _ in range(3)) for _ in range(2))
            b = tuple(tuple(rng.randint(-1000, 1000) for _ in range(2)) for _ in range(3))
            self.assertEqual(reference(a, b, 97), transposed(a, b, 97))
        for a, b, p in [(((True,),), ((1,),), 7), (((1,),), ((1,),), 1), (((1, 2),), ((1,),), 7)]:
            with self.assertRaises(Invalid):
                transposed(a, b, p)


def backend_record(name: str) -> dict[str, Any]:
    row: dict[str, Any] = json.loads((ROOT / "examples/results.json").read_text())["results"][0]
    row["scenario"].update(
        backend=name,
        relation_version="test-relation",
        numerical_semantics="test-numeric",
        security_mode="research",
    )
    for key in ("parameters_digest", "program_digest", "circuit_digest", "key_digest"):
        row["scenario"][key] = "sha256:" + "1" * 64
    row["provenance"].update(
        source_commit="1" * 40, workflow_run=1, dependency_digest="sha256:" + "1" * 64
    )
    row["outcome"] = {
        "status": "successful",
        "reason": "Fabricated validator fixture only; never real backend evidence.",
    }
    row["repetitions"] = [
        {
            "id": f"r{i}",
            "attempt": 1,
            "status": "successful",
            "timeout": False,
            "excluded": False,
            "reason": "Synthetic metadata fixture only.",
            "quality": "pass",
            "measurements": [{"phase": "total", "quantity": "time", "unit": "s", "value": v}],
        }
        for i, v in enumerate((1, 2))
    ]
    row["benchmark"] = {
        "workload_digest": "sha256:" + "1" * 64,
        "warmups": 0,
        "setup_amortization": "none",
        "cached_work": "none",
        "quality_threshold": "synthetic fixture only",
        "phases": {
            p: ("measured" if p == "total" else "unavailable")
            for p in ["setup", "witness", "prove", "aggregate", "verify", "transfer", "total"]
        },
        "resources": {
            p: "unavailable:synthetic-metadata-test"
            for p in ["peak_memory", "proof_bytes", "communication"]
        },
    }
    return row


class BackendTests(unittest.TestCase):
    def test_unavailable_and_different_assurances_never_selected(self) -> None:
        required = Assurance(
            "test-relation",
            "test-numeric",
            "exact-training-transition",
            "aggregator",
            "full-training",
            "test-assumptions",
            "test-setup",
            "test-binding",
        )
        available = BackendEvidence(
            "test-a",
            required,
            "available",
            "Synthetic validator fixture.",
            "test-review",
            backend_record("test-a"),
        )
        unavailable = BackendEvidence(
            "test-b", required, "not-run", "Adapter unavailable.", None, None
        )
        report = compare_backends(required, [available, unavailable])
        self.assertEqual(report["status"], "inconclusive")
        self.assertIsNone(report["selection"])
        modes: tuple[
            Literal["specialized-property", "recursion", "attestation", "arithmetic-only"], ...
        ] = ("specialized-property", "recursion", "attestation", "arithmetic-only")
        for mode in modes:
            other = replace(available, backend="test-b", assurance=replace(required, mode=mode))
            self.assertTrue(compare_backends(required, [other])["excluded"])

    def test_matched_results_reuse_shared_comparison_and_reject_wrong_hardware(self) -> None:
        assurance = Assurance(
            "test-relation",
            "test-numeric",
            "test-guarantee",
            "test-observer",
            "full-training",
            "test-security",
            "test-setup",
            "test-binding",
        )
        a = BackendEvidence(
            "a", assurance, "available", "Synthetic fixture.", "test-review", backend_record("a")
        )
        b = replace(a, backend="b", result=backend_record("b"))
        report = compare_backends(assurance, [a, b])
        self.assertEqual(report["status"], "diagnostic")
        assert b.result is not None
        changed = copy.deepcopy(b.result)
        changed["provenance"]["hardware"]["cpu"] = "different"
        report = compare_backends(assurance, [a, replace(b, result=changed)])
        self.assertEqual(report["comparisons"][0]["status"], "incomparable")
        changed = copy.deepcopy(b.result)
        changed["scenario"]["security_mode"] = "synthetic-test"
        with self.assertRaises(Invalid):
            compare_backends(assurance, [replace(b, result=changed)])


class SourceTests(unittest.TestCase):
    def test_retained_profile_integrity_and_raw_aggregation(self) -> None:
        path = ROOT / "experiments/m3-m4/native-profile-v1.json"
        data = json.loads(path.read_text())
        expected = (path.with_suffix(".sha256")).read_text().split()[0]
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
        self.assertRegex(data["execution_origin"]["source_commit"], r"^[a-f0-9]{40}$")
        self.assertEqual(data["execution_origin"]["kind"], "local")
        self.assertIsNone(data["execution_origin"]["workflow_run"])
        all_results = set()
        for index, name in enumerate(("reference", "transposed")):
            rows = data["raw_profiles"][name]
            self.assertEqual(len(rows), data["plan"]["repetitions"])
            for row in rows:
                events = [Event(**event) for event in row["ledger"]["events"]]
                samples = [LiveSample(**sample) for sample in row["ledger"]["resource_samples"]]
                recomputed = summarize(
                    events, samples, [], budget_ns=20_000_000_000, quality_target=F(0)
                )
                for key, value in recomputed.items():
                    self.assertEqual(row["profile"][key], value)
                self.assertGreaterEqual(row["end_to_end_ns"], row["profile"]["wall_ns"])
                self.assertEqual(
                    row["launch_import_and_ipc_ns"],
                    row["end_to_end_ns"] - row["profile"]["wall_ns"],
                )
                all_results.add(row["result_digest"])
            summary = summarize_times([row["end_to_end_ns"] / 1e9 for row in rows], 0, 0)
            self.assertEqual(data["comparison"]["distributions"][index], summary)
        self.assertEqual(len(all_results), 1)
        self.assertEqual(data["gpu"]["status"], "not-run")
        self.assertEqual(data["backend_bakeoff"]["status"], "not-run")

    def test_every_golden_has_verified_source_equation_and_inputs(self) -> None:
        self.assertEqual(GOLDEN["source"]["author_declared_edition"], None)
        self.assertEqual(len(GOLDEN["source"]["markdown_export_sha256"]), 64)
        for case in GOLDEN["vectors"]:
            self.assertTrue(case["equation"] and case["verified_inputs"] and case["expected"])
            self.assertLess(*case["docs_utf16_range"])


if __name__ == "__main__":
    unittest.main()
