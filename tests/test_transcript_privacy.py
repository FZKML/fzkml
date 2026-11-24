from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

from fzkml_transcript.algebra import (
    check_patterns,
    conditional_covariance,
    gaussian_rdp,
    matrix,
    positive_semidefinite,
    scalar_cube_maximum,
    squared_separation,
    trace_gram,
)
from fzkml_transcript.entropy import (
    EntropyPolicy,
    EntropyUseRegistry,
    half_normal_delta_floor,
    one_shot_public_filter,
    require_residual_noise,
    select_nonnegative,
    xor_counts,
)
from fzkml_transcript.ledger import (
    LedgerPolicy,
    MechanismContract,
    Observation,
    ReferenceAccountant,
)
from fzkml_transcript.sampling import (
    PopulationTrace,
    amplification_status,
    dependent_variance,
    weighted_moments,
)


def entropy_policy() -> EntropyPolicy:
    return EntropyPolicy("synthetic:independent-secret-source", True, True, True, True, True)


def ledger_policy() -> LedgerPolicy:
    contract = MechanismContract(
        "synthetic:declared-mechanism",
        F(1),
        F(1, 1000),
        "synthetic:theorem-interface",
        "synthetic:entropy-interface",
        "synthetic-conformance-only",
        entropy_policy(),
    )
    return LedgerPolicy(
        "synthetic:server",
        "synthetic-record",
        "1" * 64,
        ("synthetic:c0", "synthetic:c1"),
        F(2),
        F(1, 100),
        (contract,),
    )


def release(index: int) -> Observation:
    return Observation(
        f"synthetic:event-{index}",
        f"synthetic:output-{index}",
        "aggregate",
        "accounted-release",
        f"{index:064x}",
        "synthetic:declared-finite-contract",
        "synthetic:declared-mechanism",
        f"synthetic:application-{index}",
    )


class GeometryTests(unittest.TestCase):
    def test_scalar_vector_gap_from_source(self) -> None:
        precision = matrix([[F(8, 5) * int(i == j) - F(1, 2) for j in range(3)] for i in range(3)])
        gram = matrix([[1 if i == j else F(-1, 2) for j in range(3)] for i in range(3)])
        self.assertTrue(positive_semidefinite(gram))
        self.assertEqual(scalar_cube_maximum(precision), F(43, 10))
        self.assertEqual(trace_gram(precision, gram), F(24, 5))
        # The Gram matrix of 120-degree planar vectors is exact, without sqrt rounding.
        self.assertTrue(all(sum(row) == 0 for row in gram))

    def test_singular_support_is_not_zero_cost(self) -> None:
        covariance = matrix([[1, 1], [1, 1]])
        self.assertIsNone(squared_separation(covariance, [1, 0]))
        self.assertEqual(squared_separation(covariance, [1, 1]), 1)
        self.assertEqual(squared_separation(covariance, [0, 0]), 0)
        self.assertEqual(gaussian_rdp(covariance, [1, 1], F(3)), F(3, 2))

    def test_correlation_direction_matters(self) -> None:
        covariance = matrix([[1, F(1, 2)], [F(1, 2), 1]])
        self.assertEqual(squared_separation(covariance, [1, 0]), F(4, 3))
        self.assertEqual(squared_separation(covariance, [1, 1]), F(4, 3))
        self.assertEqual(squared_separation(covariance, [1, -1]), 4)

    def test_coalition_conditioning(self) -> None:
        self.assertEqual(conditional_covariance(matrix([[2, 1], [1, 1]]), [0], [1]), matrix([[1]]))
        with self.assertRaisesRegex(ValueError, "invertible"):
            conditional_covariance(matrix([[1, 0], [0, 0]]), [0], [1])
        with self.assertRaisesRegex(ValueError, "joint covariance"):
            conditional_covariance(matrix([[1, 2], [2, 1]]), [0], [1])

    def test_exact_psd_has_no_eigenvalue_tolerance(self) -> None:
        self.assertTrue(positive_semidefinite(matrix([[F(1, 10**80), 0], [0, 0]])))
        self.assertFalse(positive_semidefinite(matrix([[-F(1, 10**80), 0], [0, 0]])))
        self.assertFalse(positive_semidefinite(matrix([[0, 1], [1, 0]])))
        with self.assertRaisesRegex(ValueError, "exact"):
            matrix([[0.1]])  # type: ignore[list-item]

    def test_all_permitted_recovery_patterns_required(self) -> None:
        patterns = {"both": matrix([[2]]), "one-survivor": matrix([[1]])}
        self.assertEqual(
            check_patterns(patterns, frozenset(patterns), [[1]], F(1)),
            {"both": F(1, 2), "one-survivor": F(1)},
        )
        with self.assertRaisesRegex(ValueError, "complete explicit"):
            check_patterns({"both": patterns["both"]}, frozenset(patterns), [[1]], F(1))
        with self.assertRaisesRegex(ValueError, "outside residual support"):
            check_patterns({"none": matrix([[0]])}, frozenset({"none"}), [[1]], F(1))


