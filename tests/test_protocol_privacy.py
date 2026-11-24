"""Exact reference/counterexample tests; no real cryptographic or DP deployment."""

from __future__ import annotations

import contextlib
import copy
import io
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import cast
from unittest.mock import patch

from fzkml_ci.validate import ROOT, Invalid, load, validate_bundle, validate_claims
from fzkml_protocol.__main__ import shared_results
from fzkml_protocol.experiments import certificate, genesis, harmful_updates, run_all, successor
from fzkml_protocol.geometric import Geometric, tuple_centered
from fzkml_protocol.histories import Certificate, TrustedLedger, assess
from fzkml_protocol.integer import (
    FixedSlotQuery,
    property_valid,
    rounded,
    training_relation,
    training_step,
)
from fzkml_protocol.visibility import Witness, public_bytes, public_execution, validate_observers


def fixed_uniform(rank: int) -> Callable[[int], int]:
    return lambda _: rank


def sequence_uniform(ranks: list[int]) -> Callable[[int], int]:
    iterator = iter(ranks)
    return lambda _: next(iterator)


class HistoryTests(unittest.TestCase):
    def test_disconnected_valid_edges_fail(self) -> None:
        start = genesis()
        left, right = successor(start, (1, 1), "left"), successor(start, (2, 2), "right")
        later = successor(right, (3, 3), "later")
        a, b = certificate(start, left), certificate(right, later)
        result = assess(
            start, (start, left, later), (a.root, b.root), {a.root: a, b.root: b}, lambda c: True
        )
        self.assertEqual(result.local_validity, "invalid")
        self.assertFalse(result.connected)

    def test_two_valid_histories_and_ledger_selection(self) -> None:
        start = genesis()
        left, right = successor(start, (1, 1), "left"), successor(start, (2, 2), "right")
        a, b = certificate(start, left), certificate(start, right)
        for child, cert in [(left, a), (right, b)]:
            result = assess(start, (start, child), (cert.root,), {cert.root: cert}, lambda c: True)
            self.assertEqual(result.local_validity, "valid")
            self.assertEqual(result.global_consistency, "unresolved")
        ledger = TrustedLedger(start)
        self.assertEqual(
            assess(
                start, (start, left), (a.root,), {a.root: a}, lambda c: True, ledger
            ).global_consistency,
            "ledger-selected",
        )
        conflict = assess(start, (start, right), (b.root,), {b.root: b}, lambda c: True, ledger)
        self.assertEqual(conflict.global_consistency, "conflict")
        self.assertEqual(conflict.local_validity, "valid")
        # Losing durable selection state permits the conflicting history again.
        self.assertEqual(
            assess(
                start, (start, right), (b.root,), {b.root: b}, lambda c: True, TrustedLedger(start)
            ).global_consistency,
            "ledger-selected",
        )

    def test_withheld_certificate_stalls_without_validity(self) -> None:
        start = genesis()
        child = successor(start, (1, 1), "one")
        cert = certificate(start, child)
        result = assess(start, (start, child), (cert.root,), {}, lambda c: True)
        self.assertEqual(result.local_validity, "unavailable")
        self.assertEqual(result.liveness, "stalled")
        self.assertEqual(result.certificate_availability, "withheld")

    def test_complete_state_context_and_order_bound(self) -> None:
        start = genesis()
        child = successor(start, (1, 1), "one")
        cert = certificate(start, child)
        mutations = [
            replace(child, model=(2, 2)),
            replace(child, key_epoch=1),
            replace(child, policy_digest="1" * 64),
            replace(child, relation_digest="2" * 64),
            replace(child, sid="other"),
            replace(child, model_version=3),
        ]
        for changed in mutations:
            result = assess(
                start, (start, changed), (cert.root,), {cert.root: cert}, lambda c: True
            )
            self.assertEqual(result.local_validity, "invalid")
        result = assess(start, (child, start), (cert.root,), {cert.root: cert}, lambda c: True)
        self.assertEqual(result.reason, "untrusted-genesis")
        with self.assertRaises(ValueError):
            replace(child, optimizer=(1,))
        with self.assertRaises(ValueError):
            replace(child, release_ledger_digest="0" * 64)

    def test_real_verifier_must_be_supplied_and_failure_is_closed(self) -> None:
        start = genesis()
        child = successor(start, (1, 1), "one")
        cert = certificate(start, child)
        self.assertEqual(
            assess(
                start, (start, child), (cert.root,), {cert.root: cert}, lambda c: False
            ).local_validity,
            "invalid",
        )

        def malformed(_: Certificate) -> bool:
            return cast(bool, "false")  # Deliberately malformed adapter response.

        self.assertEqual(
            assess(
                start, (start, child), (cert.root,), {cert.root: cert}, malformed
            ).local_validity,
            "invalid",
        )

        def failing(_: Certificate) -> bool:
            raise ValueError("private verifier detail")

        self.assertEqual(
            assess(start, (start, child), (cert.root,), {cert.root: cert}, failing).reason,
            "verifier-failure",
        )

    def test_concurrent_first_writer_and_replay(self) -> None:
        start = genesis()
        ledger = TrustedLedger(start)
        children = [successor(start, (i, i), f"release{i}") for i in range(2)]

        def choose(i: int) -> str:
            child = children[i]
            cert = certificate(start, child)
            return assess(
                start, (start, child), (cert.root,), {cert.root: cert}, lambda c: True, ledger
            ).global_consistency

        with ThreadPoolExecutor(2) as workers:
            outcomes = list(workers.map(choose, [0, 1]))
        self.assertEqual(sorted(outcomes), ["conflict", "ledger-selected"])
        winner = outcomes.index("ledger-selected")
        self.assertEqual(choose(winner), "ledger-selected")

    def test_conflicting_path_is_atomic(self) -> None:
        start = genesis()
        first = successor(start, (1, 1), "one")
        left, right = successor(first, (2, 2), "left"), successor(first, (3, 3), "right")
        ledger = TrustedLedger(start)
        self.assertTrue(
            ledger.select(start.root, [(start.root, first.root), (first.root, left.root)])
        )
        self.assertFalse(
            ledger.select(start.root, [(start.root, first.root), (first.root, right.root)])
        )
        self.assertTrue(
            ledger.select(start.root, [(start.root, first.root), (first.root, left.root)])
        )
        self.assertFalse(ledger.select(start.root, [(left.root, right.root)]))


