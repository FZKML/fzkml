"""Independent arithmetic/law/source reproduction, never a universal DP proof."""

from __future__ import annotations

# ruff: noqa: E402
import ast
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from fzkml_protocol.geometric import Geometric  # noqa:E402
from fzkml_research.audit import AuditPlan, Trial, audit  # noqa:E402
from fzkml_research.compression import dense_bound_from_projection, kernel_vector  # noqa:E402
from fzkml_research.evaluation import private_gap_certificate  # noqa:E402
from fzkml_research.statistics import binomial_tail, lower_bound, upper_bound  # noqa:E402
from fzkml_transcript.algebra import conditional_covariance, matrix, squared_separation  # noqa:E402
from fzkml_transcript.entropy import EntropyPolicy
from fzkml_transcript.ledger import (
    LedgerPolicy,
    MechanismContract,
    Observation,
    ReferenceAccountant,
)
from fzkml_transcript.sampling import dependent_variance, weighted_moments  # noqa:E402
from python.fzkml_math import numeric  # noqa:E402
from python.fzkml_math.arithmetic import (
    floating_scalar,
    lift_field,
    manuscript_step,
    no_wrap_residual,
    rounded,
    signed_field,
)  # noqa:E402
from python.fzkml_math.costs import amdahl, batch  # noqa:E402
from python.fzkml_math.datasets import Record, representation_digest, split, synthetic  # noqa:E402
from python.fzkml_math.distributions import (
    conditioned,
    cyclic_geometric,
    exact_uniform_cdf,
    hockey_stick,
    law,
    postprocess,
)  # noqa:E402
from python.fzkml_math.private_v2 import (
    CONTRACT_SHA256,
    ContextV2,
    StatementV2,
    require_next,
)
from python.fzkml_math.private_v2 import (
    arithmetic as private_arithmetic,
)
from python.fzkml_math.private_v2 import (
    synthetic as private_context,
)
from python.fzkml_math.sensitivity import FixedMean, rounded_change_bound  # noqa:E402
from reference import numeric as compatibility  # noqa:E402


