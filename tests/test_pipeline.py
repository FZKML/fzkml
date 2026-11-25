from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

from fzkml_ci.report import render, verify_report, write_report
from fzkml_ci.validate import (
    MAX_FILE,
    ROOT,
    Invalid,
    load,
    public_tree,
    validate_bundle,
    validate_claims,
    validate_result,
)
from fzkml_ci.workflow import ACTIONS, check_repository, check_workflow


def example() -> dict[str, Any]:
    return load(ROOT / "examples/results.json")  # type: ignore[no-any-return]


def registry() -> dict[str, Any]:
    return {"schema_version": "1.0.0", "claims": [], "evidence": []}


def measured() -> dict[str, Any]:
    r: dict[str, Any] = example()["results"][0]
    r["outcome"] = {"status": "successful", "reason": "Synthetic validator fixture."}
    r["provenance"]["source_commit"] = "1" * 40
    r["provenance"]["workflow_run"] = 1
    r["provenance"]["dependency_digest"] = "sha256:" + "1" * 64
    r["repetitions"] = [
        {
            "id": "rep1",
            "attempt": 1,
            "status": "successful",
            "timeout": False,
            "excluded": False,
            "reason": "Synthetic repetition.",
            "quality": "pass",
            "measurements": [{"phase": "prove", "quantity": "time", "unit": "s", "value": 2}],
        },
        {
            "id": "rep2",
            "attempt": 1,
            "status": "successful",
            "timeout": False,
            "excluded": False,
            "reason": "Synthetic repetition.",
            "quality": "pass",
            "measurements": [{"phase": "prove", "quantity": "time", "unit": "s", "value": 4}],
        },
    ]
    r["metrics"] = [
        {
            "phase": "prove",
            "quantity": "time",
            "unit": "s",
            "value": 3,
            "aggregation": "mean",
            "repetition_ids": ["rep1", "rep2"],
        }
    ]
    return r


def claim() -> dict[str, Any]:
    return {
        "id": "FZK-V01-C01-TEST-001",
        "source": {
            "edition": "V01",
            "chapter": 1,
            "section": "synthetic",
            "equation": "none",
            "version": "fixture",
        },
        "kind": "assumption-theorem",
        "observer": "not-applicable",
        "privacy_unit": "not-applicable",
        "numerical_semantics": "synthetic-fixture",
        "statement": "Synthetic claim for validation only.",
        "evidence_class": "specification",
        "scope": "Fixture only.",
        "assumptions": [],
        "owner": "synthetic-owner",
        "responsible_issue": 16,
        "status": "planned",
        "evidence_ids": [],
        "formal_proof": {"artifact_ids": [], "assumptions": [], "scope": "None."},
        "independent_review": {"artifact_ids": [], "scope": "None."},
        "limitations": ["Not extracted from manuscript."],
    }


