import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_research import validate  # noqa: E402
from research_fixtures import canonical_bytes, default_entities, generate, split  # noqa: E402


class FixtureTests(unittest.TestCase):
    def test_stable_public_bytes_and_seed_separation(self):
        expected = (ROOT / "assets/public/synthetic-cross-silo-v1.json").read_bytes()
        self.assertEqual(canonical_bytes(generate()), expected)
        self.assertNotEqual(canonical_bytes(generate(0)), canonical_bytes(generate(1)))

    def test_entity_time_and_duplicate_separation(self):
        data = generate()
        parts = split(data["records"], *default_entities())
        self.assertEqual([len(parts[k]) for k in ("train", "evaluation", "excluded")], [32, 16, 52])
        self.assertTrue(
            all(r["event_time"] <= 4 and r["label_available_at"] <= 4 for r in parts["train"])
        )
        self.assertTrue(all(r["event_time"] > 4 for r in parts["evaluation"]))
        for field in ("entity_id", "duplicate_group"):
            self.assertFalse(
                {r[field] for r in parts["train"]} & {r[field] for r in parts["evaluation"]}
            )
        self.assertEqual(
            len(parts["train"]) + len(parts["evaluation"]) + len(parts["excluded"]),
            len(data["records"]),
        )

    def test_future_label_never_enters_training(self):
        rows = generate()["records"]
        target = next(
            r for r in rows if r["entity_id"] == "synthetic:s0-e1" and r["event_time"] == 2
        )
        target["label_available_at"] = 9
        parts = split(rows, *default_entities())
        self.assertNotIn(target["record_id"], {r["record_id"] for r in parts["train"]})

    def test_entity_overlap_fails(self):
        train, evaluation = default_entities()
        with self.assertRaisesRegex(ValueError, "entity policy overlaps"):
            split(generate()["records"], train, evaluation | train)

    def test_conflicting_duplicate_payload_fails(self):
        rows = generate()["records"]
        duplicate = next(r for r in rows if r["record_id"].endswith("v0-b"))
        duplicate["target"] += 1
        with self.assertRaisesRegex(ValueError, "duplicate-group"):
            split(rows, *default_entities())

    def test_duplicate_id_and_bad_seed_fail(self):
        rows = generate()["records"]
        with self.assertRaisesRegex(ValueError, "duplicate record ID"):
            split(rows + [rows[0]], *default_entities())
        for seed in (-1, 2**32, True):
            with self.assertRaises(ValueError):
                generate(seed)


class ResearchMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ("docs/research", "claims", "specs/m0", "experiments/m0", "assets/public"):
            shutil.copytree(ROOT / directory, self.root / directory)

    def mutate(self, path, change):
        file = self.root / path
        value = json.loads(file.read_text())
        change(value)
        file.write_text(json.dumps(value))

    def test_coverage_and_evidence_are_not_confused(self):
        result = validate(self.root)
        self.assertEqual((result["chapters"], result["exercises"]), (80, 48))
        self.assertEqual(result["claims"], 16)
        for name in (
            "empirical_evidence",
            "externally_reviewed",
            "formal_artifacts_with_declared_assumptions",
        ):
            self.assertEqual(result[name], 0)

    def test_missing_chapter_is_not_covered(self):
        self.mutate("docs/research/coverage.json", lambda d: d["items"].pop(0))
        with self.assertRaisesRegex(ValueError, "chapter coverage"):
            validate(self.root)

    def test_dangling_claim_fails(self):
        self.mutate(
            "docs/research/coverage.json", lambda d: d["items"][0]["claim_ids"].append("unknown")
        )
        with self.assertRaisesRegex(ValueError, "dangling coverage claim"):
            validate(self.root)

    def test_wrong_source_version_fails(self):
        self.mutate("docs/research/coverage.json", lambda d: d.update(source_version="other"))
        with self.assertRaisesRegex(ValueError, "source version mismatch"):
            validate(self.root)

    def test_unimplemented_status_cannot_be_promoted(self):
        self.mutate("claims/registry.json", lambda d: d["claims"][0].update(status="tested"))
        with self.assertRaisesRegex(ValueError, "unimplemented claim promoted"):
            validate(self.root)

    def test_unit_test_is_not_formal_proof(self):
        def promote(d):
            eid = d["claims"][0]["evidence_ids"][0]
            d["evidence"][0]["kind"] = "unit-test"
            d["claims"][0]["formal_proof"]["artifact_ids"] = [eid]

        self.mutate("claims/registry.json", promote)
        with self.assertRaisesRegex(ValueError, "wrong special evidence kind"):
            validate(self.root)

    def test_equation_payload_cannot_be_invented(self):
        self.mutate(
            "docs/research/source-index.json",
            lambda d: d["equations"][0].update(source_review="verified"),
        )
        with self.assertRaisesRegex(ValueError, "authorized inspected artifact"):
            validate(self.root)

    def test_missing_assurance_cell_fails(self):
        self.mutate(
            "experiments/m0/capabilities.json",
            lambda d: d["families"][0]["assurance_modes"].pop("inference-proof"),
        )
        with self.assertRaisesRegex(ValueError, "assurance mode gap"):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()