class ArithmeticTests(unittest.TestCase):
    def test_canonical_oracle_and_original_vectors_unchanged(self) -> None:
        self.assertIs(compatibility.evaluate, numeric.evaluate)
        path = ROOT / "assets/public/numeric-v1.json"
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "454af1102b6eff77c878b9012600320bdb25c797447ff067c716ea9242d693b8",
        )
        tree = ast.parse((ROOT / "python/fzkml_math/numeric.py").read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(
            any(s and ("rust" in s or "torch" in s or "fzkml_native" in s) for s in imports)
        )
        for item in json.loads(path.read_text())["valid"]:
            self.assertEqual(
                numeric.evaluate(bytes.fromhex(item["canonical_hex"])), item["expected"]
            )

    def test_external_rust_cli_extended_vectors_when_built(self) -> None:
        binary = ROOT / "target/release/fzkml-contract"
        if not binary.is_file():
            self.skipTest("External Rust CLI not built; scripts/validate-s02 builds and checks it.")
        result = json.loads(
            subprocess.check_output(
                [sys.executable, str(ROOT / "scripts/s02_conformance.py"), str(binary)],
                cwd=ROOT,
                timeout=120,
            )
        )
        self.assertEqual(result["accepted"], 129)
        self.assertEqual(result["wrong_output_rejections"], 129)

    def test_reused_same_repository_sources_are_exact(self) -> None:
        document = json.loads((ROOT / "python/reference-sources.json").read_text())
        for entry in document["files"]:
            self.assertEqual(
                hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest(), entry["sha256"]
            )

    def test_extended_canonical_and_exceptional_vectors(self) -> None:
        data = json.loads((ROOT / "tests/vectors/synthetic/s02-boundaries-v1.json").read_text())
        self.assertEqual(data["contract_version"], numeric.CONTRACT_VERSION)
        for item in data["valid"]:
            wire = bytes.fromhex(item["canonical_hex"])
            self.assertEqual(numeric.evaluate(wire), item["expected"])
            self.assertEqual(numeric.encode(*numeric.decode(wire)), wire)
        for wire in data["invalid_hex"]:
            with self.assertRaises(ValueError):
                numeric.decode(bytes.fromhex(wire))
        for args in [
            (0, [], [], []),
            (0, [0] * 3, [0] * 3, [0] * 3),
            (True, [0] * 3, [0] * 3, [1] * 3),
            (2**100, [0] * 3, [0] * 3, [1] * 3),
        ]:
            with self.assertRaises(ValueError):
                numeric.encode(*args)
        for value in (math.nan, math.inf, -math.inf, 2.01):
            with self.assertRaises(ValueError):
                numeric.quantize(value)

    def test_arbitrary_precision_ties_negative_and_denominators(self) -> None:
        for n in range(-65, 66):
            for d in range(1, 17):
                q, r = divmod(n, d)
                self.assertEqual(rounded(n, d), q + int(2 * r > d or (2 * r == d and q % 2 == 1)))
                self.assertEqual(rounded(n, d, "nearest-positive"), math.floor(F(n, d) + F(1, 2)))
        huge = 10**1000
        self.assertEqual(rounded(2 * huge + 1, 2), huge)
        self.assertEqual(rounded(-2 * huge - 1, 2), -huge)
        self.assertEqual(rounded(1, 2), 0)
        self.assertEqual(rounded(1, 2, "nearest-positive"), 1)
        for d in (0, -1):
            with self.assertRaises(ValueError):
                rounded(1, d)
        with self.assertRaises(ValueError):
            rounded(True, 2)

    def test_signed_field_and_complete_residual_bounds(self) -> None:
        for n in range(-8, 9):
            self.assertEqual(lift_field(signed_field(n, 17, 8), 17, 8), n)
        self.assertEqual((5 * 5 - 8) % 17, 0)
        with self.assertRaises(ValueError):
            no_wrap_residual(17, 17, 17)
        self.assertTrue(no_wrap_residual(0, 17, 16))
        self.assertFalse(no_wrap_residual(1, 17, 16))
        for value in (-1, 17, 18):
            with self.assertRaises(ValueError):
                lift_field(value, 17, 8)

    def test_full_state_rounding_and_float_comparison(self) -> None:
        trace = numeric.evaluate(numeric.encode(1, [0, 0, 8], [0, 0, 8], [1, 1, 2]))
        self.assertEqual(trace["updates"], [1, 1, 2])
        self.assertEqual(trace["numerator"], 6)
        self.assertEqual(trace["denominator"], 4)
        self.assertEqual(trace["output"], 2)
        wrong = 1 + rounded(2, 4)
        self.assertEqual(wrong, 1)
        self.assertNotEqual(wrong, trace["output"])
        exact = numeric.evaluate(numeric.encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1]))
        baseline = floating_scalar(0.5, (1.0, -0.5, 1.5), (1.0, -1.0, 0.5), (1, 2, 1))
        self.assertEqual(baseline, 0.5546875)
        self.assertEqual(F(int(exact["output"]), 16) - F(baseline), F(1, 128))  # type: ignore[arg-type]


class DataTests(unittest.TestCase):
    def test_deterministic_entity_time_and_duplicate_separation(self) -> None:
        rows = synthetic()
        self.assertEqual(rows, synthetic())
        self.assertNotEqual(rows, synthetic(1))
        data = json.loads((ROOT / "tests/vectors/synthetic/s02-data-v1.json").read_text())
        self.assertEqual(data["representation_sha256"], representation_digest(rows))
        parts = split(rows, frozenset({"synthetic:e6", "synthetic:e7"}), 5, 11)
        self.assertFalse(
            {r.entity for r in parts["train"]} & {r.entity for r in parts["evaluation"]}
        )
        self.assertTrue(all(r.time <= 5 for r in parts["train"]))
        self.assertTrue(all(r.time <= 11 for r in parts["evaluation"]))
        self.assertTrue(any(r.duplicate_of is not None for r in parts["excluded"]))
        self.assertFalse(
            {(r.x, r.y) for r in parts["train"]} & {(r.x, r.y) for r in parts["evaluation"]}
        )
        self.assertEqual(sum(map(len, parts.values())), len(rows))
        bad = (
            *rows,
            Record("synthetic:bad", "synthetic:other", "synthetic:source1", 2, 0, 0, "missing"),
        )
        with self.assertRaises(ValueError):
            split(bad, frozenset(), 5, 11)
        with self.assertRaises(ValueError):
            split((*rows, rows[0]), frozenset(), 5, 11)


