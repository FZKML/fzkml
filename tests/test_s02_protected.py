"""M4 reference contracts, adversarial cases, and optional external conformance."""

from __future__ import annotations

import copy
import itertools
import json
import socket
import struct
import tempfile
import threading
import unittest
from fractions import Fraction as F
from pathlib import Path

from jsonschema import Draft202012Validator

from python.fzkml_math.collaborative import (
    Relay,
    inspect_multiplier,
    public_transcript,
    sections,
    verify,
)
from python.fzkml_math.pq_audit import audit
from python.fzkml_math.progress import (
    Frontier,
    capacity,
    client_admission,
    miss_probability,
    pipeline,
)
from python.fzkml_math.protected import (
    Paillier,
    coalition_reconstruct,
    exact_product,
    probable_prime,
    replicated_views,
    require_prover_profile,
    sumcheck_counterexample,
)

ROOT = Path(__file__).resolve().parents[1]


class FrontierTests(unittest.TestCase):
    def test_completed_and_descendant_checks_do_not_certify_missing_ancestor(self) -> None:
        f = Frontier()
        f.add("a", "genesis", 1, f.context)
        f.add("b", "a", 2, f.context)
        f.evidence("b", "a", f.context, True)
        self.assertNotIn("b", f.certified)
        with self.assertRaises(ValueError):
            f.release("b", require_real_proof=False)
        f.evidence("a", "genesis", f.context, True)
        self.assertEqual(f.release("b", require_real_proof=False)["assurance"], "simulation-only")
        with self.assertRaisesRegex(ValueError, "real-release"):
            f.release("b")

    def test_stale_context_parent_duplicate_and_conflicting_release(self) -> None:
        f = Frontier()
        for name in ("a", "fork"):
            f.add(name, "genesis", 1, f.context)
            f.evidence(name, "genesis", f.context, True)
        f.release("a", require_real_proof=False)
        with self.assertRaises(ValueError):
            f.release("fork", require_real_proof=False)
        with self.assertRaises(ValueError):
            f.add("a", "genesis", 1, f.context)
        with self.assertRaises(ValueError):
            f.add("wrong", "a", 3, f.context)
        with self.assertRaises(ValueError):
            f.evidence("a", "wrong", f.context, True)
        with self.assertRaises(ValueError):
            f.evidence("a", "genesis", "other-session", True)
        with self.assertRaises(ValueError):
            f.evidence("a", "genesis", f.context, False)

    def test_withheld_data_and_rollback_preserve_accepted_state(self) -> None:
        f = Frontier()
        f.add("a", "genesis", 1, f.context)
        f.evidence("a", "genesis", f.context, True)
        f.release("a", require_real_proof=False)
        f.add("b", "a", 2, f.context)
        f.add("c", "b", 3, f.context)
        f.evidence("c", "b", f.context, True)
        f.evidence("b", "a", f.context, False)
        self.assertEqual(f.invalid, {"b", "c"})
        self.assertEqual(f.released, "a")
        with self.assertRaises(ValueError):
            f.release("c", require_real_proof=False)
        with self.assertRaises(ValueError):
            f.evidence("c", "b", f.context, True)
        f.add("retry", "a", 2, f.context)
        f.available.remove("retry")
        f.evidence("retry", "a", f.context, True)
        with self.assertRaises(ValueError):
            f.release("retry", require_real_proof=False)

    def test_staleness_is_not_reinterpreted_as_fresh(self) -> None:
        self.assertEqual(client_admission(1, 4, 2, True), "stale")
        self.assertEqual(client_admission(2, 4, 2, True), "admitted")
        self.assertEqual(client_admission(4, 4, 2, False), "unavailable")
        with self.assertRaises(ValueError):
            client_admission(5, 4, 2, True)

    def test_pipeline_is_bounded_monotone_and_counts_rework(self) -> None:
        for w in (1, 2, 4, 8):
            clean = pipeline(w)
            bad = pipeline(w, fail_height=4)
            self.assertLessEqual(clean["maximum_speculative_depth"], w)
            self.assertLessEqual(bad["maximum_speculative_depth"], w)
            self.assertEqual(clean["rollback_count"], 0)
            self.assertEqual(bad["rollback_count"], 1)
            self.assertGreater(
                F(bad["time_to_certified_quality_seconds"]),
                F(clean["time_to_certified_quality_seconds"]),
            )
            self.assertGreater(bad["issued_proof_jobs"], clean["issued_proof_jobs"])
            for result in (clean, bad):
                heights = [r["certified_height"] for r in result["trace"]]
                self.assertEqual(sorted(heights), heights)
                self.assertEqual(heights[-1], 16)
                self.assertLessEqual(F(result["certified_per_second"]), F(4))


