"""Deterministic original synthetic counterexamples, with evidence class labels."""

from __future__ import annotations

from dataclasses import asdict, replace
from fractions import Fraction
from typing import Any

from .geometric import Geometric
from .histories import Certificate, State, TrustedLedger, assess, digest
from .integer import FixedSlotQuery, loss, property_valid, rounded, training_relation, training_step
from .visibility import Witness, public_bytes, public_execution


def genesis() -> State:
    return State(
        "synthetic",
        0,
        digest("policy", "m0"),
        digest("relation", "m0"),
        (8, 4),
        (),
        0,
        0,
        ("C0", "C1", "C2", "C3"),
        "ready",
        (),
        digest("fzkml-release-ledger-v1", ()),
    )


def successor(parent: State, model: tuple[int, int], release: str) -> State:
    ids = (*parent.release_ids, release)
    return replace(
        parent,
        sequence=parent.sequence + 1,
        model=model,
        model_version=parent.model_version + 1,
        phase="released",
        release_ids=ids,
        release_ledger_digest=digest("fzkml-release-ledger-v1", ids),
    )


def certificate(parent: State, child: State) -> Certificate:
    return Certificate(
        parent.sid,
        child.sequence,
        parent.root,
        child.root,
        parent.relation_digest,
        digest("synthetic-ideal-verifier-evidence", [parent.root, child.root]),
    )


def histories() -> dict[str, Any]:
    start = genesis()
    left = successor(start, (6, 5), "left")
    right = successor(start, (7, 5), "right")
    later = successor(right, (5, 5), "later")
    a, b, c = certificate(start, left), certificate(start, right), certificate(right, later)
    certificates = {item.root: item for item in [a, b, c]}

    def ideal_verifier(item: Certificate) -> bool:
        # An explicit assumption for this counterexample, never a production verifier.
        return item.root in certificates

    def evaluate(
        states: tuple[State, ...],
        ids: tuple[str, ...],
        ledger: TrustedLedger | None = None,
        available: dict[str, Certificate] | None = None,
    ) -> dict[str, Any]:
        return asdict(
            assess(
                start,
                states,
                ids,
                certificates if available is None else available,
                ideal_verifier,
                ledger,
            )
        )

    ledger = TrustedLedger(start)
    return {
        "evidence_class": "synthetic-counterexample",
        "verifier": "ideal-oracle-assumption",
        "two_histories": [evaluate((start, left), (a.root,)), evaluate((start, right), (b.root,))],
        "disconnected_valid_edges": evaluate((start, left, later), (a.root, c.root)),
        "withheld_certificate": evaluate((start, left), (a.root,), available={}),
        "trusted_selection": [
            evaluate((start, left), (a.root,), ledger),
            evaluate((start, right), (b.root,), ledger),
        ],
        "limitations": [
            "No real cryptographic verifier, durable storage or consensus.",
            "Local validity never establishes unique globally available history.",
        ],
    }


def harmful_updates() -> dict[str, Any]:
    model, features, honest_label = (0, 0), (16, 0), 16
    good = training_step(model, features, honest_label)
    harmful = training_step(model, features, -honest_label)
    return {
        "evidence_class": "exact-synthetic-counterexample",
        "initial_model": model,
        "updates": [good, harmful],
        "norm_squared": [sum(x * x for x in d) for d in [good, harmful]],
        "property_valid": [property_valid(d) for d in [good, harmful]],
        "clean_evaluation_loss": [str(loss(d, features, honest_label)) for d in [good, harmful]],
        "initial_clean_loss": str(loss(model, features, honest_label)),
        "training_relation": {
            "honest_data": training_relation(model, features, honest_label, good),
            "poisoned_data": training_relation(model, features, -honest_label, harmful),
            "incorrect_execution": training_relation(model, features, -honest_label, good),
        },
        "real_full_training_proof": "not-run",
        "validity": "Both norm checks pass; harmful training correctly executes.",
        "statistical_utility": "Opposing updates have clean squared loss 0 versus 4, initially 1.",
        "byzantine_tolerance": "No Byzantine tolerance is demonstrated.",
        "source_authenticity": "No data/source authenticity is established.",
        "limitations": [
            "One deterministic one-step synthetic example, not a population result.",
            "A real full-training proof/circuit remains a dependency on #33/#46.",
        ],
    }