class SensitivityTests(unittest.TestCase):
    def test_rne_odd_translation_tie_requires_extra_lattice_unit(self) -> None:
        self.assertEqual(rounded(1, 2), 0)
        self.assertEqual(rounded(3, 2), 2)
        self.assertEqual(rounded_change_bound(2, 2), 2)
        self.assertEqual(rounded_change_bound(2, 2, "nearest-positive"), 1)
        for d in range(1, 13):
            for change in range(25):
                maximum = max(abs(rounded(s + change, d) - rounded(s, d)) for s in range(-40, 41))
                self.assertEqual(maximum, rounded_change_bound(change, d))

    def test_exact_finite_sensitivity_and_private_denominator_counterexample(self) -> None:
        for weights in ((1, 1), (1, 2, 1)):
            model = FixedMean(2, weights)
            for adjacency in ("add-remove-zero-slot", "replace-slot"):
                actual, pair = model.enumerate_sensitivity(adjacency)
                self.assertEqual(actual, abs(model.release(pair[0]) - model.release(pair[1])))
                self.assertLessEqual(actual, model.bound(adjacency))
        # Four declared slots; substituting the private nonempty count changes the function.
        self.assertEqual(abs(rounded(2, 1) - rounded(0, 2)), 2)
        self.assertEqual(FixedMean(2, (1, 1, 1, 1)).bound("add-remove-zero-slot"), 1)
        with self.assertRaises(ValueError):
            FixedMean(1, (0,))
        with self.assertRaises(ValueError):
            FixedMean(1, [1, 1])  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            FixedMean(1, (1, 1)).bound("record-unspecified")