class EntropyTests(unittest.TestCase):
    def test_release_context_and_entropy_reuse_are_bound(self) -> None:
        registry = EntropyUseRegistry(entropy_policy())
        registry.bind("release-1", "context-1", "entropy-1")
        registry.bind("release-1", "context-1", "entropy-1")
        with self.assertRaisesRegex(ValueError, "change context or entropy"):
            registry.bind("release-1", "context-1", "entropy-2")
        with self.assertRaisesRegex(ValueError, "reused"):
            registry.bind("release-2", "context-2", "entropy-1")

    def test_half_normal_retry_counterexample(self) -> None:
        self.assertAlmostEqual(half_normal_delta_floor(0.1), 0.07965567455405796, places=14)
        self.assertEqual(select_nonnegative((-0.3, -0.1, 0.2)), (0.2, 3))
        self.assertIsNone(one_shot_public_filter(-0.3, 0))
        with self.assertRaisesRegex(ValueError, "exhausted"):
            select_nonnegative((-0.3, -0.1))

    def test_fixed_xor_is_uniform_but_adaptive_xor_is_not(self) -> None:
        for adversarial in range(16):
            self.assertEqual(xor_counts(4, adversarial), dict.fromkeys(range(16), 1))
        self.assertEqual({h ^ h for h in range(16)}, {0})

    def test_coalition_dropout_and_direction_threshold(self) -> None:
        loadings = {"a": matrix([[1], [0]]), "b": matrix([[0], [1]])}
        shifts = ((F(1), F(0)), (F(0), F(1)))
        covariance = require_residual_noise(
            entropy_policy(), loadings, frozenset(loadings), frozenset(), shifts, F(1)
        )
        self.assertEqual(covariance, matrix([[1, 0], [0, 1]]))
        with self.assertRaisesRegex(ValueError, "insufficient"):
            require_residual_noise(
                entropy_policy(), loadings, frozenset(loadings), frozenset({"a"}), shifts, F(1)
            )
        with self.assertRaisesRegex(ValueError, "insufficient"):
            require_residual_noise(
                entropy_policy(),
                {"a": loadings["a"], "b": loadings["a"]},
                frozenset(loadings),
                frozenset(),
                shifts,
                F(1),
            )

    def test_grinding_reuse_and_missing_secrecy_block_claim(self) -> None:
        for policy in (
            replace(entropy_policy(), hidden_from_observer=False),
            replace(entropy_policy(), retry_rule="retry-until-favorable"),
            replace(entropy_policy(), adversary_fixed_before_honest_seed=False),
            replace(entropy_policy(), inclusion_independent_of_noise=False),
        ):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                policy.require_available()