class ResultTests(unittest.TestCase):
    def test_local_pending_record_and_publication_gate(self) -> None:
        r = measured()
        r["schema_version"] = "1.1.0"
        r["provenance"].update(execution_kind="local", workflow_path=None, workflow_run=None)
        r["publication_review"]["approved"] = False
        r["repetitions"][0]["measurements"][0]["phase"] = "aggregate"
        r["repetitions"][1]["measurements"][0]["phase"] = "aggregate"
        r["metrics"][0]["phase"] = "aggregate"
        validate_result(r)
        bundle = {"schema_version": "1.1.0", "results": [r]}
        validate_bundle(bundle, registry())
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "out"
            with self.assertRaisesRegex(Invalid, "publication-review-pending"):
                write_report(bundle, registry(), destination)
            self.assertFalse(destination.exists())
        for mutation in ("fake-run", "missing-run", "unknown-phase", "old-version"):
            changed = copy.deepcopy(r)
            if mutation == "fake-run":
                changed["provenance"]["workflow_run"] = 1
            elif mutation == "missing-run":
                changed["provenance"]["execution_kind"] = "github-actions"
            elif mutation == "unknown-phase":
                changed["repetitions"][0]["measurements"][0]["phase"] = "anything"
            else:
                changed["schema_version"] = "1.0.0"
            with self.subTest(mutation=mutation), self.assertRaises(Invalid):
                validate_result(changed)
        r["publication_review"]["approved"] = True
        self.assertIn("Execution: local; no workflow run.", render(bundle, registry())["report.md"])

    def test_language_workflow_registration(self) -> None:
        result = measured()
        result["provenance"]["workflow_path"] = ".github/workflows/language.yml"
        validate_result(result)
        result["provenance"]["workflow_path"] = ".github/workflows/unreviewed.yml"
        with self.assertRaises(Invalid):
            validate_result(result)

    def test_all_outcomes_remain_distinct(self) -> None:
        for status in ["successful", "failed", "inconclusive", "unsupported", "not-run"]:
            with self.subTest(status=status):
                r = measured()
                r["outcome"]["status"] = status
                if status in {"not-run", "unsupported"}:
                    r["metrics"], r["repetitions"] = [], []
                elif status == "failed":
                    for rep in r["repetitions"]:
                        rep["status"], rep["timeout"] = "failed", True
                validate_result(r)

    def test_required_version_units_and_status(self) -> None:
        for mutation in [
            "missing",
            "version",
            "unit",
            "unit-pair",
            "status",
            "raw",
            "aggregate",
            "excluded",
            "timeout",
            "quality",
            "duplicate",
            "nonfinite",
            "provenance",
        ]:
            with self.subTest(mutation=mutation):
                r = measured()
                if mutation == "missing":
                    del r["provenance"]
                if mutation == "version":
                    r["schema_version"] = "99"
                if mutation == "unit":
                    r["metrics"][0]["unit"] = "ms"
                if mutation == "unit-pair":
                    r["repetitions"][0]["measurements"][0]["unit"] = "byte"
                if mutation == "status":
                    r["outcome"]["status"] = "not-run"
                if mutation == "raw":
                    r["metrics"][0]["repetition_ids"] = ["missing"]
                if mutation == "aggregate":
                    r["metrics"][0]["value"] = 99
                if mutation == "excluded":
                    r["repetitions"][0]["excluded"] = True
                if mutation == "timeout":
                    r["repetitions"][0]["timeout"] = True
                if mutation == "quality":
                    r["repetitions"][0]["quality"] = "fail"
                if mutation == "duplicate":
                    r["repetitions"].append(r["repetitions"][0])
                if mutation == "nonfinite":
                    r["metrics"][0]["value"] = float("nan")
                if mutation == "provenance":
                    r["provenance"]["source_commit"] = "0" * 40
                with self.assertRaises(Invalid):
                    validate_result(r)

    def test_forbidden_fields_and_licenses(self) -> None:
        for field in [
            "witness",
            "training_records",
            "secret_share",
            "private_seed",
            "participant_id",
        ]:
            r = measured()
            r[field] = "synthetic forbidden field"
            with self.assertRaises(Invalid):
                validate_result(r)
        for field in ["license", "publication"]:
            r = measured()
            del r["scenario"]["dataset"][field]
            with self.assertRaises(Invalid):
                validate_result(r)
        r = measured()
        r["scenario"]["dataset"]["id"] = "participant-alice"
        with self.assertRaises(Invalid):
            validate_result(r)

    def test_secret_patterns_and_safe_diagnostic(self) -> None:
        for marker in [
            "FZKML_FORBIDDEN_SECRET",
            "ghp_" + "x" * 30,
            "AKIA" + "A" * 16,
            "api_key=synthetic-private-value",
        ]:
            r = measured()
            r["limitations"] = [marker]
            with self.assertRaises(Invalid) as caught:
                validate_result(r)
            self.assertNotIn(marker, str(caught.exception))

    def test_duplicate_keys_deep_data_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for data in [b'{"a":1,"a":2}', b"x" * (MAX_FILE + 1), b"[" * 2000]:
                path.write_bytes(data)
                with self.assertRaises(Invalid):
                    load(path)
        deep: Any = []
        for _ in range(30):
            deep = [deep]
        with self.assertRaises(Invalid):
            public_tree(deep)


class ClaimTests(unittest.TestCase):
    def test_empty_and_deferred_are_visible(self) -> None:
        data = registry()
        c = claim()
        c["status"] = "deferred"
        data["claims"] = [c]
        coverage = validate_claims(data)
        self.assertEqual(coverage["unmapped"], [c["id"]])
        self.assertEqual(coverage["by_status"]["deferred"], [c["id"]])
        self.assertEqual(c["status"], "deferred")

    def test_dangling_result_claim_and_evidence(self) -> None:
        data = registry()
        c = claim()
        data["claims"] = [c]
        c["evidence_ids"] = ["absent"]
        with self.assertRaises(Invalid):
            validate_claims(data)
        bundle = example()
        bundle["results"][0]["claim_ids"] = [c["id"]]
        with self.assertRaises(Invalid):
            validate_bundle(bundle, registry())

    def test_test_reference_and_formal_boundary(self) -> None:
        data = registry()
        c = claim()
        c["evidence_ids"] = ["test"]
        data["claims"] = [c]
        data["evidence"] = [
            {
                "id": "test",
                "kind": "unit-test",
                "path": "tests/test_pipeline.py::test_test_reference_and_formal_boundary",
                "scope": "Fixture checks only.",
            }
        ]
        validate_claims(data)
        self.assertEqual(c["status"], "planned")
        c["formal_proof"]["artifact_ids"] = ["test"]
        with self.assertRaises(Invalid):
            validate_claims(data)
        c["formal_proof"]["artifact_ids"] = []
        c["status"] = "formally-proved"
        with self.assertRaises(Invalid):
            validate_claims(data)
        c["status"] = "planned"
        data["evidence"][0]["path"] = "tests/test_pipeline.py::test_absent"
        with self.assertRaises(Invalid):
            validate_claims(data)

    def test_source_and_path_validation(self) -> None:
        data = registry()
        data["claims"] = [claim()]
        data["claims"][0]["source"]["chapter"] = 2
        with self.assertRaises(Invalid):
            validate_claims(data)
        data["claims"] = []
        data["evidence"] = [
            {
                "id": "x",
                "kind": "specification",
                "path": "../outside",
                "scope": "Synthetic fixture.",
            }
        ]
        with self.assertRaises(Invalid):
            validate_claims(data)