class PrivacyMathTests(unittest.TestCase):
    def test_independent_pmf_convolution_and_exact_test_draws(self) -> None:
        for modulus in (3, 5, 7):
            p = cyclic_geometric(2, 3, modulus)
            ref = Geometric(2, 3, modulus).pmf()
            self.assertEqual(tuple(p.values()), ref)

            def shift(k: int, m: int = modulus) -> int:
                return (k + 1) % m

            shifted = postprocess(p, shift)
            self.assertEqual(hockey_stick(p, shifted, F(3, 2)), 0)
            self.assertEqual(hockey_stick(shifted, p, F(3, 2)), 0)
        p = {0: F(1, 3), 1: F(2, 3)}
        counts = Counter(exact_uniform_cdf(p, i) for i in range(3))
        self.assertEqual(counts, {0: 1, 1: 2})
        with self.assertRaises(ValueError):
            exact_uniform_cdf(p, 3)
        with self.assertRaises(ValueError):
            law({0: F(1, 2)})
        # Truncated shifts have support mismatch even when continuous intuition looks harmless.
        self.assertEqual(
            hockey_stick({0: F(1, 2), 1: F(1, 2)}, {1: F(1, 2), 2: F(1, 2)}, F(2)), F(1, 2)
        )

    def test_conditioning_is_not_postprocessing_and_transcript_is_not_marginal(self) -> None:
        p = {-1: F(1, 3), 0: F(1, 3), 1: F(1, 3)}
        self.assertNotEqual(conditioned(p, lambda x: x >= 0), postprocess(p, lambda x: max(0, x)))
        marginal = {0: F(1, 2), 1: F(1, 2)}
        self.assertEqual(hockey_stick(marginal, marginal, F(1)), 0)
        left = {(0, 0): F(1, 2), (1, 1): F(1, 2)}
        right = {(0, 1): F(1, 2), (1, 0): F(1, 2)}
        self.assertEqual(hockey_stick(left, right, F(1)), 1)

    def test_singular_gaussian_support_and_conditioning(self) -> None:
        covariance = matrix([[1, 1], [1, 1]])
        self.assertEqual(squared_separation(covariance, [1, 1]), 1)
        self.assertIsNone(squared_separation(covariance, [1, -1]))
        self.assertEqual(conditional_covariance(matrix([[2, 1], [1, 1]]), [0], [1]), matrix([[1]]))
        with self.assertRaises(ValueError):
            squared_separation(matrix([[1, 2], [2, 1]]), [1, 1])

    def test_dependent_inclusion_and_noninjective_compression(self) -> None:
        vectors = {"a": (F(1),), "b": (F(-1),)}
        weights = {"a": F(1, 2), "b": F(1, 2)}
        for inclusion in (
            {frozenset({"a"}): F(1, 2), frozenset({"b"}): F(1, 2)},
            {frozenset(): F(1, 2), frozenset({"a", "b"}): F(1, 2)},
        ):
            mean, var = weighted_moments(vectors, weights, inclusion)
            self.assertEqual(mean, (F(0),))
            self.assertEqual(var, dependent_variance(vectors, weights, inclusion))
        projection = ((F(1), F(0)),)
        kernel = kernel_vector(projection)
        self.assertNotEqual(kernel, (F(0), F(0)))
        with self.assertRaises(ValueError):
            dense_bound_from_projection(projection)

    def test_accounting_retains_failure_cost_and_blocks_exhaustion(self) -> None:
        entropy = EntropyPolicy("synthetic:declared-source", True, True, True, True, True)
        mechanism = MechanismContract(
            "synthetic:finite-law",
            F(1, 2),
            F(0),
            "synthetic:law-assumption",
            "synthetic:entropy-assumption",
            "synthetic-conformance-only",
            entropy,
        )
        policy = LedgerPolicy(
            "synthetic:observer",
            "synthetic-record",
            "a" * 64,
            ("synthetic:client",),
            F(1),
            F(0),
            (mechanism,),
        )
        event = Observation(
            "synthetic:event1",
            "synthetic:output1",
            "failure",
            "accounted-release",
            "b" * 64,
            "synthetic:sum-visible-before-error",
            mechanism.mechanism_id,
            "synthetic:application1",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            ledger = ReferenceAccountant(path, policy, create=True)
            receipt = ledger.authorize(event)
            self.assertEqual(ledger.authorize(event), receipt)
            recovered = ReferenceAccountant(path, policy)
            self.assertEqual(recovered.summary()["epsilon"], "1/2")
            recovered.authorize(
                replace(
                    event,
                    event_id="synthetic:event2",
                    output_id="synthetic:output2",
                    application_id="synthetic:application2",
                )
            )
            with self.assertRaises(ValueError):
                recovered.authorize(
                    replace(
                        event,
                        event_id="synthetic:event3",
                        output_id="synthetic:output3",
                        application_id="synthetic:application3",
                    )
                )
            self.assertEqual(recovered.summary()["epsilon"], "1")
        with self.assertRaises(ValueError):
            replace(entropy, hidden_from_observer=False).require_available()

    def test_binomial_reference_and_correlated_trial_rejection(self) -> None:
        for n in range(1, 8):
            for k in range(n + 2):
                exact = sum(
                    (
                        F(math.comb(n, j)) * F(1, 3) ** j * F(2, 3) ** (n - j)
                        for j in range(k, n + 1)
                    ),
                    F(0),
                )
                self.assertAlmostEqual(binomial_tail(k, n, 1 / 3), float(exact), places=14)
        plan = AuditPlan(
            "synthetic:attack", "coordinator", "replace-client", "client", "fixed", True, True, ()
        )
        trials = [
            Trial("t1", "same-model", "random1", "D", "completed", True),
            Trial("t2", "same-model", "random2", "D-prime", "completed", False),
        ]
        with self.assertRaises(ValueError):
            audit(plan, trials)
        trials[1] = replace(trials[1], model_run_id="other", status="timed-out", event=None)
        report = audit(plan, trials)
        self.assertEqual(report["status"], "inconclusive")
        self.assertIsNone(report["epsilon_lower_bound"])


class BookTests(unittest.TestCase):
    def test_verified_source_examples(self) -> None:
        data = json.loads((ROOT / "tests/vectors/book/manuscript-v1.json").read_text())
        self.assertEqual(data["fixture_version"], "s02-book-1.0.0")
        for v in data["vectors"]:
            self.assertTrue(v["source_nodes"])
            self.assertEqual(v["source_review"], "inspected-native-equations-and-inputs")
            inputs = v["verified_inputs"]
            expected = v["expected"]
            if v["id"] == "audit-ch48-2":
                p = lower_bound(inputs["events_D"], inputs["n_D"], inputs["one_sided_error"])
                q = upper_bound(
                    inputs["events_D_prime"], inputs["n_D_prime"], inputs["one_sided_error"]
                )
                self.assertAlmostEqual(p, expected["p_lower"], delta=v["tolerances"]["probability"])
                self.assertAlmostEqual(q, expected["q_upper"], delta=v["tolerances"]["probability"])
                self.assertAlmostEqual(
                    math.log((p - inputs["delta"]) / q),
                    expected["epsilon_lower"],
                    delta=v["tolerances"]["epsilon"],
                )
            elif v["id"] == "fairness-ch56-4":
                report = private_gap_certificate(
                    tuple(inputs["noisy_denominators"]),
                    inputs["noisy_gap"],
                    epsilon=inputs["epsilon"],
                    alpha=inputs["alpha"],
                    beta=inputs["beta"],
                    fixed_classifier=True,
                    iid_units=True,
                    ideal_laplace_assumption=True,
                )
                self.assertAlmostEqual(
                    report["noise_bound"],
                    expected["noise_bound"],
                    delta=v["tolerances"]["noise_bound"],
                )
                self.assertAlmostEqual(
                    report["upper_bound"],
                    expected["upper_bound"],
                    delta=v["tolerances"]["upper_bound"],
                )
                small = private_gap_certificate(
                    (10, 10),
                    0.04,
                    epsilon=1,
                    alpha=0.04,
                    beta=0.01,
                    fixed_classifier=True,
                    iid_units=True,
                    ideal_laplace_assumption=True,
                )
                self.assertEqual(small["status"], "inconclusive")
            elif v["id"] == "amdahl-ch64-2":
                self.assertEqual(amdahl(F(inputs["f"]), F(inputs["k"])), F(expected["speedup"]))
            elif v["id"] == "batch-ch64-2":
                self.assertEqual(
                    batch(F(inputs["a"]), F(inputs["c"]), inputs["b"], F(inputs["spacing"])),
                    {k: F(v) for k, v in expected.items()},
                )
            elif v["id"] == "training-ch40":
                trace = manuscript_step(tuple(inputs["w"]), tuple(inputs["x"]), inputs["y"])
                self.assertEqual(trace.rounded_prediction_after, 4)
                self.assertEqual(trace.rounded_residual_loss_after, 0)
                self.assertEqual(trace.loss_after, F(1, 2048))
                for name, wanted in expected.items():
                    found = getattr(trace, name)
                    self.assertEqual(
                        found,
                        tuple(wanted)
                        if isinstance(wanted, list)
                        else F(wanted)
                        if isinstance(wanted, str)
                        else wanted,
                    )
            else:
                self.fail("unknown-book-vector")


class PrivateV2Tests(unittest.TestCase):
    def test_source_hash_roundtrip_and_two_round_arithmetic(self) -> None:
        fixture = json.loads(
            (ROOT / "tests/vectors/synthetic/private-transition-v2.json").read_text()
        )
        self.assertEqual(
            hashlib.sha256(fixture["contract_snapshot_json"].encode()).hexdigest(), CONTRACT_SHA256
        )
        previous = None
        for v in fixture["valid"]:
            raw = bytes.fromhex(v["context_hex"])
            context = ContextV2.decode(raw)
            self.assertEqual(context.encode(), raw)
            self.assertEqual(len(raw), 392)
            statement = StatementV2.decode(bytes.fromhex(v["statement_hex"]))
            self.assertEqual(statement.encode().hex(), v["statement_hex"])
            self.assertEqual(len(statement.encode()), 472)
            self.assertEqual(
                private_arithmetic(context, bytes.fromhex(v["numeric_hex"])), v["expected"]
            )
            self.assertEqual(len(bytes.fromhex(v["envelope_layout_hex"])), 652)
            self.assertIn("invalid-placeholder", v["envelope_cryptographic_validity"])
            if previous is not None:
                require_next(previous, context)
            previous = statement
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/generate_s02_private_v2.py"), "--check"],
            check=True,
            capture_output=True,
        )

    def test_context_rejections_and_parent_gate(self) -> None:
        f = json.loads((ROOT / "tests/vectors/synthetic/private-transition-v2.json").read_text())
        for value in f["invalid_context_hex"]:
            with self.assertRaises(ValueError):
                ContextV2.decode(bytes.fromhex(value))
        with self.assertRaises(ValueError):
            replace(private_context(), counts=[1, 2, 1]).encode()  # type: ignore[arg-type]
        previous = StatementV2.decode(bytes.fromhex(f["valid"][0]["statement_hex"]))
        next_context = ContextV2.decode(bytes.fromhex(f["valid"][1]["context_hex"]))
        require_next(previous, replace(next_context, counts=(4, 1, 1)))
        for invalid in [
            replace(next_context, parent=bytes(32)),
            replace(next_context, parent_value=8),
            replace(next_context, round=1),
            replace(next_context, key_id=bytes([6]) * 32),
            replace(next_context, session=bytes([9]) * 16),
        ]:
            with self.assertRaises(ValueError):
                require_next(previous, invalid)
        with self.assertRaises(ValueError):
            private_arithmetic(
                private_context(), numeric.encode(7, [16, -8, 24], [16, -16, 8], [1, 2, 1])
            )
        context = private_context(33)
        self.assertEqual(len(context.encode()), 392)
        wire = bytes.fromhex(f["valid"][0]["numeric_hex"])
        import struct

        with self.assertRaises(ValueError):
            private_arithmetic(context, wire[:16] + struct.pack("<q", 33) + wire[24:])


