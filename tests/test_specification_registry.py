"""Mutation tests for scientific provenance, not mathematical/security proofs."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from specifications.validate import ROOT, check_attestation, checked_ref, schemas, validate


class SpecificationRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="fzkml-registry-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for directory in ("claims", "specifications", "docs", "schemas", "specs", "src", "tests"):
            shutil.copytree(
                ROOT / directory,
                self.root / directory,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        shutil.copytree(ROOT / "experiments", self.root / "experiments")

    def read(self, path: str) -> Any:
        return json.loads((self.root / path).read_text())

    def save(self, path: str, data: Any) -> None:
        (self.root / path).write_text(json.dumps(data, indent=2) + "\n")

    def invalid(self, pattern: str) -> None:
        with self.assertRaisesRegex(ValueError, pattern):
            validate(self.root)

    def test_valid_inventory_and_no_automatic_promotion(self) -> None:
        before = (self.root / "claims/registry.json").read_bytes()
        report = validate(self.root)
        self.assertEqual(report["status_counts"], {"planned": 8, "specified": 10, "tested": 5})
        self.assertEqual((report["source_nodes"], report["inspected_equations"]), (923, 20))
        self.assertEqual(report["declared_formal_artifacts"], 0)
        self.assertEqual(report["declared_independent_reviews"], 0)
        self.assertEqual(before, (self.root / "claims/registry.json").read_bytes())

    def test_missing_source_node(self) -> None:
        d = self.read("claims/source-map-v1.json")
        d["nodes"].pop(0)
        self.save("claims/source-map-v1.json", d)
        self.invalid("dangling source parent")

    def test_duplicate_alias(self) -> None:
        d = self.read("claims/source-map-v1.json")
        d["nodes"][1]["aliases"] = d["nodes"][0]["aliases"]
        self.save("claims/source-map-v1.json", d)
        self.invalid("duplicate source alias")

    def test_locator_drift(self) -> None:
        d = self.read("claims/source-map-v1.json")
        d["nodes"][0]["location"]["start_utf16"] += 1
        self.save("claims/source-map-v1.json", d)
        self.invalid("source locator drift")

    def test_edition_migration_required(self) -> None:
        d = self.read("docs/research/manuscript.json")
        d["observed_revision_id"] = "different-revision"
        self.save("docs/research/manuscript.json", d)
        self.invalid("edition migration required")

    def test_node_version_mismatch(self) -> None:
        d = self.read("claims/source-map-v1.json")
        d["nodes"][0]["source_version"] = "different-source"
        self.save("claims/source-map-v1.json", d)
        self.invalid("node source version mismatch")

    def test_equation_inspection_cannot_be_invented(self) -> None:
        d = self.read("claims/source-map-v1.json")
        row = next(n for n in d["nodes"] if n["kind"] == "equation")
        row["inspection_status"] = "equation-markup-inspected"
        row["inspection_record"] = "docs/research/s03-source-inspection.json"
        self.save("claims/source-map-v1.json", d)
        self.invalid("missing equation inspection")

    def test_claim_wrong_section(self) -> None:
        d = self.read("claims/registry.json")
        d["claims"][0]["source"]["section"] = "anchor.h.wrong"
        self.save("claims/registry.json", d)
        self.invalid("claim section mismatch")

    def test_claim_wrong_chapter(self) -> None:
        d = self.read("claims/registry.json")
        d["claims"][0]["source"]["chapter"] = 3
        self.save("claims/registry.json", d)
        self.invalid("claim source mapping mismatch")

    def test_relation_evidence_cannot_cross_profiles(self) -> None:
        d = self.read("claims/traceability-v1.json")
        d["records"][1]["relation_id"] = "fzknum-1.0.0"
        self.save("claims/traceability-v1.json", d)
        self.invalid("claim relation mismatch")

    def test_missing_claim_binding(self) -> None:
        d = self.read("claims/traceability-v1.json")
        d["records"].pop()
        self.save("claims/traceability-v1.json", d)
        self.invalid("incomplete claim traceability")

    def test_changed_specification_hash(self) -> None:
        path = self.root / "specs/m0/deployment-v0.1.md"
        path.write_text(path.read_text() + "\nChanged\n")
        self.invalid("artifact hash mismatch")

    def test_named_test_must_exist_even_with_valid_hash(self) -> None:
        path = "tests/test_transcript_privacy.py"
        ref = {
            "path": path + "::test_nonexistent",
            "sha256": hashlib.sha256((self.root / path).read_bytes()).hexdigest(),
        }
        with self.assertRaisesRegex(ValueError, "missing named test"):
            checked_ref(self.root, ref)

    def test_path_traversal_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe artifact"):
            checked_ref(self.root, {"path": "../private-source.docx", "sha256": "0" * 64})

    def test_symlink_ancestor_rejected(self) -> None:
        (self.root / "linked").symlink_to(self.root / "docs", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink artifact"):
            checked_ref(self.root, {"path": "linked/assurance.md", "sha256": "0" * 64})

    def test_unknown_schema_reference_does_not_fetch_network(self) -> None:
        d = self.read("claims/schema-v1.json")
        d["$ref"] = "https://example.invalid/unknown.json"
        self.save("claims/schema-v1.json", d)
        self.invalid("schema validation failed")
        self.assertIsNotNone(schemas(self.root))

    def test_tested_status_needs_implementation(self) -> None:
        d = self.read("claims/registry.json")
        d["claims"][0]["status"] = "tested"
        self.save("claims/registry.json", d)
        self.invalid("implemented status without implementation")

    def test_tested_status_needs_successful_execution(self) -> None:
        d = self.read("claims/traceability-v1.json")
        next(e for e in d["evidence"] if e["kind"] == "unit-test")["execution"]["outcome"] = (
            "failed"
        )
        self.save("claims/traceability-v1.json", d)
        self.invalid("tested status without successful test evidence")

    def test_execution_commit_must_match(self) -> None:
        d = self.read("claims/traceability-v1.json")
        next(e for e in d["evidence"] if e["kind"] == "unit-test")["execution"]["source_commit"] = (
            "0" * 40
        )
        self.save("claims/traceability-v1.json", d)
        self.invalid("execution commit mismatch")

    def test_formal_proof_cannot_reference_unit_test(self) -> None:
        d = self.read("claims/registry.json")
        row = next(c for c in d["claims"] if c["status"] == "tested")
        row["formal_proof"]["artifact_ids"] = row["evidence_ids"]
        self.save("claims/registry.json", d)
        self.invalid("formal statement mismatch")

    def test_formal_classification_needs_artifacts(self) -> None:
        d = self.read("claims/registry.json")
        d["claims"][0]["evidence_class"] = "formal"
        self.save("claims/registry.json", d)
        self.invalid("formal classification without proof artifacts")

    def test_review_status_needs_independent_artifact(self) -> None:
        d = self.read("claims/registry.json")
        d["claims"][0]["status"] = "reviewed"
        self.save("claims/registry.json", d)
        self.invalid("reviewed status without independent review")

    def test_unit_test_cannot_be_independent_review(self) -> None:
        d = self.read("claims/registry.json")
        row = next(c for c in d["claims"] if c["status"] == "tested")
        row["independent_review"]["artifact_ids"] = row["evidence_ids"]
        self.save("claims/registry.json", d)
        self.invalid("missing independent reviewer")

    def test_replication_requires_raw_result_manifest(self) -> None:
        d = self.read("claims/registry.json")
        next(c for c in d["claims"] if c["status"] == "tested")["status"] = "replicated"
        self.save("claims/registry.json", d)
        self.invalid("replication requires raw result manifest")

    def test_formal_evidence_requires_checker_execution(self) -> None:
        item = self.read("claims/traceability-v1.json")["evidence"][-1]
        item["kind"] = "formal-proof"
        item["formal"] = {"statement_id": "fixture-only"}
        with self.assertRaisesRegex(ValueError, "successful checker execution"):
            check_attestation(self.root, item)

    def test_formal_evidence_requires_kernel_declaration(self) -> None:
        d = self.read("claims/traceability-v1.json")
        d["evidence"][-1]["formal"] = {"statement_id": "fixture-only"}
        self.save("claims/traceability-v1.json", d)
        self.invalid("schema validation failed")

    def test_independent_reviewer_cannot_be_author(self) -> None:
        item = self.read("claims/traceability-v1.json")["evidence"][-1]
        item["kind"] = "independent-review"
        item["review"] = {
            "artifact": {"path": item["path"], "sha256": item["sha256"]},
            "date": "2026-11-24",
            "reviewed_source_commit": item["source_commit"],
            "reviewer": "fixture-author",
            "independent_from": ["fixture-author"],
        }
        with self.assertRaisesRegex(ValueError, "self review"):
            check_attestation(self.root, item)

    def test_nested_test_helper_is_not_discoverable(self) -> None:
        path = self.root / "tests/test_helper_fixture.py"
        path.write_text("def helper():\n    def test_hidden():\n        pass\n")
        with self.assertRaisesRegex(ValueError, "missing named test"):
            checked_ref(
                self.root,
                {
                    "path": "tests/test_helper_fixture.py::test_hidden",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                },
            )

    def test_candidate_cannot_be_marked_adopted(self) -> None:
        d = self.read("claims/candidate-evidence-v1.json")
        d["records"][0]["state"] = "adopted"
        self.save("claims/candidate-evidence-v1.json", d)
        self.invalid("schema validation failed")

    def test_candidate_skipped_test_cannot_count_as_passed(self) -> None:
        d = self.read("claims/candidate-evidence-v1.json")
        d["records"][0]["observation"]["passed"] += 1
        self.save("claims/candidate-evidence-v1.json", d)
        self.invalid("candidate skipped tests counted as passed")

    def test_candidate_hosted_counts_must_match(self) -> None:
        d = self.read("claims/candidate-evidence-v1.json")
        d["records"][0]["hosted_check_scope"]["language_math_passed"] += 1
        self.save("claims/candidate-evidence-v1.json", d)
        self.invalid("candidate hosted execution scope mismatch")

    def test_candidate_source_mapping_must_match(self) -> None:
        d = self.read("claims/candidate-evidence-v1.json")
        d["records"][0]["vectors"][0]["chapter"] = 40
        self.save("claims/candidate-evidence-v1.json", d)
        self.invalid("candidate source mapping mismatch")

    def test_candidate_requires_immutable_url(self) -> None:
        d = self.read("claims/candidate-evidence-v1.json")
        d["records"][0]["files"][0]["url"] = "https://github.com/FZKML/fzkml/blob/main/example"
        self.save("claims/candidate-evidence-v1.json", d)
        self.invalid("candidate immutable URL mismatch")

    def test_m4_requires_source_and_test_links(self) -> None:
        d = self.read("specifications/m4/contracts-v1.json")
        d["contracts"][0]["source_refs"].append("missing-source")
        self.save("specifications/m4/contracts-v1.json", d)
        self.invalid("dangling M4 source reference")

    def test_m4_requires_existing_named_test(self) -> None:
        d = self.read("specifications/m4/contracts-v1.json")
        d["contracts"][0]["required_tests"].append("test_nonexistent")
        self.save("specifications/m4/contracts-v1.json", d)
        self.invalid("missing M4 required test")

    def test_outcome_contract_requires_source_links(self) -> None:
        path = "specifications/data_outcomes/contracts-v1.json"
        d = self.read(path)
        d["contracts"][0]["source_refs"].append("missing-source")
        self.save(path, d)
        self.invalid("dangling data/outcome source reference")

    def test_outcome_plan_cannot_contain_invented_observations(self) -> None:
        path = "specifications/data_outcomes/adoption-v1.json"
        d = self.read(path)
        d["observations"] = [{"willing": True}]
        self.save(path, d)
        self.invalid("schema validation failed")

    def test_sector_card_cannot_claim_FZKML_deployment(self) -> None:
        path = "specifications/data_outcomes/sector-cards-v1.json"
        d = self.read(path)
        d["cards"][0]["FZKML_deployment_outcome"] = True
        self.save(path, d)
        self.invalid("schema validation failed")

    def test_unknown_status_rejected(self) -> None:
        d = self.read("claims/registry.json")
        d["claims"][0]["status"] = "verified"
        self.save("claims/registry.json", d)
        self.invalid("schema validation failed")


if __name__ == "__main__":
    unittest.main()
