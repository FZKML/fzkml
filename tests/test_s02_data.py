"""Independent M5 numerical invariants, privacy boundaries and process-crash recovery."""

from __future__ import annotations

import copy
import itertools
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace
from fractions import Fraction as F
from pathlib import Path

from python.fzkml_math.data_experiment_contract import validate_config
from python.fzkml_math.data_lineage import (
    ORGS,
    Policy,
    Row,
    digest,
    partition,
    snapshot,
    synthetic_parts,
    verify_snapshot,
)
from python.fzkml_math.join_reference import JoinPolicy, authorized_join, binary_correspondence
from python.fzkml_math.streaming_data import Stream
from python.fzkml_math.summary_cache import (
    FeatureModel,
    SummaryCache,
    approximation_bound,
    break_even,
    cache_key,
    direct,
    evaluate,
    examples,
    query_witness_key,
    stats,
)
from python.fzkml_math.toy_generation import (
    control,
    copied_training_sample,
    denoise,
    require_real_claim,
    verify_control,
    verify_denoising,
)

ROOT = Path(__file__).resolve().parents[1]


def row(i: int = 0, value: int = 1, org: str = ORGS[0], time: int = 2) -> Row:
    return Row(
        f"synthetic:event{i}",
        f"synthetic:p{i}",
        org,
        time,
        value,
        1,
        "cm",
        "holdout" if i == 3 else "train",
    )


def event(
    r: Row, version: int = 1, previous: str | None = None, operation: str = "upsert"
) -> dict[str, object]:
    return {
        "id": r.id,
        "version": version,
        "previous": previous,
        "operation": operation,
        "row": asdict(r),
        "arrival_time": 20,
    }


class SnapshotTests(unittest.TestCase):
    def test_dag_and_partition_mutations_change_or_invalidate_identity(self) -> None:
        parts = synthetic_parts()
        p = Policy()
        state = snapshot(parts, p)
        self.assertEqual(verify_snapshot(state, parts, p), "selection-membership-only")
        expected = {v["organization"]: v["digest"] for v in parts}
        self.assertIn("trusted-inventory", verify_snapshot(state, parts, p, expected))
        mutated = copy.deepcopy(parts)
        mutated[0]["rows"][0]["value"] += 1
        with self.assertRaises(ValueError):
            snapshot(mutated, p)
        for policy in (
            replace(p, version="synthetic-policy-2"),
            replace(p, schema_version="raw-row-2"),
            replace(p, preprocessing_version="exact-cm-mm-v2"),
        ):
            self.assertNotEqual(snapshot(parts, policy)["identity"], state["identity"])
        changed = tuple(Row(**r) for r in parts[0]["rows"])
        new = (partition((replace(changed[0], value=9), *changed[1:]), ORGS[0]), *parts[1:])
        self.assertNotEqual(snapshot(new, p)["identity"], state["identity"])
        with self.assertRaises(ValueError):
            verify_snapshot(snapshot(new, p), new, p, expected)

    def test_selected_membership_does_not_imply_completeness(self) -> None:
        parts = synthetic_parts()
        p = Policy()
        partial = snapshot(parts[:2], p)
        self.assertEqual(verify_snapshot(partial, parts[:2], p), "selection-membership-only")
        with self.assertRaises(ValueError):
            verify_snapshot(partial, parts[:2], p, {x["organization"]: x["digest"] for x in parts})
        altered = copy.deepcopy(partial)
        altered["manifest"]["dag"].pop(1)
        with self.assertRaises(ValueError):
            verify_snapshot(altered, parts[:2], p)

    def test_versioned_source_and_original_vectors(self) -> None:
        book = json.loads((ROOT / "tests/vectors/book/data-lineage-v1.json").read_text())
        duplicate = book["vectors"][0]
        self.assertEqual(
            duplicate["verified_inputs"]["rows_at_A"] * duplicate["verified_inputs"]["rows_at_B"],
            duplicate["expected"]["joined_rows"],
        )
        expected = book["vectors"][1]["expected"]
        world = binary_correspondence()
        self.assertEqual([[*k, str(p)] for k, p in world["equal"].items()], expected["equal_joint"])
        self.assertEqual(
            [[*k, str(p)] for k, p in world["opposite"].items()], expected["opposite_joint"]
        )
        f = json.loads((ROOT / "tests/vectors/synthetic/data-lineage-v1.json").read_text())
        self.assertEqual(
            snapshot(synthetic_parts(), Policy())["identity"], f["snapshot"]["expected_identity"]
        )
        self.assertEqual(denoise(), f["denoising"])

    def test_unit_time_split_and_hash_dictionary_leak(self) -> None:
        with self.assertRaises(ValueError):
            partition((replace(row(), unit="m"),), ORGS[0])
        wrong = replace(row(3), split="train")
        with self.assertRaises(ValueError):
            snapshot((partition((wrong,), ORGS[0]),), Policy())
        s = snapshot((partition((replace(row(), time=11),), ORGS[0]),), Policy())
        self.assertEqual(s["manifest"]["selected_count"], 0)
        committed = partition((row(value=3),), ORGS[0])["digest"]
        guesses = [
            v for v in range(-4, 5) if partition((row(value=v),), ORGS[0])["digest"] == committed
        ]
        self.assertEqual(guesses, [3])  # unsalted content hashes are not hiding commitments