def sensitivity() -> dict[str, Any]:
    query = FixedSlotQuery()
    zero = ((0, 0),) * 4
    add = ((48, 48), *zero[1:])
    positive = ((48, 48), *zero[1:])
    negative = ((-48, -48), *zero[1:])
    return {
        "query": "fixed-four-slot-half-up-clipped-v1",
        "privacy_unit": "one public contribution slot",
        "add_remove_bound_l1": query.sensitivity("add-remove-zero-slot"),
        "replace_bound_l1": query.sensitivity("replace-slot"),
        "add_remove_extremizer": [query.evaluate(zero), query.evaluate(add)],
        "replacement_extremizer": [query.evaluate(positive), query.evaluate(negative)],
        "private_denominator_counterexample": {
            "before": rounded(48, 1),
            "after": rounded(48 - 48, 2),
            "change": 48,
            "incorrect_bound_using_new_count": 24,
        },
        "person_four_slot_bound_l1": query.sensitivity("replace-slot", 4),
        "limitations": [
            "Zero-slot adjacency does not hide the public roster or abort behavior.",
            "Counts/weights/denominator are public and fixed, not data dependent.",
            "No record/person claim without a verified contribution-multiplicity bound.",
        ],
    }


def mechanism() -> dict[str, Any]:
    reference = Geometric(1, 2, 5)
    weights = reference.weights()
    denominator = sum(weights) ** 2
    pmf_from_sampler = [
        Fraction(sum(weights[i] * weights[(i - r) % 5] for i in range(5)), denominator)
        for r in range(5)
    ]
    default = Geometric()
    epsilon, delta = default.account(FixedSlotQuery(), "replace-slot")
    return {
        "mechanism": "rational-folded-discrete-laplace-v1",
        "reference": "CKS2020-Lemma29",
        "default_parameters": {"a": 255, "b": 256, "modulus": 257},
        "epsilon_upper_rational": str(epsilon),
        "delta": str(delta),
        "exact_small_reference_pmf": [str(p) for p in reference.pmf()],
        "sampler_mass_matches_reference": tuple(pmf_from_sampler) == reference.pmf(),
        "normalization": str(sum(reference.pmf())),
        "floating_point_error": 0,
        "support": "All 257 residues; centered decode -128..128. No truncated noise tails.",
        "limitations": [
            "Conditional mathematical analysis; no machine-checked proof or security audit.",
            "Trusted central sampler; independent client noise shares are unsupported.",
            "Output-only privacy; timing, memory, failures and clean server view excluded.",
            "Distribution checks are conformance evidence, never a DP proof.",
        ],
    }


def visibility() -> dict[str, Any]:
    witness = Witness((16, 0), -16, "FZKML_FORBIDDEN_SECRET_SYNTHETIC_WITNESS", b"synthetic-coins")
    event = public_execution(witness, lambda w: training_step((0, 0), w.features, w.label))
    encoded = public_bytes(event)
    return {
        "public_event": event,
        "synthetic_canary_absent": witness.private_notes.encode() not in encoded,
        "surfaces": ["declared-public-json", "CLI-stdout", "CLI-stderr"],
        "limitations": [
            "Tests cover declared reference surfaces, not arbitrary worker/subprocess logs.",
            "Source test fixtures intentionally contain synthetic canary definitions.",
            "No protection from remote provers that receive plaintext witnesses.",
        ],
    }


def run_all() -> dict[str, Any]:
    return {
        "version": 1,
        "histories": histories(),
        "visibility": visibility(),
        "harmful_updates": harmful_updates(),
        "sensitivity": sensitivity(),
        "mechanism": mechanism(),
    }