class ReportTests(unittest.TestCase):
    def test_deterministic_outputs_and_visible_limits(self) -> None:
        first = render(example(), registry())
        self.assertEqual(first, render(example(), registry()))
        self.assertIn("not-run", first["report.md"])
        self.assertIn("pending R001", first["report.md"])
        self.assertIn("raw repetitions", first["report.md"])

    def test_escape_html_markdown_and_separate_groups(self) -> None:
        bundle: dict[str, Any] = {"schema_version": "1.0.0", "results": [measured()]}
        bundle["results"][0]["limitations"] = [
            "<script>alert(1)</script> ![x](https://example.org)"
        ]
        other = copy.deepcopy(bundle["results"][0])
        other["run_id"] = "synthetic:second"
        other["scenario"]["security_mode"] = "research"
        bundle["results"].append(other)
        rendered = render(bundle, registry())
        self.assertNotIn("<script>", rendered["report.html"])
        self.assertNotIn("![x]", rendered["report.md"])
        groups = [r["comparison_group"] for r in json.loads(rendered["summary.json"])["runs"]]
        self.assertNotEqual(*groups)
        self.assertIn("prove time mean", rendered["plots.svg"])
        self.assertIn("<circle", rendered["plots.svg"])

    def test_reject_tampering_extra_files_links_and_oversize(self) -> None:
        for attack in ["tamper", "extra", "symlink", "hardlink", "oversize", "nested"]:
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "report"
                write_report(example(), registry(), out)
                target = out / "report.md"
                if attack == "tamper":
                    target.write_text("arbitrary unreviewed participant")
                if attack == "extra":
                    (out / "private.txt").write_text("synthetic private")
                if attack in {"symlink", "hardlink"}:
                    target.unlink()
                    if attack == "symlink":
                        target.symlink_to(out / "results.json")
                    else:
                        os.link(out / "results.json", target)
                if attack == "oversize":
                    target.write_bytes(b"x" * (MAX_FILE + 1))
                if attack == "nested":
                    (out / "nested").mkdir()
                with self.assertRaises(Invalid):
                    verify_report(out)

    def test_cli_never_dumps_private_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"private":"FZKML_FORBIDDEN_SECRET"}')
            command = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "fzkml_ci",
                    "report",
                    "--results",
                    str(path),
                    "--output",
                    str(Path(tmp) / "report"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(command.returncode, 0)
            self.assertNotIn("FZKML_FORBIDDEN_SECRET", command.stderr)
            self.assertLess(len(command.stderr), 200)


class WorkflowTests(unittest.TestCase):
    def test_repository_workflows(self) -> None:
        check_repository()

    def test_security_mutations_are_blocked(self) -> None:
        for mutation in [
            "trigger",
            "permissions",
            "action",
            "timeout",
            "runner",
            "checkout",
            "secret",
            "cache",
            "matrix",
            "shell",
            "upload",
            "environment",
        ]:
            with self.subTest(mutation=mutation):
                wf = yaml.load(
                    (ROOT / ".github/workflows/cpu.yml").read_text(), Loader=yaml.BaseLoader
                )
                job = wf["jobs"]["validate"]
                if mutation == "trigger":
                    wf["on"] = {"pull_request_target": ""}
                if mutation == "permissions":
                    job["permissions"] = {"contents": "write"}
                if mutation == "action":
                    job["steps"][0]["uses"] = "actions/checkout@v4"
                if mutation == "timeout":
                    del job["timeout-minutes"]
                if mutation == "runner":
                    job["runs-on"] = "self-hosted"
                if mutation == "checkout":
                    job["steps"][0]["with"]["ref"] = "untrusted"
                if mutation == "secret":
                    job["env"] = {"TOKEN": "${{ secrets.TOKEN }}"}
                if mutation == "cache":
                    job["steps"].append({"uses": "actions/cache@v4"})
                if mutation == "matrix":
                    job["strategy"] = {"matrix": {"x": list(range(100))}}
                if mutation == "shell":
                    job["steps"][2]["run"] = "echo ${{ github.event.pull_request.title }}"
                if mutation == "upload":
                    job["steps"].append(
                        {
                            "uses": next(
                                a for a in ACTIONS if a.startswith("actions/upload-artifact@")
                            )
                        }
                    )
                if mutation == "environment":
                    job["environment"] = "public-reports"
                with self.assertRaises(Invalid):
                    check_workflow(wf)


if __name__ == "__main__":
    unittest.main()
