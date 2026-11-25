"""Adversarial coverage for the bounded CI evidence comparison and release gates."""

from __future__ import annotations

import copy
import unittest

from fzkml_ci.evidence_gates import (
    FIXTURE,
    Lineage,
    benchmark_row,
    complete_arm,
    matched_benchmark,
    numeric_trace,
    release_gate,
    render_portal,
    strength_gate,
)
from fzkml_ci.validate import Invalid, load


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load(FIXTURE)

    def test_pairing_retains_timeout_or_missing_attempt(self) -> None:
        config = self.fixture["benchmark"]
        left = benchmark_row(config, 0)
        right = benchmark_row(config, 1)
        self.assertEqual(matched_benchmark(left, right, config["schedule"])["status"], "diagnostic")
        missing = copy.deepcopy(right)
        missing["repetitions"].pop()
        self.assertEqual(
            matched_benchmark(left, missing, config["schedule"])["status"], "inconclusive"
        )
        right["repetitions"][2]["timeout"] = True
        decision = matched_benchmark(left, right, config["schedule"])
        self.assertEqual(decision["status"], "inconclusive")
        self.assertNotIn("distributions", decision)

    def test_scope_and_setup_amortization_cannot_be_compared(self) -> None:
        config = self.fixture["benchmark"]
        left = benchmark_row(config, 0)
        right = benchmark_row(config, 1)
        right["scenario"]["statement"] = "different"
        self.assertEqual(matched_benchmark(left, right, config["schedule"])["status"], "unmatched")
        right = benchmark_row(config, 1)
        right["benchmark"]["setup_amortization"] = "100 repetitions"
        self.assertEqual(matched_benchmark(left, right, config["schedule"])["status"], "unmatched")

    def test_invalid_lineage_does_not_change_tip(self) -> None:
        config = self.fixture["lineage"]
        stream = Lineage(config)
        first, second = config["events"]
        stream.apply(first)
        state = stream.state()
        tip = stream.release("one", stream.tip, state)
        with self.assertRaisesRegex(Invalid, "duplicate-or-full-event"):
            stream.apply(first)
        with self.assertRaisesRegex(Invalid, "declared-unit-shift"):
            stream.apply(dict(second, unit="kWh"))
        with self.assertRaisesRegex(Invalid, "already-released-state"):
            stream.release("two", tip, stream.state())
        self.assertEqual((stream.tip, stream.state()), (tip, state))

    def test_memorization_and_unlicensed_checkpoint_are_rejected(self) -> None:
        config = self.fixture["release"]
        release_gate(config, {"Apache-2.0"})
        with self.assertRaisesRegex(Invalid, "synthetic-canary"):
            release_gate(dict(config, candidate=config["canary"].upper()), {"Apache-2.0"})
        config["assets"][1]["license"] = "unknown"
        with self.assertRaisesRegex(Invalid, "unknown-asset-license"):
            release_gate(config, {"Apache-2.0"})

    def test_seed_replay_and_selection_failures(self) -> None:
        config = self.fixture["outcomes"]
        self.assertEqual(numeric_trace(17, config), numeric_trace(17, config))
        self.assertNotEqual(numeric_trace(17, config, True), numeric_trace(17, config))
        seeds = config["seeds"]
        for missing in ("timed-out", "skipped", "canceled", "unsupported"):
            attempts = [{"seed": seed, "status": "completed"} for seed in seeds]
            attempts[-1]["status"] = missing
            self.assertEqual(complete_arm(attempts, seeds), "inconclusive")
            self.assertEqual(complete_arm(attempts[:-1], seeds), "inconclusive")

    def test_theorem_needs_bound_formal_evidence_and_portal_escapes_markup(self) -> None:
        claim = {
            "kind": "cryptographic-security",
            "status": "tested",
            "evidence_class": "unit-test",
            "formal_proof": {"artifact_ids": ["example"]},
        }
        with self.assertRaisesRegex(Invalid, "theorem-without-formal-evidence"):
            strength_gate(claim, [{"kind": "unit-test", "evidence_id": "example"}])
        page = render_portal(
            [
                {
                    "id": "FZK-EXAMPLE",
                    "status": "planned",
                    "class": "specification",
                    "statement": "<script>fixture</script>",
                    "sources": [],
                    "evidence": [
                        {"availability": "unavailable", "execution": {"outcome": "failed"}},
                    ],
                    "limitations": [],
                    "required_reviews": [],
                }
            ],
            "abc",
            [],
        )
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("unavailable", page)
        self.assertIn("failed", page)


if __name__ == "__main__":
    unittest.main()