class RefinementTests(unittest.TestCase):
    def test_precision_recurrence_and_unsafe_optimizer(self) -> None:
        from python.fzkml_math.refinement import quadratic

        gaps = []
        for scale in (1, 2, 4, 8, 16, 32):
            run = quadratic(scale)
            self.assertEqual(run["status"], "completed")
            self.assertTrue(run["valid_contraction_assumption"])
            self.assertGreaterEqual(run["signed_i32_state_margin"], 0)
            for step in run["trace"]:
                self.assertLessEqual(F(step["step_error"]), F(1, 2 * scale))
                self.assertLessEqual(abs(F(step["weight"]) - F(1, 3)), F(step["recurrence_bound"]))
            gaps.append(F(run["objective_gap"]))
        self.assertLess(gaps[-1], gaps[0])
        invalid = quadratic(16, rate=F(3))
        self.assertFalse(invalid["valid_contraction_assumption"])
        self.assertEqual(invalid["status"], "rejected-state-domain")

    def test_certified_and_only_observed_unchanged_classes(self) -> None:
        from python.fzkml_math.refinement import class_status

        strong = class_status((F(1), F(0)), (F(9, 10), F(1, 10)), F(1, 10))
        self.assertTrue(strong["observed_unchanged"])
        self.assertTrue(strong["certified_unchanged"])
        weak = class_status((F(1, 10), F(0)), (F(1, 10), F(0)), F(1, 10))
        self.assertTrue(weak["observed_unchanged"])
        self.assertFalse(weak["certified_unchanged"])
        changed = class_status((F(1, 10), F(0)), (F(0), F(1, 10)), F(1, 10))
        self.assertFalse(changed["observed_unchanged"])
        self.assertFalse(changed["certified_unchanged"])
