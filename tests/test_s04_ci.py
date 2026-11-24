"""CI security/status mutations; fake receipt metadata is never proof execution."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from fzkml_ci.report import render, write_report
from fzkml_ci.research import initialize, profile, reconcile, run, write
from fzkml_ci.s04 import DIGESTS, artifact_tree, journal, proof_receipt, summary, verify_required
from fzkml_ci.validate import ROOT, Invalid, load, validate_bundle, validate_result
from fzkml_ci.workflow import check_repository


def fake_receipt() -> dict[str, Any]:
    # Validator fixture only; production obtains this from a freshly built native extension.
    return {
        "version": 1,
        "backend": "ark-groth16-0.5.0-bn254",
        "proof_mode": "research-real",
        "assurance": "public-arithmetic-only",
        "source_commit": "1" * 40,
        "source_dirty": False,
        "verified": True,
        "proof_bytes": 128,
        "expected_output": 9,
        "oracle_matches": True,
        "negatives": {
            k: True
            for k in [
                "changed-output",
                "changed-public-count",
                "wrong-verifying-key",
                "malformed-proof",
                "trailing-proof-byte",
            ]
        },
        "seconds": {k: 0.1 for k in ["setup", "witness", "prove", "verify"]},
        "workflow_run": None,
        "limitations": ["Synthetic unit metadata, not a proof."],
        **{k: "sha256:" + "1" * 64 for k in DIGESTS},
    }


def script_module(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GenuineBoundaryTests(unittest.TestCase):
    def test_no_false_green_required_aggregate(self) -> None:
        required = {
            "foundation": "success",
            "proof": "success",
            "conformance": "success",
            "registry": "success",
        }
        self.assertTrue(verify_required(required))
        for name in required:
            for outcome in [
                "failure",
                "skipped",
                "cancelled",
                "timed_out",
                "neutral",
                "",
                "pending",
            ]:
                self.assertFalse(verify_required(dict(required, **{name: outcome})))
        required.pop("proof")
        self.assertFalse(verify_required(required))

    def test_mock_mode_skip_or_missing_negative_rejected(self) -> None:
        value = fake_receipt()
        proof_receipt(value, "1" * 40)
        for field, replacement in [
            ("backend", "mock"),
            ("proof_mode", "development"),
            ("assurance", "private-training"),
            ("verified", False),
            ("oracle_matches", False),
            ("source_commit", "2" * 40),
            ("proof_bytes", 0),
            ("expected_output", 10),
        ]:
            bad = copy.deepcopy(value)
            bad[field] = replacement
            with self.assertRaises(Invalid):
                proof_receipt(bad, "1" * 40)
        for name in value["negatives"]:
            bad = copy.deepcopy(value)
            bad["negatives"].pop(name)
            with self.assertRaises(Invalid):
                proof_receipt(bad)
            bad = copy.deepcopy(value)
            bad["negatives"][name] = "skipped"
            with self.assertRaises(Invalid):
                proof_receipt(bad)

    def test_missing_identity_dirty_hosted_or_nonfinite_time_rejected(self) -> None:
        for name in DIGESTS:
            bad = fake_receipt()
            bad[name] = "sha256:" + "0" * 64
            with self.assertRaises(Invalid):
                proof_receipt(bad)
        bad = fake_receipt()
        bad.update(workflow_run=1, source_dirty=True)
        with self.assertRaises(Invalid):
            proof_receipt(bad)
        bad = fake_receipt()
        bad["seconds"]["prove"] = float("nan")
        with self.assertRaises(Invalid):
            proof_receipt(bad)

    def test_negative_adapter_accepts_only_real_false_or_rejection(self) -> None:
        module = script_module("s04_proof")
        self.assertTrue(module.rejected(lambda: False))
        self.assertFalse(module.rejected(lambda: True))
        self.assertFalse(module.rejected(lambda: "false"))
        self.assertFalse(module.rejected(lambda: None))

        def invalid_encoding() -> bool:
            raise ValueError("synthetic-invalid-proof")

        self.assertTrue(module.rejected(invalid_encoding))


class JournalBoundaryTests(unittest.TestCase):
    def test_incomplete_repetition_never_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = initialize("contract", Path(temporary) / "journal.json")
            for status in [
                "not-started",
                "running",
                "skipped",
                "inconclusive",
                "not-run",
                "timed-out",
            ]:
                state["status"] = "completed"
                state["repetitions"][0]["status"] = status
                with self.assertRaises(Invalid):
                    journal(state)

    def test_unavailable_dependency_has_no_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "journal.json"
            initialize("protocol-invariants", path)
            self.assertEqual(run("protocol-invariants", path), 1)
            state = load(path)
            self.assertEqual(state["status"], "unavailable")
            self.assertTrue(all(r["seconds"] is None for r in state["repetitions"]))
            self.assertIn("unavailable", summary(path))

    def test_missing_lost_cancelled_metadata_stays_inconclusive(self) -> None:
        value = reconcile(
            {
                "jobs": [
                    {"id": i, "status": "completed", "conclusion": status}
                    for i, status in enumerate(["skipped", "cancelled", "timed_out", "failure"])
                ]
            },
            None,
        )
        self.assertEqual(value["status"], "inconclusive")
        self.assertEqual(len(value["jobs"]), 4)
        self.assertTrue(all(j["repetitions"] == "unknown-without-journal" for j in value["jobs"]))
        with tempfile.TemporaryDirectory() as temporary:
            self.assertIn("inconclusive", summary(Path(temporary) / "missing.json"))

    def test_unsafe_artifacts_and_secret_fields_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            initialize("contract", directory / "journal.json")
            artifact_tree(directory)
            (directory / "witness.txt").write_text("synthetic-should-not-publish")
            with self.assertRaises(Invalid):
                artifact_tree(directory)
            (directory / "witness.txt").unlink()
            value = load(directory / "journal.json")
            value["raw_environment"] = "FZKML_FORBIDDEN_SECRET_SYNTHETIC"
            write(directory / "journal.json", value)
            with self.assertRaises(Invalid):
                artifact_tree(directory)

    def test_symlink_artifact_or_output_parent_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            initialize("contract", directory / "journal.json")
            (directory / "proof-check.json").symlink_to(directory / "journal.json")
            with self.assertRaises(Invalid):
                artifact_tree(directory)
        with tempfile.TemporaryDirectory(dir=ROOT / ".tools") as temporary:
            directory = Path(temporary)
            (directory / "redirect").symlink_to(directory, target_is_directory=True)
            with self.assertRaises(Invalid):
                write(directory / "redirect" / "journal.json", {"version": 1})

    def test_budget_and_source_drift_rejected(self) -> None:
        for name in ["../../unsafe", "custom-paid-gpu"]:
            with self.assertRaises(Invalid):
                profile(name)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "journal.json"
            state = initialize("contract", path)
            state["source_sha"] = "0" * 40
            write(path, state)
            with self.assertRaises(Invalid):
                run("contract", path)


class WorkflowTierTests(unittest.TestCase):
    def test_exact_workflows_and_unknown_registration(self) -> None:
        check_repository()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "unexpected.yml").write_text(
                (ROOT / ".github/workflows/governance.yml").read_text()
            )
            with self.assertRaises(Invalid):
                check_repository(path)

    def test_privilege_and_source_boundaries(self) -> None:
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            self.assertEqual(workflow["permissions"], {})
            self.assertNotIn("pull_request_target", workflow["on"])
            for job in workflow["jobs"].values():
                self.assertEqual(job["runs-on"], "ubuntu-24.04")
                self.assertLessEqual(int(job["timeout-minutes"]), 30)
                if "pull_request" in workflow["on"] and path.name != "codeql.yml":
                    self.assertEqual(job["permissions"], {"contents": "read"})
                    self.assertNotIn("environment", job)
                for step in job["steps"]:
                    if "run" in step:
                        self.assertNotIn("${{", step["run"])
                    if "uses" in step:
                        self.assertRegex(step["uses"], r"@[a-f0-9]{40}$")

    def test_expensive_jobs_only_main_or_disabled(self) -> None:
        main = yaml.load(
            (ROOT / ".github/workflows/language.yml").read_text(), Loader=yaml.BaseLoader
        )
        self.assertNotIn("pull_request", main["on"])
        self.assertIn("refs/heads/main", main["jobs"]["integration"]["if"])
        gpu = yaml.load((ROOT / ".github/workflows/gpu.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(set(gpu["on"]), {"workflow_dispatch"})
        self.assertEqual(gpu["jobs"]["disabled"]["environment"], "gpu-research")
        self.assertIn("exit 1", gpu["jobs"]["disabled"]["steps"][0]["run"])

    def test_nightly_weekly_and_safe_upload_separation(self) -> None:
        workflow = yaml.load(
            (ROOT / ".github/workflows/research.yml").read_text(), Loader=yaml.BaseLoader
        )
        self.assertEqual(len(workflow["on"]["schedule"]), 2)
        self.assertEqual(set(workflow["jobs"]), {"nightly", "weekly"})
        for job in workflow["jobs"].values():
            self.assertIn("refs/heads/main", job["if"])
            self.assertIn("FZKML/fzkml", job["if"])
            upload = job["steps"][-1]
            self.assertEqual(upload["if"], "always() && steps.public.outcome == 'success'")
            self.assertEqual(job["steps"][-2]["run"], "./scripts/research verify-artifacts")


class PublicationTests(unittest.TestCase):
    def test_local_v11_compatibility_and_pending_publication(self) -> None:
        row = copy.deepcopy(load(ROOT / "examples/results.json")["results"][0])
        row["schema_version"] = "1.1.0"
        row["provenance"].update(execution_kind="local", workflow_path=None, workflow_run=None)
        row["publication_review"]["approved"] = False
        validate_result(row)
        bundle = {"schema_version": "1.1.0", "results": [row]}
        claims = load(ROOT / "claims/registry.json")
        validate_bundle(bundle, claims)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "public"
            with self.assertRaisesRegex(Invalid, "publication-review-pending"):
                write_report(bundle, claims, destination)
            self.assertFalse(destination.exists())
        for mutation in ["fake-hosted-id", "missing-hosted-id", "unknown-version", "old-version"]:
            bad = copy.deepcopy(row)
            if mutation == "fake-hosted-id":
                bad["provenance"]["workflow_run"] = 1
            elif mutation == "missing-hosted-id":
                bad["provenance"]["execution_kind"] = "github-actions"
            else:
                bad["schema_version"] = "2.0.0" if mutation == "unknown-version" else "1.0.0"
            with self.assertRaises(Invalid):
                validate_result(bad)
        row["publication_review"]["approved"] = True  # Explicit synthetic publication fixture only.
        result = render(bundle, claims)
        self.assertIn("Execution: local; no workflow run.", result["report.md"])
        self.assertEqual(json.loads(result["summary.json"])["schema_version"], "1.1.0")

    def test_v11_schema_bytes_match_session03_review(self) -> None:
        expected = {
            "result": "582bc7a993f3dd5baf612cb90ef0b7ea56480700d9413eb7fa2252ffbbea6f5e",
            "bundle": "4ba965923f13c02781671567f359eaa1207255773ea1aa3c027827cfc1393e54",
        }
        for name, digest in expected.items():
            self.assertEqual(
                hashlib.sha256((ROOT / f"schemas/{name}-1.1.0.json").read_bytes()).hexdigest(),
                digest,
            )

    def test_local_never_invents_workflow_identity(self) -> None:
        report = script_module("s04_report")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(Invalid):
                report.bundle()

    def test_failed_preparation_and_unavailable_are_not_passes(self) -> None:
        report = script_module("s04_report")
        base = load(ROOT / "examples/results.json")
        with tempfile.TemporaryDirectory() as temporary:
            state = initialize("protocol-invariants", Path(temporary) / "journal.json")
            state["status"] = "unavailable"
            state["repetitions"][0]["status"] = "not-run"
            actual_load = report.load

            def injected(path: Path) -> Any:
                return state if path.name == "journal.json" else actual_load(path)

            with (
                patch.dict("os.environ", {"GITHUB_RUN_ID": "1"}),
                patch.object(report, "load", side_effect=injected),
            ):
                unavailable = report.bundle()
                self.assertEqual(unavailable["results"][0]["outcome"]["status"], "not-run")
                state["status"] = "failed"
                state["repetitions"][0].update(status="timed-out", seconds=12.0)
                failed = report.bundle()
                self.assertEqual(failed["results"][0]["outcome"]["status"], "failed")
                self.assertTrue(failed["results"][0]["repetitions"][0]["timeout"])
                validate_bundle(failed, load(ROOT / "claims/registry.json"))
        self.assertEqual(base["schema_version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
