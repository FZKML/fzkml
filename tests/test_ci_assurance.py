"""Bounded engineering regressions, not production privacy or consensus proofs."""

from __future__ import annotations

import base64
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import quote_from_bytes

from jsonschema import Draft202012Validator, ValidationError

from specifications.ci_assurance.disclosure import scan_views
from specifications.ci_assurance.parameters import (
    check_parameters,
    clipped_query,
    ticket_map,
    weights,
)
from specifications.ci_assurance.planner import matrix_digest, plan_matrix
from specifications.ci_assurance.rounds import (
    Authority,
    State,
    classification,
    explore,
    invariant,
    replay,
)
from specifications.ci_assurance.run import (
    HERE,
    ROOT,
    check_report,
    concurrent_conformance,
    read_json,
    run,
)


class CIAssuranceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="fzkml-ci-assurance-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = read_json(HERE / "fixtures-v1.json")
        self.parameters = copy.deepcopy(self.fixture["parameters"])
        self.matrix = read_json(HERE / "matrix-v1.json")

    def parameters_check(self, config: dict[str, Any]) -> dict[str, Any]:
        return check_parameters(config, HERE / "dp-geometric-v1.md")

    def plan(self, matrix: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        # This is an injected synthetic trust anchor, not a human approval.
        return plan_matrix(
            matrix,
            frozenset({matrix_digest(matrix)}),
            HERE / "dataset-v1.json",
            HERE / "software-v1.json",
            **kwargs,
        )

    def public_views(self) -> list[dict[str, Any]]:
        for entry in self.fixture["views"]:
            (self.root / entry["path"]).write_text(entry["payload"])
        return [{k: v for k, v in e.items() if k != "payload"} for e in self.fixture["views"]]

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "src")}
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "specifications.ci_assurance.run",
                "--output",
                str(self.root / "report.json"),
                *args,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_fault_replay_and_abort_classes(self) -> None:
        releases = []
        for row in self.fixture["traces"]:
            result = replay(row["events"])
            self.assertEqual(
                (classification(result), result.charged, result.releases),
                (row["classification"], row["charged"], row["releases"]),
            )
            if result.releases:
                releases.append((result.accepted, result.cached))
        self.assertEqual(len(set(releases)), 1)
        self.assertEqual(len(releases), 5)
        with self.assertRaisesRegex(ValueError, "trace-resource"):
            replay([["restart", "", "", "h0"]] * 65)

    def test_duplicate_release_mutation(self) -> None:
        result = explore(unsafe_release=True)
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(
            [event[0] for event in result["counterexample"]][-2:], ["release", "release"]
        )
        self.assertEqual(len(result["counterexample"]), 8)

    def test_exhaustive_model_and_inconclusive_bound(self) -> None:
        self.assertEqual(
            explore(), {"outcome": "successful", "states": 34, "edges": 374, "counterexample": []}
        )
        self.assertEqual(explore(1)["outcome"], "inconclusive")
        with self.assertRaisesRegex(ValueError, "model-resource"):
            explore(4097)

    def test_concurrent_history_and_conflicting_head(self) -> None:
        self.assertEqual(concurrent_conformance(), 27)
        authority = Authority()
        authority.apply(("admit", "c0", "first", "h0"))
        authority.apply(("admit", "c0", "second", "h0"))
        authority.apply(("admit", "c1", "other", "h1"))
        self.assertEqual(authority.state.pending, (("c0", "first"),))
        self.assertEqual(authority.state.version, 1)
        authority.apply(("release", "", "", "h0"))
        self.assertEqual(authority.state.releases, 0)

    def test_restart_rejects_rollback(self) -> None:
        authority = Authority()
        old = authority.snapshot()
        authority.apply(("admit", "c0", "p0", "h0"))
        with self.assertRaisesRegex(ValueError, "rollback"):
            Authority.restore(old, authority.state.version)
        recovered = Authority.restore(authority.snapshot(), authority.state.version)
        self.assertEqual(recovered.state, authority.state)
        for state in (
            replace(State(), phase="forged"),
            replace(State(), charged=1),
            replace(State(), phase="reserved"),
            replace(State(), releases=-1),
        ):
            with self.assertRaises(ValueError):
                invariant(state)

    def test_inventory_canaries_and_unlisted_outputs(self) -> None:
        inventory = self.public_views()
        canary = self.fixture["canary"].encode()
        self.assertEqual(scan_views(self.root, inventory, canary)["files_scanned"], 5)
        encodings = (
            canary,
            canary.hex().encode(),
            canary.hex().upper().encode(),
            base64.b64encode(canary),
            quote_from_bytes(canary, safe="").encode(),
        )
        for entry in inventory:
            target = self.root / entry["path"]
            for encoded in encodings:
                with self.subTest(channel=entry["channel"], encoding=len(encoded)):
                    target.write_bytes(b"prefix " + encoded + b" suffix")
                    with self.assertRaisesRegex(ValueError, "prohibited-canary") as caught:
                        scan_views(self.root, inventory, canary)
                    self.assertNotIn(canary.decode(), str(caught.exception))
            target.write_text("safe\n")
        (self.root / "unexpected.txt").write_text("safe")
        with self.assertRaisesRegex(ValueError, "unlisted-public-export"):
            scan_views(self.root, inventory, canary)
        (self.root / "unexpected.txt").unlink()
        (self.root / inventory[0]["path"]).unlink()
        with self.assertRaisesRegex(ValueError, "missing-declared-export"):
            scan_views(self.root, inventory, canary)
        with self.assertRaisesRegex(ValueError, "missing-release-view"):
            scan_views(self.root, inventory[1:], canary)

    def test_scanner_path_and_resource_bounds(self) -> None:
        inventory = self.public_views()
        canary = self.fixture["canary"].encode()
        for path in ("../escape.txt", "/absolute.txt", ".hidden.txt"):
            altered = copy.deepcopy(inventory)
            altered[0]["path"] = path
            with self.assertRaisesRegex(ValueError, "unsafe-view"):
                scan_views(self.root, altered, canary)
        target = self.root / inventory[0]["path"]
        target.write_bytes(b"x" * 1048577)
        with self.assertRaisesRegex(ValueError, "scan-byte-budget"):
            scan_views(self.root, inventory, canary)
        target.unlink()
        target.symlink_to(self.root / inventory[1]["path"])
        with self.assertRaisesRegex(ValueError, "symlink"):
            scan_views(self.root, inventory, canary)

    def test_exact_ticket_law_and_adjacency(self) -> None:
        tickets = Counter(ticket_map(17))
        expected = (256, 128, 64, 32, 16, 8, 4, 2, 1, 1, 2, 4, 8, 16, 32, 64, 128)
        self.assertEqual(tuple(tickets[z] for z in range(17)), expected)
        self.assertEqual(weights(17), expected)
        self.assertEqual(sum(tickets.values()), 766)
        self.assertEqual(self.parameters_check(self.parameters)["composed_ratio"], "4")
        self.assertEqual(clipped_query((100, -100, 1)), 1)
        for x in range(-3, 4):
            for y in range(-3, 4):
                self.assertIn(
                    (clipped_query((x, 1, 0)) - clipped_query((y, 1, 0))) % 17, (0, 1, 2, 15, 16)
                )
        replacement = copy.deepcopy(self.parameters)
        replacement.update(
            adjacency="replace-fixed-slot", sensitivity=2, releases=[self.parameters["releases"][0]]
        )
        self.assertEqual(self.parameters_check(replacement)["single_release_ratio"], "4")

    def test_dp_parameter_mutations(self) -> None:
        for key, value in (
            ("sampler", "continuous-gaussian"),
            ("q", 16),
            ("clipping", 2),
            ("cohort", 4),
            ("scale", 8),
            ("released_value", "decoded-integer"),
            ("query", "arbitrary-training"),
            ("amplification", "subsampled"),
            ("amplification_factor", 2),
            ("claim_scope", "full-transcript"),
            ("theorem_sha256", "0" * 64),
            ("sensitivity", 0),
            ("budget_ratio", 2),
        ):
            config = copy.deepcopy(self.parameters)
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parameters_check(config)

    def test_repeated_release_accounting(self) -> None:
        config = copy.deepcopy(self.parameters)
        config["releases"][1]["cached_retransmission"] = False
        with self.assertRaisesRegex(ValueError, "unaccounted-repeated"):
            self.parameters_check(config)
        config = copy.deepcopy(self.parameters)
        config["releases"][2]["noise_instance"] = "n0"
        with self.assertRaisesRegex(ValueError, "noise-reuse"):
            self.parameters_check(config)
        config = copy.deepcopy(self.parameters)
        config["releases"].append(
            {"id": "r2", "noise_instance": "n2", "cached_retransmission": False}
        )
        with self.assertRaisesRegex(ValueError, "release-budget"):
            self.parameters_check(config)
        config = copy.deepcopy(self.parameters)
        config.update(adjacency="replace-fixed-slot", sensitivity=2)
        with self.assertRaisesRegex(ValueError, "composed-privacy-budget"):
            self.parameters_check(config)

    def test_matrix_totals_and_no_dispatch(self) -> None:
        result = self.plan(self.matrix)
        self.assertEqual(result["totals"], self.matrix["quotas"])
        self.assertEqual(len(result["rows"]), 4)
        self.assertFalse(result["dispatch_authorized"])
        with self.assertRaisesRegex(ValueError, "live-dispatch-unsupported"):
            self.plan(self.matrix, dispatch_requested=True)
        with self.assertRaisesRegex(ValueError, "untrusted-dispatch"):
            self.plan(self.matrix, trusted_context=False)
        with self.assertRaisesRegex(ValueError, "review-digest-not-authorized"):
            plan_matrix(
                self.matrix, frozenset(), HERE / "dataset-v1.json", HERE / "software-v1.json"
            )
        review = read_json(HERE / "matrix-review-v1.json")
        self.assertEqual(review["live_approved_digests"], [])
        self.assertIsNone(review["human_approval"])

    def test_matrix_budget_mutations(self) -> None:
        for key, value in (("cpus", 10000), ("hardware", "*"), ("gpus", 1), ("timeout_seconds", 0)):
            matrix = copy.deepcopy(self.matrix)
            matrix["resources"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.plan(matrix)
        mutations = []
        matrix = copy.deepcopy(self.matrix)
        del matrix["quotas"]["cpu_seconds"]
        mutations.append(matrix)
        matrix = copy.deepcopy(self.matrix)
        matrix["quotas"]["serial_seconds"] = 1
        mutations.append(matrix)
        matrix = copy.deepcopy(self.matrix)
        matrix["axes"] = {
            "a": ["v" + str(i) for i in range(8)],
            "b": ["s" + str(i) for i in range(8)],
        }
        mutations.append(matrix)
        matrix = copy.deepcopy(self.matrix)
        matrix["axes"]["seed"] = ["*"]
        mutations.append(matrix)
        for key, value in (
            ("dataset_sha256", "0" * 64),
            ("software_sha256", "latest"),
            ("attempts", 10000),
            ("command_id", "curl attacker"),
        ):
            matrix = copy.deepcopy(self.matrix)
            matrix[key] = value
            mutations.append(matrix)
        for matrix in mutations:
            with self.assertRaises(ValueError):
                self.plan(matrix)

    def test_closed_report_schema_and_no_status_promotion(self) -> None:
        report = run(HERE / "fixtures-v1.json")
        validator = Draft202012Validator(read_json(HERE / "report-schema-v1.json"))
        validator.validate(report)
        self.assertEqual(report["scientific_claim_ids"], [])
        self.assertFalse(report["publication"]["approved"])
        self.assertTrue(all(row["outcome"] == "successful" for row in report["records"]))
        for outcome in ("failed", "inconclusive", "unsupported", "canceled"):
            altered = copy.deepcopy(report)
            altered["records"][0]["outcome"] = outcome
            validator.validate(altered)
            with self.assertRaisesRegex(ValueError, "non-success"):
                check_report(altered)
        mutations: tuple[Callable[[dict[str, Any]], Any], ...] = (
            lambda r: r["publication"].update(approved=True),
            lambda r: r.update(secret_witness="forbidden"),
            lambda r: r["records"][0]["observations"].update(raw_witness="forbidden"),
            lambda r: r["records"][0].update(outcome="skipped"),
            lambda r: r["records"].pop(),
        )
        for mutate in mutations:
            altered = copy.deepcopy(report)
            mutate(altered)
            with self.assertRaises(ValidationError):
                validator.validate(altered)

    def test_cli_baseline_and_positive_fixture_mutation(self) -> None:
        self.assertEqual(self.cli().returncode, 0)
        fixture = copy.deepcopy(self.fixture)
        fixture["views"][0]["payload"] = fixture["canary"]
        altered = self.root / "mutated.json"
        altered.write_text(json.dumps(fixture))
        result = self.cli("--fixtures", str(altered))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(fixture["canary"], result.stdout + result.stderr)
        self.assertIn('"outcome": "failed"', result.stdout)
        failure = read_json(self.root / "report.json")
        Draft202012Validator(read_json(HERE / "report-schema-v1.json")).validate(failure)
        self.assertEqual(failure["outcome"], "failed")
        self.assertEqual(failure["records"], [])
        with self.assertRaisesRegex(ValueError, "non-success"):
            check_report(failure)
        result = self.cli("--mutation", "duplicate-release")
        self.assertEqual(result.returncode, 1)
        result = self.cli("--max-states", "1")
        self.assertEqual(result.returncode, 1)
        self.assertIn('"outcome": "inconclusive"', result.stdout)