class VisibilityTests(unittest.TestCase):
    def test_canary_success_failure_and_declared_surfaces(self) -> None:
        secret = "FZKML_FORBIDDEN_SECRET_PRIVATE_CANARY"
        witness = Witness((16, 0), -16, secret, secret.encode())
        stdout, stderr = io.StringIO(), io.StringIO()

        def failing(w: Witness) -> tuple[int, int]:
            raise ValueError(w.private_notes + repr(w.commitment_coins))

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            good = public_execution(witness, lambda w: training_step((0, 0), w.features, w.label))
            bad = public_execution(witness, failing)
            observations = run_all()
        self.assertEqual(good["status"], "accepted")
        self.assertEqual(bad["status"], "failed")
        for value in [
            repr(witness),
            stdout.getvalue(),
            stderr.getvalue(),
            public_bytes([good, bad, observations]).decode(),
        ]:
            self.assertNotIn(secret, value)
        # Negative control: the existing CI-10 validator detects a declared raw canary leak.
        with self.assertRaises(Invalid):
            public_bytes({"log": secret})

    def test_all_external_roles_require_assumptions(self) -> None:
        inventory = load(ROOT / "experiments" / "protocol" / "observers.json")
        validate_observers(inventory)
        for role in inventory["roles"]:
            changed = copy.deepcopy(inventory)
            changed["roles"][role]["assumption"] = ""
            with self.assertRaises(ValueError):
                validate_observers(changed)
        self.assertNotEqual(
            inventory["roles"]["outsourced-prover"]["witness_view"],
            inventory["roles"]["collaborative-prover"]["witness_view"],
        )