class JoinTests(unittest.TestCase):
    def test_duplicate_multiplicity_caps_authorization_and_public_view(self) -> None:
        rows = tuple(
            replace(row(value=1, org=org), id=f"synthetic:{i}-{j}")
            for i, org in enumerate(ORGS)
            for j in range((2, 3, 1)[i])
        )
        policy = JoinPolicy()
        r = authorized_join(
            rows, policy, recipient="synthetic:trusted-operator", purpose=policy.purpose
        )
        self.assertEqual(r["privileged_synthetic_diagnostics"]["matched_pairs"]["synthetic:p0"], 6)
        self.assertEqual(r["privileged_synthetic_diagnostics"]["dropped_by_cap"], 4)
        public = authorized_join(rows, policy, recipient=policy.recipient, purpose=policy.purpose)
        self.assertNotIn("privileged_synthetic_diagnostics", public)
        self.assertNotIn("synthetic:p0", json.dumps(public))
        for kwargs in (
            {"recipient": "synthetic:intruder", "purpose": policy.purpose},
            {"recipient": policy.recipient, "purpose": "synthetic:other-purpose"},
        ):
            with self.assertRaises(ValueError):
                authorized_join(
                    rows, policy, recipient=kwargs["recipient"], purpose=kwargs["purpose"]
                )
        with self.assertRaises(ValueError):
            authorized_join(
                rows,
                policy,
                recipient=policy.recipient,
                purpose=policy.purpose,
                require_private_psi=True,
            )
        self.assertEqual(2 * 3, 6)

    def test_entity_sensitivity_attained_and_unrelated_entities_not_displaced(self) -> None:
        p = JoinPolicy()
        positive = tuple(
            replace(row(value=1, org=o), id=f"synthetic:positive-{i}-{j}")
            for i, o in enumerate(ORGS)
            for j in range((2, 1, 1)[i])
        )
        negative = tuple(replace(r, value=-1) for r in positive)

        def release(rows: tuple[Row, ...]) -> F:
            return F(
                authorized_join(rows, p, recipient=p.recipient, purpose=p.purpose)["public_output"][
                    "value"
                ]
            )

        self.assertEqual(abs(release(positive) - release(())), p.sensitivity("add-remove-entity"))
        self.assertEqual(
            abs(release(positive) - release(negative)), p.sensitivity("replace-entity")
        )
        other = tuple(replace(r, entity="synthetic:p1", id=r.id + "x", value=-1) for r in positive)
        self.assertEqual(
            release(positive + other) - release(other), p.sensitivity("add-remove-entity")
        )
        # Enumerate a bounded scalar slot universe independently of join implementation.
        for values in itertools.product(range(-3, 4), repeat=2):
            for changed in itertools.product(range(-3, 4), repeat=2):
                self.assertLessEqual(
                    abs(F(sum(values) - sum(changed), 8)), p.sensitivity("replace-entity")
                )

    def test_fixed_alias_map_caps_one_privacy_entity_across_aliases(self) -> None:
        p = JoinPolicy()
        base = tuple(
            replace(row(org=o), id=f"synthetic:base{i}-{j}")
            for i, o in enumerate(ORGS)
            for j in range((2, 1, 1)[i])
        )
        aliases = base + tuple(replace(r, id=r.id + "alias", entity="synthetic:p1") for r in base)
        unaligned = authorized_join(aliases, p, recipient=p.recipient, purpose=p.purpose)
        aligned = replace(
            p, entity_map=(("synthetic:p0", "synthetic:p0"), ("synthetic:p1", "synthetic:p0"))
        )
        result = authorized_join(aliases, aligned, recipient=p.recipient, purpose=p.purpose)
        self.assertGreater(
            F(unaligned["public_output"]["value"]), p.sensitivity("add-remove-entity")
        )
        self.assertEqual(
            F(result["public_output"]["value"]), aligned.sensitivity("add-remove-entity")
        )

    def test_missing_correspondence_and_private_denominator_counterexample(self) -> None:
        worlds = binary_correspondence()
        self.assertTrue(worlds["same_marginals"])
        self.assertNotEqual(worlds["equal_predictor"], worlds["opposite_predictor"])
        self.assertEqual(worlds["cross_world_prediction_error"], 1)
        missing = tuple(row(org=o) for o in ORGS[:2])
        p = JoinPolicy()
        result = authorized_join(missing, p, recipient=p.recipient, purpose=p.purpose)
        self.assertEqual(F(result["public_output"]["value"]), 0)
        # Variable-count average changes the function; fixed-denominator theorem does not transfer.
        self.assertGreater(abs(F(2) - F(2 - 2, 2)), F(2, 8))


