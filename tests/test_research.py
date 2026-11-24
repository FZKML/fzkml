"""Synthetic control fixtures only: these tests never establish a real proof."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fzkml_ci.benchmark import compare
from fzkml_ci.inventory import generate
from fzkml_ci.release import FILES, inventory, verify
from fzkml_ci.research import (
    execute,
    initialize,
    profile,
    proof_command,
    proof_results,
    reconcile,
    run,
)
from fzkml_ci.validate import ROOT, Invalid, load
from fzkml_ci.workflow import check_research_workflow


def proof_fixture() -> dict[str, Any]:
    # Made-up successful records exercise validators; no cryptographic execution.
    value: dict[str, Any] = load(ROOT / "examples" / "results.json")
    value["results"] = value["results"][:3]
    for row in value["results"]:
        row["outcome"] = {"status": "successful", "reason": "Synthetic unit fixture only."}
        row["scenario"]["security_mode"] = "research"
        row["scenario"]["backend"] = "test-fixture"
        for field in ["program_digest", "circuit_digest", "parameters_digest", "key_digest"]:
            row["scenario"][field] = "sha256:" + "1" * 64
        row["provenance"].update(
            source_commit="1" * 40, workflow_run=1, dependency_digest="sha256:" + "1" * 64
        )
        row["repetitions"] = [
            {
                "id": "fixture",
                "attempt": 1,
                "status": "successful",
                "timeout": False,
                "excluded": False,
                "reason": "unit fixture",
                "measurements": [],
                "quality": "pass",
            }
        ]
    return value


class ProofGateTests(unittest.TestCase):
    def test_placeholder_and_missing_adapter_fail(self) -> None:
        with self.assertRaises(Invalid):
            proof_command()
        with self.assertRaises(Invalid):
            proof_results(load(ROOT / "examples" / "results.json"))

    def test_mandatory_cases_and_mode(self) -> None:
        value = proof_fixture()
        proof_results(value)
        for mode in ["synthetic-test", "production-declared"]:
            bad = copy.deepcopy(value)
            bad["results"][0]["scenario"]["security_mode"] = mode
            with self.assertRaises(Invalid):
                proof_results(bad)
        value["results"].pop()
        with self.assertRaises(Invalid):
            proof_results(value)

    def test_skips_timeouts_mock_and_zero_identity_fail(self) -> None:
        for field, value in [("excluded", True), ("timeout", True), ("status", "failed")]:
            bad = proof_fixture()
            bad["results"][0]["repetitions"][0][field] = value
            with self.assertRaises(Invalid):
                proof_results(bad)
        for field, value in [("backend", "mock"), ("program_digest", "sha256:" + "0" * 64)]:
            bad = proof_fixture()
            bad["results"][0]["scenario"][field] = value
            with self.assertRaises(Invalid):
                proof_results(bad)


class JournalTests(unittest.TestCase):
    def test_initial_manifest_and_unavailable_repetitions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "journal.json"
            initial = initialize("tiny-reference", path)
            self.assertEqual([r["status"] for r in initial["repetitions"]], ["not-started"] * 3)
            self.assertEqual(run("tiny-reference", path), 1)
            self.assertEqual([r["status"] for r in load(path)["repetitions"]], ["not-run"] * 3)

    def test_failure_retained_with_bounded_reproducer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "journal.json"
            initialize("contract", path)
            with patch(
                "fzkml_ci.research.execute",
                side_effect=[("completed", 1.0), ("failed", 2.0), ("timed-out", 3.0)],
            ):
                self.assertEqual(run("contract", path), 1)
            final = load(path)
            self.assertEqual(
                [r["status"] for r in final["repetitions"]], ["completed", "failed", "timed-out"]
            )
            self.assertLess((path.parent / "reproducer.json").stat().st_size, 1000)

    def test_partial_journal_survives_interrupted_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "journal.json"
            initialize("contract", path)
            with patch(
                "fzkml_ci.research.execute", side_effect=[("completed", 1.0), KeyboardInterrupt]
            ):
                with self.assertRaises(KeyboardInterrupt):
                    run("contract", path)
            self.assertEqual(
                [r["status"] for r in load(path)["repetitions"]],
                ["completed", "running", "not-started"],
            )

    def test_timeout_and_failure_are_real_process_results(self) -> None:
        self.assertEqual(execute([sys.executable, "-c", "raise SystemExit(1)"], 1, 1)[0], "failed")
        self.assertEqual(
            execute([sys.executable, "-c", "import time; time.sleep(5)"], 0.05, 1)[0], "timed-out"
        )

    def test_reconciliation_never_infers_repetitions(self) -> None:
        jobs = {
            "jobs": [
                {"id": i, "status": "completed", "conclusion": c}
                for i, c in enumerate(["success", "cancelled", "timed_out", "failure"])
            ]
        }
        value = reconcile(jobs, None)
        self.assertEqual(value["status"], "inconclusive")
        self.assertEqual(len(value["jobs"]), 4)
        self.assertTrue(all(j["repetitions"] == "unknown-without-journal" for j in value["jobs"]))

    def test_allowlist_and_budget(self) -> None:
        with self.assertRaises(Invalid):
            profile("../../arbitrary")
        with patch(
            "fzkml_ci.research.load", return_value=dict(profile("contract"), repetitions=500)
        ):
            with self.assertRaises(Invalid):
                profile("contract")


class ReleaseTests(unittest.TestCase):
    def bundle(self, directory: Path) -> None:
        for name in FILES:
            (directory / name).write_bytes(b"synthetic artifact")
        (directory / "results.json").write_text(json.dumps(proof_fixture()))
        manifest = inventory(directory, "1" * 40, "v0.0.0")
        (directory / "manifest.json").write_text(json.dumps(manifest))

    def test_binary_and_manifest_tampering_detected(self) -> None:
        for filename in ["libfzkml_core.rlib", "manifest.json"]:
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                self.bundle(directory)
                verify(directory, "1" * 40, "v0.0.0", attest=False)
                if filename == "manifest.json":
                    value = load(directory / filename)
                    value["commit"] = "2" * 40
                    (directory / filename).write_text(json.dumps(value))
                else:
                    (directory / filename).write_bytes(b"tampered")
                with self.assertRaises(Invalid):
                    verify(directory, "1" * 40, "v0.0.0", attest=False)

    def test_identity_constrained_verification_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.bundle(directory)
            with patch("fzkml_ci.release.subprocess.run") as verifier:
                verify(directory, "1" * 40, "v0.0.0")
                self.assertEqual(verifier.call_count, 2)
                command = verifier.call_args.args[0]
                for option in [
                    "--repo",
                    "--signer-workflow",
                    "--source-digest",
                    "--source-ref",
                    "--deny-self-hosted-runners",
                ]:
                    self.assertIn(option, command)
            with patch(
                "fzkml_ci.release.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "gh"),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    verify(directory, "1" * 40, "v0.0.0")

    def test_extra_files_and_symlinks_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.bundle(directory)
            (directory / "unexpected").write_text("extra")
            with self.assertRaises(Invalid):
                verify(directory, "1" * 40, "v0.0.0", attest=False)
            (directory / "unexpected").unlink()
            (directory / "libfzkml_core.rlib").unlink()
            (directory / "libfzkml_core.rlib").symlink_to(directory / "source.tar.gz")
            with self.assertRaises(Invalid):
                verify(directory, "1" * 40, "v0.0.0", attest=False)


class BenchmarkTests(unittest.TestCase):
    def fixture(self) -> dict[str, Any]:
        row: dict[str, Any] = proof_fixture()["results"][0]
        row["benchmark"] = {
            "workload_digest": "sha256:" + "1" * 64,
            "warmups": 0,
            "setup_amortization": "none",
            "cached_work": "none",
            "quality_threshold": "unit fixture only",
            "phases": {
                p: "unavailable"
                for p in ["setup", "witness", "prove", "aggregate", "verify", "transfer", "total"]
            },
            "resources": {
                p: "unavailable: unit fixture"
                for p in ["peak_memory", "proof_bytes", "communication"]
            },
        }
        row["benchmark"]["phases"]["total"] = "measured"
        row["repetitions"] *= 2
        row["repetitions"] = [copy.deepcopy(r) for r in row["repetitions"]]
        for i, rep in enumerate(row["repetitions"]):
            rep["id"] = str(i)
            rep["measurements"] = [
                {"phase": "total", "quantity": "time", "unit": "s", "value": i + 1}
            ]
        return row

    def test_comparison_stays_diagnostic_with_raw_variance(self) -> None:
        row = self.fixture()
        value = compare(row, row)
        self.assertEqual(value["status"], "diagnostic")
        self.assertEqual(value["distributions"][0]["variance_seconds2"], 0.5)

    def test_unmatched_work_and_hidden_setup_rejected(self) -> None:
        row = self.fixture()
        mutations: list[Callable[[dict[str, Any]], None]] = [
            lambda r: r["scenario"].update(numerical_semantics="different"),
            lambda r: r["provenance"]["hardware"].update(cpu="different"),
            lambda r: r["benchmark"].update(cached_work="precomputed"),
            lambda r: r["benchmark"]["phases"].update(setup="measured"),
        ]
        for mutation in mutations:
            bad = copy.deepcopy(row)
            mutation(bad)
            with self.assertRaises(Invalid):
                compare(row, bad)


class PolicyTests(unittest.TestCase):
    def test_workflow_mutations_need_review(self) -> None:
        for name in [
            "research.yml",
            "research-reconcile.yml",
            "gpu.yml",
            "release.yml",
            "codeql.yml",
            "cpu.yml",
        ]:
            data = (ROOT / ".github" / "workflows" / name).read_bytes()
            check_research_workflow(name, data)
            with self.assertRaises(Invalid):
                check_research_workflow(name, data.replace(b"ubuntu-24.04", b"self-hosted"))

    def test_inventory_includes_transitive_and_tooling(self) -> None:
        document = generate()
        packages = {p["name"] for p in document["sbom"]["packages"]}
        self.assertTrue({"rpds-py", "attrs", "uv", "fzkml-core"} <= packages)
        self.assertEqual(document, generate())


if __name__ == "__main__":
    unittest.main()