class ExactSamplingTests(unittest.TestCase):
    def test_without_replacement_matches_independent_enumeration(self) -> None:
        for total in range(1, 9):
            for bad in range(total + 1):
                for k in range(total + 1):
                    choices = list(itertools.combinations(range(total), k))
                    good = sum(all(i >= bad for i in subset) for subset in choices)
                    self.assertEqual(miss_probability(total, bad, k), F(good, len(choices)))
        for values in ((0, 0, 0), (3, 4, 1), (3, 1, 4), (True, 0, 0)):
            with self.assertRaises(ValueError):
                miss_probability(*values)

    def test_source_inspected_capacity_and_sampling_examples(self) -> None:
        f = json.loads((ROOT / "tests/vectors/book/progress-v1.json").read_text())
        self.assertEqual(f["source"]["observed_edition"], "MS20261125")
        v = f["vectors"][0]
        inputs = v["verified_inputs"]
        self.assertEqual(
            capacity(
                F(inputs["compute_seconds"]), F(inputs["prove_worker_seconds"]), inputs["workers"]
            ),
            F(v["expected"]["certified_rate_upper_bound"]),
        )
        sample = f["vectors"][1]
        inputs = sample["verified_inputs"]
        total, k = inputs["total"], inputs["samples"]
        self.assertEqual(
            1 - miss_probability(total, inputs["isolated_bad"], k),
            F(sample["expected"]["isolated_detection"]),
        )
        exact = miss_probability(total, inputs["fraction_bad_count"], k)
        upper = (1 - F(inputs["fraction_bad_count"], total)) ** k
        self.assertLessEqual(exact, upper)
        self.assertLess(abs(float(upper) - 0.0000432), 0.00000005)
        self.assertEqual(miss_probability(10, 3, 8), 0)
        self.assertEqual(miss_probability(10, 0, 10), 1)
        with self.assertRaises(ValueError):
            capacity(F(0), F(2), 8)