class SummaryTests(unittest.TestCase):
    def test_full_data_matches_sufficient_statistics_and_approximation_bounds(self) -> None:
        model = FeatureModel()
        rows = examples(23)
        exact = stats(rows, model)
        approx = stats(rows, model, F(1, 2))
        self.assertEqual(len(exact), 7)
        for a, b in itertools.product((F(-2), F(0), F(1, 2), F(2)), repeat=2):
            theta = (a, b)
            full = direct(rows, theta, model)
            self.assertEqual(full, evaluate(exact, theta, model))
            reduced = evaluate(approx, theta, model)
            bound = approximation_bound(theta, model)
            self.assertLessEqual(abs(reduced["objective"] - full["objective"]), bound["objective"])
            for i in range(2):
                self.assertLessEqual(
                    abs(reduced["gradient"][i] - full["gradient"][i]), bound[f"gradient{i}"]
                )
        incomplete = dict(exact)
        del incomplete["q"]
        with self.assertRaises(ValueError):
            evaluate(incomplete, (F(0), F(0)), model)

    def test_context_cache_invalidation_and_witness_head_binding(self) -> None:
        m = FeatureModel()
        key = cache_key("data-1", m, "pre-1", "policy-1", "schema-1")
        variants = [
            cache_key("data-2", m, "pre-1", "policy-1", "schema-1"),
            cache_key("data-1", replace(m, gain=F(2)), "pre-1", "policy-1", "schema-1"),
            cache_key("data-1", m, "pre-2", "policy-1", "schema-1"),
            cache_key("data-1", m, "pre-1", "policy-2", "schema-1"),
            cache_key("data-1", m, "pre-1", "policy-1", "schema-2"),
        ]
        self.assertTrue(all(x != key for x in variants))
        self.assertNotEqual(
            query_witness_key(key, (F(0), F(0))), query_witness_key(key, (F(1), F(0)))
        )
        with self.assertRaises(FrozenInstanceError):
            m.gain = F(2)  # type: ignore[misc]
        with tempfile.TemporaryDirectory() as d:
            c = SummaryCache(Path(d))
            payload = stats(examples(4), m)
            c.put(key, payload)
            self.assertEqual(c.get(key), payload)
            for stale in variants:
                with self.assertRaises(FileNotFoundError):
                    c.get(stale)
            path = Path(d) / (key + ".json")
            record = json.loads(path.read_text())
            record["payload"]["t0"] = "123"
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                c.get(key)

    def test_mean_regularization_and_self_hash_do_not_prove_cache_correctness(self) -> None:
        m = FeatureModel()
        rows = ((F(0), F(1)), (F(0), F(1)))
        summary = stats(rows, m)
        self.assertEqual(evaluate(summary, (F(1, 2), F(0)), m)["gradient"], (0, 0))
        self.assertNotEqual(evaluate(summary, (F(2, 3), F(0)), m)["gradient"], (0, 0))
        with tempfile.TemporaryDirectory() as d:
            key = cache_key("snapshot", m, "pre", "policy", "schema")
            cache = SummaryCache(Path(d))
            cache.put(key, summary)
            path = Path(d) / (key + ".json")
            record = json.loads(path.read_text())
            record["payload"]["t0"] = "999"
            record["payload_digest"] = digest("cache-payload", record["payload"])
            from python.fzkml_math.data_lineage import canonical

            path.write_bytes(canonical(record))
            self.assertNotEqual(
                evaluate(cache.get(key), (F(0), F(0)), m), direct(rows, (F(0), F(0)), m)
            )

    def test_summary_leakage_and_no_invented_amortization(self) -> None:
        s = stats(((F(1), F(-1)),), FeatureModel())
        self.assertEqual(F(s["t0"]), -1)  # clean sufficient stats reveal the one label
        self.assertEqual(break_even(3.0, 2.0, 1.0), 4)
        self.assertIsNone(break_even(3.0, 1.0, 2.0))
        with self.assertRaises(ValueError):
            break_even(-1.0, 2.0, 1.0)


