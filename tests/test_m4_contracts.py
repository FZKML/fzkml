"""Adversarial semantics for M4 references; no genuine-proof or privacy claims."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from jsonschema import Draft202012Validator, ValidationError

from specifications.m4.reference import (
    AdmissionReference,
    certificate,
    check_certificate_structure,
    check_checkpoint,
    check_external,
    check_topology,
    checkpoint,
    context,
    subgroup_counterexample,
    word,
)
from specifications.m4.run import ROOT, memory_case, observations, validate_observations


class M4ContractsTests(unittest.TestCase):
    def test_memory_strategies_bind_one_statement(self) -> None:
        rows = [memory_case(64, mode) for mode in ("ram", "recompute", "external-memory")]
        self.assertEqual(len({r["statement_sha256"] for r in rows}), 1)
        self.assertEqual(len({r["witness_sha256"] for r in rows}), 1)
        self.assertEqual(rows[1]["compute_generated_records"], 128)
        self.assertEqual(rows[2]["application_file_read_bytes"], 512)
        self.assertEqual(rows[2]["application_file_write_bytes"], 512)
        self.assertTrue(all(r["proof_outcome"] == "not-run" for r in rows))
        with self.assertRaises(ValueError):
            memory_case(1000000, "ram")

    def test_checkpoint_replay_context_and_truncation(self) -> None:
        bound = {"n": 64, "statement": "original", "transcript_position": 32}
        payload = b"".join(word(i) for i in range(32))
        record = checkpoint(bound, 1, 32, payload)
        check_checkpoint(record, bound, 1, 32, payload)
        for bad_context, seq, data in (
            (bound, 2, payload),
            (dict(bound, statement="other"), 1, payload),
            (bound, 1, payload[:-1]),
        ):
            with self.assertRaises(ValueError):
                check_checkpoint(record, bad_context, seq, 32, data)
        with tempfile.TemporaryFile() as external:
            external.write(payload)
            external.truncate(len(payload) - 1)
            external.seek(0)
            with self.assertRaisesRegex(ValueError, "truncated"):
                check_external(external.read(), 32, hashlib.sha256(payload).hexdigest())

    def test_queue_bounds_and_work_reservation(self) -> None:
        q = AdmissionReference(workers=1, waiting=2, work=2)
        self.assertEqual(q.submit("one", b"fixture", 2), "queued")
        key, token = q.start()  # type: ignore[misc]
        q.cancel(key)
        self.assertEqual(q.submit("two", b"fixture", 1), "backpressure")
        self.assertEqual(q.reserved, 2)
        self.assertFalse(q.finish(key, token + 1, True))
        self.assertEqual(q.reserved, 2)
        self.assertFalse(q.finish(key, token, True))
        self.assertEqual(q.reserved, 0)
        self.assertEqual(q.submit("two", b"fixture", 1), "queued")
        with self.assertRaises(ValueError):
            q.submit("two", b"changed", 1)
        with self.assertRaises(ValueError):
            q.submit("oversized", b"x" * 257, 1)

    def test_concurrent_duplicate_completion(self) -> None:
        q = AdmissionReference()
        q.submit("same-context-nullifier", b"fixture", 2)
        job = q.start()
        assert job is not None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: q.finish(*job, True), range(32)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(q.accepted), 1)
        self.assertEqual(q.submit("same-context-nullifier", b"fixture", 2), "retransmission")
        self.assertEqual((q.running, q.reserved), (0, 0))

    def test_cancel_finish_linearization(self) -> None:
        for _ in range(16):
            q = AdmissionReference()
            q.submit("one", b"fixture", 1)
            job = q.start()
            assert job is not None
            started_job: tuple[str, int] = job
            barrier = threading.Barrier(2)

            def cancel(q: AdmissionReference = q, barrier: threading.Barrier = barrier) -> str:
                barrier.wait()
                return q.cancel("one")

            def finish(
                q: AdmissionReference = q,
                barrier: threading.Barrier = barrier,
                job: tuple[str, int] = started_job,
            ) -> bool:
                barrier.wait()
                return q.finish(*job, True)

            with ThreadPoolExecutor(max_workers=2) as pool:
                cancelled = pool.submit(cancel)
                completed = pool.submit(finish)
                result = completed.result()
                state = cancelled.result()
            self.assertEqual(len(q.accepted), int(result))
            self.assertEqual(state == "already-committed", result)
            self.assertEqual((q.running, q.reserved), (0, 0))

    def test_invalid_flood_cannot_grow_identity_history(self) -> None:
        q = AdmissionReference(identities=2)
        for key in ("a", "b"):
            q.submit(key, b"invalid-synthetic", 1)
            job = q.start()
            assert job is not None
            q.finish(*job, False)
        self.assertEqual(q.submit("c", b"invalid", 1), "identity-capacity")
        self.assertEqual((len(q.jobs), len(q.accepted)), (2, 0))

    def test_certificate_state_roster_weights_and_availability(self) -> None:
        tree = certificate()
        self.assertEqual(check_certificate_structure(tree, context())["sum"], 10)
        for field in ("parent", "key", "optimizer_state", "accepted_root"):
            bad = copy.deepcopy(tree)
            bad["children"][0]["children"][0]["context"][field] = "wrong"
            with self.assertRaises(ValueError):
                check_certificate_structure(bad, context())
        for mutation in ("weight", "availability", "duplicate", "omitted", "sum", "order"):
            bad = copy.deepcopy(tree)
            leaf = bad["children"][0]["children"][0]
            if mutation == "weight":
                leaf["weight"] = 2
            elif mutation == "availability":
                leaf["available"] = False
            elif mutation == "duplicate":
                bad["children"][0]["children"][1] = copy.deepcopy(leaf)
            elif mutation == "omitted":
                bad["children"].pop()
                bad["sum"], bad["weight"] = 3, 2
            elif mutation == "sum":
                bad["sum"] = 11
            else:
                bad["children"].reverse()
            with self.assertRaises(ValueError):
                check_certificate_structure(bad, context())

    def test_hierarchy_global_cohort_and_views(self) -> None:
        roster = [f"c{i}" for i in range(12)]
        groups = [roster[i : i + 4] for i in (0, 4, 8)]
        views = {f"relay{i}": ["opaque-payloads"] for i in range(3)}
        views["coordinator"] = ["global-release"]
        check_topology(groups, set(roster), views)
        check_topology([roster], set(roster), {"coordinator": ["global-release"]})
        for bad_groups, available, bad_views, corrupt in (
            ([groups[0], groups[1], groups[1]], set(roster), views, 1),
            (groups, set(roster[:-1]), views, 1),
            (groups, set(roster), dict(views, relay0=["subgroup-sum"]), 1),
            (groups, set(roster), views, 2),
        ):
            with self.assertRaises(ValueError):
                check_topology(bad_groups, available, bad_views, corrupt)

    def test_subgroup_outputs_expose_extra_information(self) -> None:
        pair = subgroup_counterexample()
        self.assertEqual(pair["global_left"], pair["global_right"])
        self.assertNotEqual(pair["subgroups_left"], pair["subgroups_right"])
        self.assertEqual(sum(pair["subgroups_left"]), pair["global_left"])
        self.assertEqual(sum(pair["subgroups_right"]), pair["global_right"])

    def test_report_case_and_resource_conservation(self) -> None:
        data = observations()
        validate_observations(data)
        bad = copy.deepcopy(data)
        bad["memory"][0]["statement_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "statement-conservation"):
            validate_observations(bad)
        bad = copy.deepcopy(data)
        bad["memory"][0] = copy.deepcopy(bad["memory"][1])
        with self.assertRaisesRegex(ValueError, "case-coverage"):
            validate_observations(bad)
        bad = copy.deepcopy(data)
        bad["queue"][0]["peak_reserved_work"] = 13
        with self.assertRaisesRegex(ValueError, "queue-bound"):
            validate_observations(bad)

    def test_report_cannot_advertise_genuine_proof_or_ZK(self) -> None:
        data = observations()
        schema = json.loads((ROOT / "specifications/m4/report-schema-v1.json").read_text())
        validator = Draft202012Validator(schema["properties"]["observations"])
        validator.validate(data)
        data["certificate"]["zero_knowledge"] = "proved"
        with self.assertRaises(ValidationError):
            validator.validate(data)
        data = observations()
        data["queue"][0]["genuine_proofs_verified"] = 1
        with self.assertRaises(ValidationError):
            validator.validate(data)


if __name__ == "__main__":
    unittest.main()