class IntegerTests(unittest.TestCase):
    def test_m0_golden_and_negative_ties(self) -> None:
        self.assertEqual(training_step((8, 4), (16, -8), 4), (-2, 1))
        self.assertEqual(rounded(-8, 16), 0)
        self.assertEqual(rounded(-24, 16), -1)
        self.assertEqual(rounded(8, 16), 1)
        with self.assertRaises(ValueError):
            training_step((17, 4), (16, -8), 4)

    def test_valid_harmful_and_incorrect_execution(self) -> None:
        result = harmful_updates()
        self.assertEqual(result["norm_squared"], [256, 256])
        self.assertEqual(result["property_valid"], [True, True])
        self.assertEqual(result["clean_evaluation_loss"], ["0", "4"])
        self.assertEqual(result["initial_clean_loss"], "1")
        self.assertTrue(result["training_relation"]["poisoned_data"])
        self.assertFalse(result["training_relation"]["incorrect_execution"])
        self.assertEqual(result["real_full_training_proof"], "not-run")
        self.assertFalse(training_relation((0, 0), (16, 0), -16, (16, 0)))
        self.assertFalse(property_valid((49, 0)))

    def test_exact_sensitivity_extremizers_and_private_denominator(self) -> None:
        query = FixedSlotQuery()
        zero = ((0, 0),) * 4
        add, sub = ((48, 48), *zero[1:]), ((-48, -48), *zero[1:])
        a, b, z = query.evaluate(add), query.evaluate(sub), query.evaluate(zero)
        self.assertEqual(sum(abs(x - y) for x, y in zip(a, z, strict=True)), 24)
        self.assertEqual(sum(abs(x - y) for x, y in zip(a, b, strict=True)), 48)
        self.assertEqual(query.sensitivity("replace-slot", 4), 192)
        self.assertGreater(abs(rounded(48, 1) - rounded(0, 2)), 48 // 2)

    def test_all_rounding_residues_obey_bound(self) -> None:
        # Every possible clipped coordinate and all 4 rounding phases, not random samples.
        for unchanged_sum in range(-3 * 48, 3 * 48 + 1):
            for changed in range(-48, 49):
                a = rounded(unchanged_sum + changed, 4)
                b = rounded(unchanged_sum, 4)
                self.assertLessEqual(abs(a - b), 12)
                c = rounded(unchanged_sum - 48, 4)
                self.assertLessEqual(abs(a - c), 24)

    def test_clipping_order_and_unsupported_configurations(self) -> None:
        query = FixedSlotQuery()
        self.assertEqual(query.evaluate(((100, -100), (0, 0), (0, 0), (0, 0))), (12, -12))
        for values in [(), ((0, 0),) * 3, ((True, 0),) * 4, ((2**31, 0),) * 4]:
            with self.assertRaises(ValueError):
                query.evaluate(values)
        for adjacency in ["person", "private-denominator", "join"]:
            with self.assertRaises(ValueError):
                query.sensitivity(adjacency)
        with self.assertRaises(ValueError):
            query.sensitivity("replace-slot", 5)
        with self.assertRaises(ValueError):
            FixedSlotQuery(slots=3)


class MechanismTests(unittest.TestCase):
    def test_folded_mass_and_exact_privacy_ratios(self) -> None:
        for mechanism in [Geometric(1, 2, 5), Geometric(2, 3, 7), Geometric()]:
            weights = mechanism.weights()
            total = sum(weights)
            sampler_mass = tuple(
                Fraction(
                    sum(
                        weights[i] * weights[(i - r) % mechanism.modulus]
                        for i in range(mechanism.modulus)
                    ),
                    total**2,
                )
                for r in range(mechanism.modulus)
            )
            self.assertEqual(sampler_mass, mechanism.pmf())
            self.assertEqual(sum(sampler_mass), 1)
            self.assertTrue(all(p > 0 for p in sampler_mass))
            p = Fraction(mechanism.numerator, mechanism.denominator)
            # All outputs for a unit shift; larger L1 shifts compose algebraically.
            for r, mass in enumerate(sampler_mass):
                self.assertLessEqual(mass / sampler_mass[(r - 1) % mechanism.modulus], 1 / p)

    def test_inverse_cdf_boundaries_and_pair_mass_enumeration(self) -> None:
        mechanism = Geometric(1, 2, 5)
        weights = mechanism.weights()
        histogram = [0] * 5
        for rank in range(sum(weights)):
            histogram[mechanism._geometric_residue(fixed_uniform(rank))] += 1
        self.assertEqual(tuple(histogram), weights)
        pairs = [0] * 5
        for a in range(sum(weights)):
            for b in range(sum(weights)):
                pairs[mechanism._noise(sequence_uniform([a, b]))] += 1
        self.assertEqual(
            tuple(Fraction(count, sum(weights) ** 2) for count in pairs), mechanism.pmf()
        )

    def test_accountant_and_modular_support(self) -> None:
        mechanism = Geometric()
        self.assertEqual(
            mechanism.account(FixedSlotQuery(), "replace-slot"), (Fraction(16, 85), Fraction(0))
        )
        self.assertEqual(
            mechanism.account(FixedSlotQuery(), "add-remove-zero-slot"),
            (Fraction(8, 85), Fraction(0)),
        )
        self.assertEqual(
            mechanism.account(FixedSlotQuery(), "replace-slot", 2, 3)[0], Fraction(96, 85)
        )
        self.assertEqual(tuple_centered((129, -129), 257), (-128, 128))
        with patch("fzkml_protocol.geometric.secrets.randbelow", return_value=0) as uniform:
            self.assertEqual(mechanism.release(((48, 48),) * 4, FixedSlotQuery()), (48, 48))
            self.assertEqual(uniform.call_count, 4)
        with self.assertRaises(ValueError):
            mechanism.account(FixedSlotQuery(), "replace-slot", releases=0)

    def test_no_silent_parameter_rounding_or_rng_fallback(self) -> None:
        for a, b, m in [(0, 2, 5), (2, 2, 5), (1, 257, 5), (1, 2, 4), (1, 2, 259), (True, 2, 5)]:
            with self.assertRaises(ValueError):
                Geometric(a, b, m)
        with self.assertRaises(ValueError):
            Geometric(1, 2, 5)._noise(lambda n: n)
        with patch(
            "fzkml_protocol.geometric.secrets.randbelow", side_effect=OSError("entropy unavailable")
        ):
            with self.assertRaises(OSError):
                Geometric().sample()


class EvidenceTests(unittest.TestCase):
    def test_scoped_registry_uses_shared_schema(self) -> None:
        registry = load(ROOT / "claims" / "protocol-privacy.json")
        self.assertEqual(validate_claims(registry)["total"], 5)
        bundle = shared_results(run_all(), 1)  # Explicit synthetic metadata validation fixture.
        validate_bundle(bundle, registry)
        self.assertTrue(
            all(row["scenario"]["security_mode"] == "synthetic-test" for row in bundle["results"])
        )
        with self.assertRaises(ValueError):
            shared_results(run_all(), 0)

    def test_observation_snapshot_and_cli_canary(self) -> None:
        expected = load(ROOT / "experiments" / "protocol" / "observations.json")
        self.assertEqual(public_bytes(run_all()), public_bytes(expected))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence"
            result = subprocess.run(
                [sys.executable, "-m", "fzkml_protocol", "--check", "--output", str(path)],
                cwd=ROOT,
                env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = result.stdout + result.stderr + (path / "observations.json").read_text()
            self.assertNotIn("FZKML_FORBIDDEN_SECRET", output)
            if (path / "public-report").exists():
                for artifact in (path / "public-report").iterdir():
                    self.assertNotIn("FZKML_FORBIDDEN_SECRET", artifact.read_text())


if __name__ == "__main__":
    unittest.main()