class ToyFamilyTests(unittest.TestCase):
    def test_complete_denoising_path_and_quantized_comparison(self) -> None:
        exact = denoise()
        quant = denoise(scale=16)
        verify_denoising(exact)
        verify_denoising(quant, scale=16)
        self.assertEqual(exact["sampling_steps"], 3)
        self.assertEqual(exact["pixel_updates"], 12)
        gain = F(7, 5) * F(73, 60) * F(17, 16)
        self.assertEqual(
            [F(x) for x in exact["output"]], [gain * x for x in (F(1, 2), F(-1, 2), F(1), F(-1))]
        )
        self.assertGreater(
            F(exact["zero_target_mse"]), F(5, 8)
        )  # untrained predictor worsens this metric
        truncated = copy.deepcopy(exact)
        truncated["trace"].pop(1)
        with self.assertRaises(ValueError):
            verify_denoising(truncated)
        self.assertTrue(copied_training_sample((1, 2), ((1, 2), (0, 0))))
        for claim in (
            "training-proof",
            "inference-proof",
            "environment-authenticity",
            "adaptive-DP",
            "model-family-safety",
        ):
            with self.assertRaises(ValueError):
                require_real_claim(claim)

    def test_simulated_control_rejects_wrong_units_and_hallucinated_events(self) -> None:
        r = control()
        verify_control(r)
        self.assertEqual(r["simulated_return"], -5)
        for key, value in (
            ("reward_unit", "dollars"),
            ("provenance", "world-model-prediction"),
            ("next_state", 999),
        ):
            bad = copy.deepcopy(r)
            bad["trajectory"][0][key] = value
            with self.assertRaises(ValueError):
                verify_control(bad)


class ExperimentContractTests(unittest.TestCase):
    def test_config_and_schema_do_not_promote_unimplemented_modes(self) -> None:
        from jsonschema import Draft202012Validator

        config = json.loads((ROOT / "experiments/s02-data/config-v1.json").read_text())
        validate_config(config)
        for group, key, value in [
            ("summary", "lambda", "2"),
            ("toy", "training", "verified"),
            ("stream", "DP_guarantee", True),
            ("join", "crypto_psi", "verified"),
        ]:
            changed = copy.deepcopy(config)
            changed[group][key] = value
            with self.assertRaises(ValueError):
                validate_config(changed)
        schema = json.loads((ROOT / "schemas/s02-data-run-1.0.0.json").read_text())
        Draft202012Validator.check_schema(schema)
        proof = copy.deepcopy(config["proof_amortization"])
        proof["status"] = "verified"
        self.assertFalse(
            Draft202012Validator(schema["properties"]["proof_amortization"]).is_valid(proof)
        )
        with self.assertRaises(ValueError):
            verify_control(control(1))
        verify_control(control(1), expected_steps=1)