class SamplingTests(unittest.TestCase):
    def test_source_inverse_inclusion_example(self) -> None:
        vectors = {"a": [1], "b": [-1]}
        weights = {"a": F(1, 2), "b": F(1, 2)}
        law = {frozenset({"a"}): F(9, 10), frozenset({"a", "b"}): F(1, 10)}
        mean, variance = weighted_moments(vectors, weights, law)
        self.assertEqual((mean, variance), ((F(0),), F(9, 4)))
        self.assertEqual(dependent_variance(vectors, weights, law), variance)
        wrong_mean, _ = weighted_moments(
            vectors, weights, law, declared_probabilities={"a": 1, "b": 1}
        )
        self.assertEqual(wrong_mean, (F(9, 20),))
        # The source's observed unweighted mean is 1 on {a}, 0 on {a,b}.
        self.assertEqual(F(9, 10) * 1 + F(1, 10) * 0, F(9, 10))

    def test_dependent_inclusions_with_equal_marginals(self) -> None:
        vectors = {"a": [1], "b": [-1]}
        weights = {"a": F(1, 2), "b": F(1, 2)}
        independent = {
            frozenset(): F(1, 4),
            frozenset({"a"}): F(1, 4),
            frozenset({"b"}): F(1, 4),
            frozenset({"a", "b"}): F(1, 4),
        }
        exclusive = {frozenset({"a"}): F(1, 2), frozenset({"b"}): F(1, 2)}
        together = {frozenset(): F(1, 2), frozenset({"a", "b"}): F(1, 2)}
        for law, expected in ((independent, F(1, 2)), (exclusive, F(1)), (together, F(0))):
            mean, variance = weighted_moments(vectors, weights, law)
            self.assertEqual(mean, (F(0),))
            self.assertEqual(variance, expected)
            self.assertEqual(dependent_variance(vectors, weights, law), expected)

    def test_two_client_objective_bias(self) -> None:
        theta = F(1)
        target = (theta + theta - 2) / 2
        effective = F(9, 10) * theta + F(1, 10) * (theta - 2)
        self.assertEqual(target, 0)
        self.assertEqual(effective, F(4, 5))
        self.assertEqual(F(9, 10) * F(1, 5) + F(1, 10) * (F(1, 5) - 2), 0)

    def test_resource_coverage_and_no_amplification(self) -> None:
        trace = PopulationTrace(
            frozenset({"a", "b"}),
            frozenset({"a", "b"}),
            frozenset({"a"}),
            frozenset({"a"}),
            frozenset({"a"}),
            {"a": "fast", "b": "slow"},
        )
        self.assertEqual(trace.summary()["invited"], {"fast": 1, "slow": 1})
        self.assertEqual(trace.summary()["released"], {"fast": 1, "slow": 0})
        with self.assertRaisesRegex(ValueError, "not nested"):
            replace(trace, accepted=frozenset({"b"})).summary()
        self.assertEqual(amplification_status(fixed_cohort=True), "no-amplification")
        with self.assertRaisesRegex(ValueError, "separate sampler"):
            amplification_status(fixed_cohort=False, theorem_reference="unmatched-theorem")

    def test_zero_inclusion_with_positive_target_weight_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive final inclusion"):
            weighted_moments(
                {"a": [1], "b": [-1]}, {"a": F(1, 2), "b": F(1, 2)}, {frozenset({"a"}): F(1)}
            )


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.jsonl"
        self.policy = ledger_policy()
        self.ledger = ReferenceAccountant(self.path, self.policy, create=True)

    def test_budget_and_exact_retransmission(self) -> None:
        receipt = self.ledger.authorize(release(1))
        self.assertEqual(self.ledger.authorize(release(1)), receipt)
        self.ledger.authorize(release(2))
        self.assertEqual(self.ledger.summary()["epsilon"], "2")
        with self.assertRaisesRegex(ValueError, "exhausted"):
            self.ledger.authorize(release(3))
        self.assertEqual(self.ledger.summary()["events"], 2)

    def test_unavailable_honest_entropy_blocks_contract(self) -> None:
        contract = replace(
            self.policy.mechanisms[0],
            entropy_policy=replace(entropy_policy(), hidden_from_observer=False),
        )
        with self.assertRaisesRegex(ValueError, "unavailable"):
            replace(self.policy, mechanisms=(contract,)).record()

    def test_delta_exhaustion_and_precomputation_public_abort(self) -> None:
        contract = replace(self.policy.mechanisms[0], epsilon=F(0), delta=F(1, 5))
        policy = replace(self.policy, delta_limit=F(1, 4), mechanisms=(contract,))
        ledger = ReferenceAccountant(self.path.with_name("delta-ledger"), policy, create=True)
        public_abort = Observation(
            "synthetic:before-data",
            "synthetic:static-abort",
            "failure",
            "post-processing",
            "c" * 64,
            "public-context-only",
            no_new_protected_access=True,
        )
        ledger.authorize(public_abort)
        self.assertEqual(ledger.summary()["delta"], "0")
        ledger.authorize(release(1))
        with self.assertRaisesRegex(ValueError, "exhausted"):
            ledger.authorize(release(2))
        self.assertEqual(ledger.summary()["epsilon"], "0")
        self.assertEqual(ledger.summary()["delta"], "1/5")

    def test_failure_retry_recovery_keeps_cost(self) -> None:
        self.ledger.authorize(replace(release(1), kind="failure"))
        recovered = ReferenceAccountant(self.path, self.policy)
        self.assertEqual(recovered.summary()["epsilon"], "1")
        redelivery = Observation(
            "synthetic:recover",
            "synthetic:recover-output",
            "recovery",
            "post-processing",
            release(1).payload_digest,
            "identical-redelivery",
            parents=(release(1).output_id,),
            no_new_protected_access=True,
        )
        recovered.authorize(redelivery)
        recovered.authorize(release(2))
        self.assertEqual(recovered.summary()["epsilon"], "2")
        with self.assertRaisesRegex(ValueError, "exhausted"):
            recovered.authorize(release(3))

    def test_conflicting_retry_and_unavailable_dependency(self) -> None:
        self.ledger.authorize(release(1))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.ledger.authorize(replace(release(1), payload_digest="f" * 64))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.ledger.authorize(replace(release(2), mechanism_id="synthetic:unknown"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_classification_and_public_input_boundary(self) -> None:
        self.ledger.authorize(release(1))
        proof = Observation(
            "synthetic:proof",
            "synthetic:proof-output",
            "proof-public-input",
            "computationally-hidden",
            "a" * 64,
            "synthetic:ZK-simulation-assumption",
            parents=(release(1).output_id,),
            no_new_protected_access=True,
            crypto_kappa=str(F(1, 2**80)),
        )
        self.ledger.authorize(proof)
        self.assertEqual(self.ledger.summary()["delta"], "1/1000")
        self.assertEqual(self.ledger.summary()["separate_crypto_kappa"], str(F(1, 2**80)))
        with self.assertRaisesRegex(ValueError, "classify all public inputs"):
            self.ledger.authorize(replace(proof, event_id="synthetic:bad-proof", parents=()))
        leak = Observation(
            "synthetic:participation",
            "synthetic:membership-bit",
            "participation",
            "explicitly-unprotected",
            "b" * 64,
            "synthetic:unprotected-private-bit",
        )
        self.ledger.authorize(leak)
        self.assertTrue(self.ledger.summary()["unprotected_transcript"])
        with self.assertRaisesRegex(ValueError, "unprotected transcript"):
            self.ledger.authorize(release(2))

    def test_new_data_is_not_post_processing(self) -> None:
        self.ledger.authorize(release(1))
        event = Observation(
            "synthetic:evaluation",
            "synthetic:metric",
            "evaluation",
            "post-processing",
            "d" * 64,
            "synthetic:fresh-private-evaluation",
            parents=(release(1).output_id,),
        )
        with self.assertRaisesRegex(ValueError, "cannot read new protected"):
            self.ledger.authorize(event)
        with self.assertRaisesRegex(ValueError, "redelivery payload differs"):
            self.ledger.authorize(
                replace(event, no_new_protected_access=True, justification="identical-redelivery")
            )

    def test_concurrent_authorizations_do_not_overspend(self) -> None:
        def attempt(index: int) -> bool:
            try:
                ReferenceAccountant(self.path, self.policy).authorize(release(index))
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(attempt, range(1, 5)))
        self.assertEqual(sum(outcomes), 2)
        self.assertEqual(self.ledger.summary()["epsilon"], "2")

    def test_recovery_refuses_torn_missing_or_rolled_back_state(self) -> None:
        header = self.path.read_bytes()
        receipt = self.ledger.authorize(release(1))
        self.path.write_bytes(header)
        with self.assertRaisesRegex(ValueError, "rollback"):
            ReferenceAccountant(self.path, self.policy, expected_root=receipt)
        with self.assertRaisesRegex(ValueError, "rollback"):
            self.ledger.summary()
        self.path.write_bytes(header + b'{"incomplete":')
        with self.assertRaisesRegex(ValueError, "malformed"):
            ReferenceAccountant(self.path, self.policy)
        with self.assertRaises(FileNotFoundError):
            ReferenceAccountant(self.path.with_name("missing"), self.policy)

    def test_changed_observer_or_cohort_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "policy/observer mismatch"):
            ReferenceAccountant(self.path, replace(self.policy, observer="synthetic:other-server"))
        with self.assertRaises(FileExistsError):
            ReferenceAccountant(self.path, self.policy, create=True)


if __name__ == "__main__":
    unittest.main()