class ProtectedArithmeticTests(unittest.TestCase):
    def test_exact_product_and_HE_signed_negatives_and_malleability(self) -> None:
        # Test-only small public key. Never used for timings or confidentiality.
        n = 17 * 19
        lam = 144
        key = Paillier(n, lam, pow(lam, -1, n))
        for a, b in ((3, 11), (-3, 11), (3, -11), (-3, -11), (0, 3), (32, -1)):
            encrypted = key.encrypt(a)
            self.assertEqual(key.decrypt(key.multiply_public(encrypted, b)), exact_product(a, b))
        c = key.encrypt(33)
        tampered = c * (n + 1) % (n * n)
        self.assertEqual(key.decrypt(tampered), 34)
        for malformed in (0, n, n * n, True, -1):
            with self.assertRaises(ValueError):
                key.decrypt(malformed)
        for a, b in ((33, 1), (1, True)):
            with self.assertRaises(ValueError):
                exact_product(a, b)
        with self.assertRaises(ValueError):
            Paillier.generate(32)
        for value in (1, 9, 341, 561):
            self.assertFalse(probable_prime(value))
        self.assertTrue(probable_prime(101))

    def test_rep3_single_view_has_every_secret_and_two_views_reconstruct(self) -> None:
        for secret in range(17):
            views = replicated_views(secret)
            self.assertEqual(coalition_reconstruct(views[:2]), secret)
            # Fix a possible party0 view; every secret has exactly one missing third share.
            for x, y in itertools.product(range(17), repeat=2):
                third = (secret - x - y) % 17
                self.assertEqual((x + y + third) % 17, secret)
        require_prover_profile(1, True, 3)
        for args in ((2, True, 3), (1, False, 3), (1, True, 2)):
            with self.assertRaises(ValueError):
                require_prover_profile(*args)

    def test_sumcheck_local_consistency_is_insufficient(self) -> None:
        negative = sumcheck_counterexample(3, 8)
        rounds = negative["rounds"]
        assert isinstance(rounds, list)
        self.assertTrue(all(r["local_consistency"] for r in rounds))
        self.assertEqual(negative["terminal_claim"], 1)
        self.assertTrue(negative["unbound_verifier_accepts"])
        self.assertFalse(negative["bound_terminal_check_accepts"])

    def test_output_itself_can_reveal_the_other_operand(self) -> None:
        # Crypto hides no information already implied by the authorized function.
        self.assertEqual(exact_product(3, 11) // 3, 11)
        self.assertEqual(exact_product(3, 11) // 11, 3)


class InventoryTests(unittest.TestCase):
    def test_complete_inventory_and_non_PQ_component_mutations(self) -> None:
        data = json.loads((ROOT / "experiments/s02-protected/pq-inventory-v1.json").read_text())
        for configuration in data["configurations"]:
            self.assertFalse(audit(configuration)["full_stack_pq_supported"])
            claimed = copy.deepcopy(configuration)
            claimed["claimed_full_stack_pq"] = True
            with self.assertRaisesRegex(ValueError, "unsupported-full-stack"):
                audit(claimed)
            for role in range(7):
                missing = copy.deepcopy(configuration)
                missing["primitives"].pop(role)
                with self.assertRaises(ValueError):
                    audit(missing)
        # Synthetic metadata checker case, not an approval of an actual PQ system.
        hypothetical = copy.deepcopy(data["configurations"][0])
        hypothetical["independent_review"] = True
        hypothetical["claimed_full_stack_pq"] = True
        for row in hypothetical["primitives"]:
            row["quantum_status"] = "candidate"
        self.assertTrue(audit(hypothetical)["full_stack_pq_supported"])
        hypothetical["primitives"][0]["quantum_status"] = "vulnerable"
        with self.assertRaises(ValueError):
            audit(hypothetical)
        mixed = data["configurations"][-1]
        self.assertEqual(mixed["primitives"][2]["algorithm"], "ML-DSA proposal only")
        self.assertIn("proof:vulnerable", audit(mixed)["blockers"])
        self.assertFalse(audit(mixed)["performance_eligible"])

    def test_local_schema_rejects_false_attestation_and_PQ_claims(self) -> None:
        schema = json.loads((ROOT / "schemas/s02-protected-run-1.0.0.json").read_text())
        Draft202012Validator.check_schema(schema)
        self.assertFalse(
            Draft202012Validator(schema["properties"]["pq_inventory_audit"]).is_valid(
                [{"full_stack_pq_supported": True}]
            )
        )
        att = schema["properties"]["matched_workload"]["properties"]["attested_execution"]
        self.assertFalse(
            Draft202012Validator(att).is_valid({"status": "verified", "reason": "mock"})
        )
        self.assertFalse(Draft202012Validator(schema).is_valid({"private_witness": [3, 11]}))

    def test_public_export_rejects_injected_witness_field(self) -> None:
        # Structural exporter test only: dummy coordinates are not a valid proof.
        proof: dict[str, object] = {
            "pi_a": [],
            "pi_b": [],
            "pi_c": [],
            "protocol": "groth16",
            "curve": "bn128",
        }
        with tempfile.TemporaryDirectory() as d:
            p, output = Path(d) / "proof.json", Path(d) / "public.json"
            p.write_text(json.dumps(proof))
            output.write_text('["33"]')
            self.assertFalse(public_transcript(p, output)["witness_columns_exported"])
            proof["private_witness"] = [3, 11]
            p.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, "undeclared-public-proof-fields"):
                public_transcript(p, output)

    def test_circom_container_rejects_duplicate_and_trailing_sections(self) -> None:
        minimal = b"wtns" + struct.pack("<II", 2, 1) + struct.pack("<IQ", 1, 0)
        self.assertEqual(sections(minimal, b"wtns"), {1: b""})
        for raw in (minimal + b"X", minimal[:-1], b"fake" + minimal[4:]):
            with self.assertRaises((ValueError, struct.error)):
                sections(raw, b"wtns")

    def test_relay_counts_payload_and_does_not_invent_round_trips(self) -> None:
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()

        def echo() -> None:
            c, _ = server.accept()
            with c:
                data = c.recv(100)
                c.sendall(data)

        worker = threading.Thread(target=echo)
        worker.start()
        relay = Relay(server.getsockname()[1])
        try:
            with socket.create_connection(("127.0.0.1", relay.port), timeout=2) as client:
                client.sendall(b"known-payload")
                self.assertEqual(client.recv(100), b"known-payload")
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(relay.bytes, 2 * len(b"known-payload"))
            self.assertEqual(relay.connections, 1)
        finally:
            relay.close()
            server.close()

    @unittest.skipUnless(
        (ROOT / ".tools/co-runtime/co-circom").exists(),
        "external runtime not installed; no real collaborative proof claimed",
    )
    def test_external_relation_and_reference_proof_when_available(self) -> None:
        source = ROOT / ".tools/co-snarks"
        observed = inspect_multiplier(source)
        self.assertEqual(observed["witness"], [1, 33, 3, 11])
        proof = source / "test_vectors/Groth16/bn254/multiplier2/circom.proof"
        self.assertTrue(
            verify(
                ROOT / ".tools/co-runtime/co-circom",
                proof,
                source / "test_vectors/Groth16/bn254/multiplier2/verification_key.json",
                proof.parent / "public.json",
            )
        )
        with tempfile.TemporaryDirectory() as d:
            wrong = Path(d) / "public.json"
            wrong.write_text('["34"]')
            self.assertFalse(
                verify(
                    ROOT / ".tools/co-runtime/co-circom",
                    proof,
                    source / "test_vectors/Groth16/bn254/multiplier2/verification_key.json",
                    wrong,
                )
            )


if __name__ == "__main__":
    unittest.main()