class StreamingTests(unittest.TestCase):
    def test_four_round_corrections_late_arrivals_tombstones_and_no_refund(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.sqlite"
            s = Stream(path, create=True)
            e0 = event(row())
            e1 = event(row(1, 2, ORGS[1], 5))
            h0 = s.ingest(e0)
            h1 = s.ingest(e1)
            first = s.advance(10, expected_parent="genesis")
            s.reserve("synthetic:r1", first["snapshot"])
            self.assertEqual(s.recover_release("synthetic:r1")["sum_mm"], 30)
            late = event(row(2, 3, ORGS[2], 4))
            with self.assertRaises(ValueError):
                s.ingest(late)
            s.ingest(late, allow_closed_revision=True)
            second = s.advance(10, expected_parent=first["snapshot"])
            s.reserve("synthetic:r2", second["snapshot"])
            s.recover_release("synthetic:r2")
            changed = event(replace(row(), value=4), 2, h0)
            with self.assertRaises(ValueError):
                s.ingest(changed)
            s.ingest(changed, allow_closed_revision=True)
            third = s.advance(10, expected_parent=second["snapshot"])
            s.reserve("synthetic:r3", third["snapshot"])
            s.recover_release("synthetic:r3")
            s.ingest(event(row(1, 2, ORGS[1], 5), 2, h1, "tombstone"), allow_closed_revision=True)
            fourth = s.advance(12, expected_parent=third["snapshot"])
            s.reserve("synthetic:r4", fourth["snapshot"])
            self.assertEqual(s.recover_release("synthetic:r4")["sum_mm"], 70)
            self.assertEqual(s.status()["observer_ledger"]["events"], 4)
            self.assertTrue(s.status()["observer_ledger"]["unprotected_transcript"])
            self.assertEqual(s.status()["observer_ledger"]["epsilon"], "0")
            s.close()
            s = Stream(path, expected_head=fourth["snapshot"])
            self.assertEqual(s.status()["reserved_release_count"], 4)
            self.assertEqual(s.recover_release("synthetic:r1"), first)
            self.assertEqual(s.status()["observer_ledger"]["events"], 4)
            s.close()

    def test_replay_conflict_watermark_stale_release_and_unavailable_proof(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            s = Stream(Path(d) / "state.sqlite", create=True)
            e = event(row())
            s.ingest(e)
            self.assertIn("retry", s.ingest(e))
            changed = event(replace(row(), value=2))
            with self.assertRaises(ValueError):
                s.ingest(changed)
            r = s.advance(10, expected_parent="genesis")
            with self.assertRaises(ValueError):
                s.advance(9, expected_parent=r["snapshot"])
            with self.assertRaises(ValueError):
                s.reserve("synthetic:wrong", "genesis")
            with self.assertRaises(ValueError):
                s.reserve("synthetic:proof", r["snapshot"], require_real_proof=True)
            with self.assertRaises(ValueError):
                s.reserve("synthetic:dp", r["snapshot"], require_dp=True)
            s.reserve("synthetic:release", r["snapshot"])
            with self.assertRaises(ValueError):
                s.reserve("synthetic:second", r["snapshot"])
            with self.assertRaises(ValueError):
                s.advance(11, expected_parent=r["snapshot"])
            s.recover_release("synthetic:release")
            s.close()

    def test_active_or_cached_output_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.sqlite"
            s = Stream(p, create=True)
            s.ingest(event(row()))
            r = s.advance(10, expected_parent="genesis")
            s.reserve("synthetic:out", r["snapshot"])
            s.recover_release("synthetic:out")
            bad = dict(r)
            bad["sum_mm"] = 999
            s.db.execute("UPDATE releases SET body=?", (json.dumps(bad),))
            with self.assertRaises(ValueError):
                s.recover_release("synthetic:out")
            active = asdict(row())
            active["value"] = 2
            s.db.execute("UPDATE active SET body=?", (json.dumps(active),))
            s.close()
            with self.assertRaises(ValueError):
                Stream(p)

    def test_concurrent_transport_retries_have_one_accepted_effect(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.sqlite"
            s = Stream(path, create=True)
            s.close()
            barrier = threading.Barrier(2)

            def deliver() -> str:
                state = Stream(path)
                try:
                    barrier.wait(timeout=5)
                    return state.ingest(event(row()))
                finally:
                    state.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: deliver(), range(2)))
            self.assertEqual(sum("retry" in x for x in results), 1)
            s = Stream(path)
            self.assertEqual(s.status()["accepted_event_versions"], 1)
            s.close()

    def test_process_crashes_before_after_commit_and_between_outbox_stores(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.sqlite"
            s = Stream(p, create=True)
            s.close()
            program = """import os,sys,json
from pathlib import Path
from python.fzkml_math.streaming_data import Stream
s=Stream(Path(sys.argv[1]));case=sys.argv[2];e=json.loads(sys.argv[3])
if case=='before':s.ingest(e,fault=lambda:os._exit(91))
elif case=='after':s.ingest(e,after_commit=lambda:os._exit(92))
else:s.recover_release('synthetic:out',fault_after_journal=lambda:os._exit(93))
"""

            def crash(case: str) -> int:
                return subprocess.run(
                    [sys.executable, "-c", program, str(p), case, json.dumps(event(row()))],
                    cwd=ROOT,
                    env={**os.environ, "PYTHONPATH": ".:src"},
                    timeout=10,
                ).returncode

            self.assertEqual(crash("before"), 91)
            s = Stream(p)
            self.assertEqual(s.status()["accepted_event_versions"], 0)
            s.close()
            self.assertEqual(crash("after"), 92)
            s = Stream(p)
            self.assertEqual(s.status()["accepted_event_versions"], 1)
            self.assertIn("retry", s.ingest(event(row())))
            r = s.advance(10, expected_parent="genesis")
            s.reserve("synthetic:out", r["snapshot"])
            s.close()
            self.assertEqual(crash("ledger"), 93)
            s = Stream(p)
            self.assertEqual(s.status()["accounted_release_count"], 0)
            self.assertEqual(s.status()["observer_ledger"]["events"], 1)
            self.assertEqual(s.recover_release("synthetic:out"), r)
            self.assertEqual(s.status()["observer_ledger"]["events"], 1)
            s.close()


if __name__ == "__main__":
    unittest.main()
