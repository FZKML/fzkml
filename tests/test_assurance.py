"""Actual native disagreement/proof tests and fail-closed evidence boundaries."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from fractions import Fraction as Q
from typing import Any

import yaml

from fzkml_assurance import authenticity as au
from fzkml_assurance import benchmark as bm
from fzkml_assurance import golden as gv
from fzkml_assurance import reporting as rp
from fzkml_assurance.common import BASE, check_schema, file_sha
from fzkml_ci.validate import ROOT, load


class GoldenTests(unittest.TestCase):
    def test_deterministic_generation_and_actual_cross_language_domain(self) -> None:
        value = gv.generate()
        self.assertEqual(gv.encoded(value), (ROOT / gv.FIXTURE).read_bytes())
        self.assertEqual((ROOT / gv.SIDECAR).read_text().strip(), file_sha(gv.FIXTURE))
        self.assertEqual(
            gv.cross_check(value),
            {
                "rounding": 1040,
                "signed": 7,
                "batches": 36,
                "invalid_i64": 5,
                "invalid_batches": 6,
            },
        )
        self.assertEqual(value["batch_vectors"][3]["expected"]["output"], 34)
        self.assertEqual(value["input_domain"]["w_max"], 32)

    def test_actual_native_zero_exit_disagrees_with_each_mutated_oracle(self) -> None:
        for name in ["rounding-tie", "negative-division", "byte-order"]:
            with self.subTest(name=name), self.assertRaises(gv.ConformanceFailure) as caught:
                gv.cross_check(gv.mutate(gv.generate(), name))
            self.assertEqual(caught.exception.detail["native_exit_code"], 0)
            self.assertNotEqual(
                caught.exception.detail["expected_digest"],
                caught.exception.detail["observed_digest"],
            )

    def test_euclidean_floor_remainder_cannot_be_replaced_by_truncation(self) -> None:
        bad = gv.generate()
        row = next(r for r in bad["rounding_vectors"] if r["n"] == -3 and r["d"] == 2)
        row["floor"], row["remainder"] = -1, -1
        with self.assertRaises(ValueError):
            gv.cross_check(bad)

    def test_nan_and_unknown_fields_rejected(self) -> None:
        for value in [dict(gv.generate(), unexpected=True), {"result": float("nan")}]:
            with self.assertRaises(ValueError):
                check_schema(value, "golden")


class AuthenticityTests(unittest.TestCase):
    actual: Any

    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [str(ROOT / "target/release/fzkml-assurance"), "auth", "positive"],
            capture_output=True,
            timeout=120,
            check=True,
        )
        cls.actual = json.loads(result.stdout)

    def test_actual_native_verifier_accepts_only_positive(self) -> None:
        au.validate_native(self.actual)
        self.assertEqual(self.actual["actual_proof_bytes"], 128)
        self.assertEqual([r["case"] for r in self.actual["cases"] if r["accepted"]], ["positive"])
        self.assertTrue(all(r["nominal_exit_code"] == 0 for r in self.actual["cases"]))
        for name in ["forged-key-tag", "fake-proof", "changed-output", "trailing-byte"]:
            row = next(r for r in self.actual["cases"] if r["case"] == name)
            self.assertTrue(row["native_verifier_called"])
            self.assertFalse(row["accepted"])

    def test_development_and_substituted_key_candidates_fail_despite_actual_zero_exit(self) -> None:
        for name in ["development", "substituted-key"]:
            result = subprocess.run(
                [str(ROOT / "target/release/fzkml-assurance"), "auth", name],
                capture_output=True,
                timeout=120,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            actual = json.loads(result.stdout)
            au.validate_native(actual, require_candidate=False)
            self.assertFalse(actual["candidate_accepted"])
            with self.assertRaises(ValueError):
                au.validate_native(actual)

    def test_missing_negative_mock_backend_key_and_canceled_verdict_rejected(self) -> None:
        mutations = []
        bad = copy.deepcopy(self.actual)
        bad["cases"].pop()
        mutations.append(bad)
        bad = copy.deepcopy(self.actual)
        bad["cases"][0]["mode"] = "development"
        mutations.append(bad)
        for key, value in [
            ("backend", "mock"),
            ("controller_key_digest", "0" * 64),
            ("program_digest", "f" * 64),
        ]:
            mutations.append(dict(self.actual, **{key: value}))
        bad = copy.deepcopy(self.actual)
        bad["cases"][-1]["accepted"] = True
        mutations.append(bad)
        for bad in mutations:
            with self.assertRaises(ValueError):
                au.validate_native(bad)


class ReviewAndReportingTests(unittest.TestCase):
    def test_packet_exact_scope_and_unauthorized_distribution(self) -> None:
        packet = rp.review_packet()
        rp.validate_review(packet)
        self.assertEqual(packet["appointment_status"], "not-appointed")
        self.assertEqual(packet["distribution"], "not-authorized")
        self.assertEqual(packet["findings"], [])
        with self.assertRaises(ValueError):
            rp.validate_review(packet, require_reviewed=True)

    def test_scope_artifact_reviewer_or_distribution_drift_fails(self) -> None:
        for key, value in [
            ("protocol_subject_commit", "0" * 40),
            ("distribution", "authorized"),
            ("reviewer", "invented reviewer"),
        ]:
            bad = dict(rp.review_packet(), **{key: value})
            with self.assertRaises(ValueError):
                rp.validate_review(bad)
        bad = rp.review_packet()
        bad["scope"]["included"].pop()
        with self.assertRaises(ValueError):
            rp.validate_review(bad)
        bad = rp.review_packet()
        bad["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            rp.validate_review(bad)

    def test_fixed_finding_needs_actual_regression_at_scoped_commit(self) -> None:
        packet = rp.review_packet()
        packet["findings"] = [
            {
                "id": "synthetic-internal-validation",
                "severity": "high",
                "disposition": "fixed",
                "scope_commit": BASE,
                "regressions": [],
            }
        ]
        with self.assertRaises(ValueError):
            rp.validate_review(packet)
        packet["findings"][0]["regressions"] = ["tests/test_pipeline.py::test_invented"]
        with self.assertRaises(ValueError):
            rp.validate_review(packet)

    def test_all_book_items_and_authoritative_claims_preserved(self) -> None:
        value = rp.evidence_index()
        rp.validate_index(value)
        self.assertEqual(len(value["claims"]), 23)
        self.assertEqual(len(value["coverage"]), 128)
        self.assertFalse(value["publication_review"]["approved"])
        self.assertTrue(all(not c["independent_review_ids"] for c in value["claims"]))
        self.assertIn("Fictional", value["reporting_fixture_classification"])

    def test_omissions_promotions_and_removed_counterevidence_fail(self) -> None:
        for key in [
            "coverage",
            "claims",
            "reporting_fixture_cases",
            "replication_cards",
            "corrections",
        ]:
            bad = rp.evidence_index()
            bad[key].pop()
            with self.subTest(key=key), self.assertRaises(ValueError):
                rp.validate_index(bad)
        bad = rp.evidence_index()
        bad["claims"][0]["status"] = "reviewed"
        with self.assertRaises(ValueError):
            rp.validate_index(bad)

    def test_counterevidence_classification_never_becomes_supported(self) -> None:
        for claim_status, expected in [
            ("refuted", "contradicted"),
            ("inconclusive", "inconclusive"),
        ]:
            self.assertEqual(rp.coverage_status([{"status": claim_status}], {}), expected)


class BenchmarkTests(unittest.TestCase):
    def test_disjoint_holdout_encoded_prediction_quality_and_target(self) -> None:
        plan = load(ROOT / "ci/assurance/benchmark-plan-v1.json")
        bm.validate_plan(plan)
        self.assertEqual(Q(bm.quality(8) or "0"), Q(9, 64))
        self.assertEqual(Q(bm.quality(9) or "0"), Q(25, 256))
        self.assertNotEqual(Q(bm.quality(9) or "0"), Q(441, 4096))
        self.assertLess(Q(bm.quality(9) or "1"), Q(plan["quality_threshold"]))
        plan["holdout"]["x"], plan["holdout"]["y"] = [-16, 16], [-16, 16]
        with self.assertRaises(ValueError):
            bm.validate_plan(plan)

    def test_real_process_clients_retain_timeout_and_cannot_certify_reduced_cohort(self) -> None:
        normal, failed = bm.federated(False), bm.federated(True)
        self.assertEqual((normal["selected"], normal["accepted"], normal["output"]), (3, 3, 9))
        self.assertEqual((failed["selected"], failed["accepted"], failed["output"]), (3, 2, None))
        self.assertIsNone(failed["certified_time_to_quality_seconds"])
        self.assertEqual(len(failed["excluded_sources"]), 1)
        self.assertEqual(len(failed["clients"]), 3)
        self.assertEqual(failed["clients"][2]["status"], "timeout")
        for client in normal["clients"]:
            self.assertGreater(client["cpu_seconds"], 0)
            self.assertGreater(client["peak_process_rss_bytes"], 0)

    def test_actual_failed_child_and_repetition_budget(self) -> None:
        failed = bm.sample([sys.executable, "-c", "raise SystemExit(7)"])
        self.assertEqual((failed["status"], failed["exit_code"]), ("failed", 7))
        for repetitions in [0, 3, True]:
            with self.assertRaises(ValueError):
                bm.run(repetitions)

    def test_mandatory_ci_and_manual_cpu_only_benchmark(self) -> None:
        cpu = yaml.load((ROOT / ".github/workflows/cpu.yml").read_text(), Loader=yaml.BaseLoader)
        for job, command in [
            ("proof", "./scripts/assurance proof"),
            ("conformance", "./scripts/assurance golden"),
        ]:
            steps = cpu["jobs"][job]["steps"]
            step = next(s for s in steps if s.get("run") == command)
            self.assertNotIn("continue-on-error", step)
            self.assertNotIn("if", step)
        workflow = yaml.load(
            (ROOT / ".github/workflows/language.yml").read_text(), Loader=yaml.BaseLoader
        )
        job = workflow["jobs"]["benchmark"]
        self.assertIn("workflow_dispatch", job["if"])
        self.assertIn("refs/heads/main", job["if"])
        self.assertEqual(job["runs-on"], "ubuntu-24.04")
        self.assertEqual(job["permissions"], {"contents": "read"})
        self.assertTrue(all("upload-artifact" not in s.get("uses", "") for s in job["steps"]))
