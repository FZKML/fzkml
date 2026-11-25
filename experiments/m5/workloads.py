"""Independent bounded synthetic references. No Rust or model library imports."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from statistics import median
from struct import pack
from time import process_time_ns
from typing import Any

MEDIAN_INPUT = ((1, 0), (1, 1), (0, 1), (1, 0), (-4, 0))
NEURAL_INPUT = (1, 1, -2, 1, 2, 1)


def cosine_gate(update: tuple[int, int], reference: tuple[int, int]) -> bool:
    """Accept cosine >= 1/2 between two nonzero vectors in the radius-four disk."""
    norm = sum(v * v for v in update)
    reference_norm = sum(v * v for v in reference)
    if not (0 < norm <= 16 and 0 < reference_norm <= 16):
        return False
    dot = sum(a * b for a, b in zip(update, reference, strict=True))
    return dot >= 0 and 4 * dot * dot >= norm * reference_norm


def robust() -> dict[str, Any]:
    values = MEDIAN_INPUT
    output = [int(median(axis)) for axis in zip(*values, strict=True)]
    same_sum = ((-2, -2, 0, 2, 2), (-2, -2, -2, 2, 4))
    adjacent = ((-4, -4, -4, 4, 4), (-4, -4, 4, 4, 4))
    # Four good scalar points are within radius 1 and one point is arbitrary.
    # The scalar geometric median is a special case of the Euclidean theorem.
    geometric = [-1, 0, 1, 1, 100]
    alpha = Fraction(1, 5)
    bound = 2 * (1 - alpha) / (1 - 2 * alpha)
    mean_x = sum(x for x, _ in values) / len(values)
    return {
        "expected_output": output,
        "input": values,
        "mean_x": mean_x,
        "outlier_target": "nonpositive coordinate zero",
        "outlier_hits_target_with_mean": mean_x <= 0,
        "outlier_hits_target_with_median": output[0] <= 0,
        "same_sum": [sum(v) for v in same_sum],
        "different_medians": [median(v) for v in same_sum],
        "adjacent_medians": [median(v) for v in adjacent],
        "replace_one_l2_sensitivity": 8,
        "geometric_median_case": {
            "data": geometric,
            "distance": abs(median(geometric)),
            "bound": str(bound),
        },
        "cosine": {
            "same_direction": cosine_gate((1, 1), (2, 0)),
            "opposite_direction": cosine_gate((-1, 0), (2, 0)),
            "zero_update": cosine_gate((0, 0), (2, 0)),
            "zero_reference": cosine_gate((1, 1), (0, 0)),
        },
    }


def score(weights: tuple[int | Fraction, ...], x: int) -> int | Fraction:
    return sum(max(0, a * x) * b for a, b in zip(weights[:2], weights[2:], strict=True))


def neural() -> dict[str, Any]:
    a, b, c, d, x, y = NEURAL_INPUT
    weights = (a, b, c, d)
    initial_score = score(weights, x)
    error = initial_score - y
    derivatives = (c * x * (a * x > 0), d * x * (b * x > 0), max(0, a * x), max(0, b * x))
    gradient = [int(error * grad) for grad in derivatives]
    exact_step = [Fraction(g, 4) for g in gradient]
    updates = tuple(w - round(step) for w, step in zip(weights, exact_step, strict=True))
    rational = tuple(w - step for w, step in zip(weights, exact_step, strict=True))
    heldout = ((-2, -1), (-1, -1), (1, 1))

    def correct(model: tuple[int | Fraction, ...]) -> dict[str, int]:
        return {
            str(label): sum(
                (score(model, value) >= 0) == (label > 0)
                for value, target in heldout
                if target == label
            )
            for label in (-1, 1)
        }

    return {
        "input": NEURAL_INPUT,
        "expected_inference_output": [initial_score],
        "expected_training_output": list(updates),
        "raw_gradient": gradient,
        "step_error": [str(round(step) - step) for step in exact_step],
        "heldout": heldout,
        "class_counts": {"-1": 2, "1": 1},
        "baseline_class_correct": correct(weights),
        "integer_class_correct": correct(updates),
        "rational_class_correct": correct(rational),
        "rational_scores": [str(score(rational, value)) for value, _ in heldout],
        "integer_scores": [score(updates, value) for value, _ in heldout],
    }


def language() -> dict[str, Any]:
    # Frozen two-token bigram head. Train one rank-one signed margin correction.
    logits = {"field": (2, 0), "cloud": (0, 1)}
    feature = {"field": -1, "cloud": 1}
    training = (("tr-a", "field", -1), ("tr-b", "cloud", 1), ("tr-c", "field", -1))
    heldout = (("ev-a", "cloud", 1), ("ev-b", "field", -1), ("ev-c", "cloud", 1))
    assert not {row[0] for row in training} & {row[0] for row in heldout}

    def margin(token: str) -> int:
        up, down = logits[token]
        return up - down

    exact = Fraction(
        sum(feature[token] * (label - margin(token)) for _, token, label in training),
        sum(feature[token] ** 2 for _, token, _ in training),
    )
    adapter = round(exact)

    def predictions(correction: Fraction | int) -> list[bool]:
        return [
            (margin(token) + correction * feature[token] >= 0) == (label > 0)
            for _, token, label in heldout
        ]

    corpus = (
        ("public-1", "public", ("field", "up")),
        ("internal-1", "restricted", ("field", "canary")),
    )

    def retrieve(query: str, role: str) -> tuple[str, ...]:
        return tuple(
            doc
            for doc, access, terms in corpus
            if (access == "public" or role == "internal") and query in terms
        )

    start = process_time_ns()
    repetitions = 2000
    for _ in range(repetitions):
        predictions(adapter)
    cpu_ns = max(1, process_time_ns() - start)
    return {
        "exact_adapter": str(exact),
        "integer_adapter": adapter,
        "numeric_change": str(adapter - exact),
        "baseline_correct": sum(predictions(0)),
        "adapted_correct": sum(predictions(adapter)),
        "exact_correct": sum(predictions(exact)),
        "heldout_predictions": len(heldout),
        "heldout_backbone_logits_per_pass": len(heldout) * 2,
        "training_backbone_logits": len(training) * 2,
        "cpu_time_ns": cpu_ns,
        "timed_token_predictions": repetitions * len(heldout),
        "host_cpu_tokens_per_second": repetitions * len(heldout) * 1e9 / cpu_ns,
        "public_query_matches": retrieve("field", "public"),
        "restricted_query_matches": retrieve("field", "internal"),
        "public_canary_visible": bool(retrieve("canary", "public")),
        "unfiltered_canary_visible": any("canary" in words for _, _, words in corpus),
        "proof_status": "not-run",
        "certified_latency_status": "not-run",
        "gpu_status": "not-run",
    }


def transfer() -> dict[str, Any]:
    preference_train = (("s0", 1), ("s1", 1), ("s2", -1))
    preference_test = (("s3", 1), ("s4", -1), ("s5", 1))
    assert not {user for user, _ in preference_train} & {user for user, _ in preference_test}
    preferred = 1 if sum(v for _, v in preference_train) >= 0 else -1

    # Original toy teacher table. The isolated synthetic canary receives a unique logit.
    teacher = {"field": (4, 3), "cloud": (-4, -3), "canary": (9,)}
    heldout = (("field", 1), ("cloud", -1), ("field", 1))
    clipped = {
        token: [max(-2, min(2, value)) for value in values] for token, values in teacher.items()
    }
    # Release only cohort means for at least two public synthetic records.
    student = {
        token: Fraction(sum(values), len(values))
        for token, values in clipped.items()
        if len(values) >= 2
    }
    generated = [token for token in teacher if max(teacher[token]) >= 8]
    return {
        "preference": {
            "train_clients": len(preference_train),
            "disagreement": sum(v != preferred for _, v in preference_train),
            "heldout_correct": sum(v == preferred for _, v in preference_test),
            "heldout_total": len(preference_test),
        },
        "distillation": {
            "cohorts_released": len(student),
            "heldout_correct": sum(
                (student[token] >= 0) == (label > 0) for token, label in heldout
            ),
            "heldout_total": len(heldout),
            "raw_unique_canary_disclosed": "canary" in teacher,
            "cohort_release_canary_disclosed": "canary" in student,
        },
        "synthetic_generation_memorized_canary": "canary" in generated,
        "privacy_mechanism": "none",
        "proof_status": "not-run",
    }


def correspondence() -> dict[str, Any]:
    left = {"pair-0": 0, "pair-1": 1, "absent": 0}
    right = {"pair-0": 0, "pair-1": 1}
    swapped = dict(zip(right, reversed(tuple(right.values())), strict=True))
    worlds = {
        name: [(value, table[key]) for key, value in left.items() if key in table]
        for name, table in (("equal", right), ("opposite", swapped))
    }
    fitted = {name: tuple(b for _, b in pairs) for name, pairs in worlds.items()}
    marginals = {
        name: [sorted(axis) for axis in zip(*pairs, strict=True)] for name, pairs in worlds.items()
    }
    candidates = ((0, 0), (0, 1), (1, 0), (1, 1))

    def classify(predictor: tuple[int, int], eval_pairs: list[tuple[int, int]]) -> int:
        return sum(predictor[a] == b for a, b in eval_pairs)

    heldout = {name: list(reversed(pairs)) for name, pairs in worlds.items()}
    return {
        "marginals_equal": marginals["equal"] == marginals["opposite"],
        "worlds": worlds,
        "paired_correct": {name: classify(fitted[name], pairs) for name, pairs in heldout.items()},
        "fixed_identity_correct": {
            name: classify((0, 1), pairs) for name, pairs in heldout.items()
        },
        "best_deterministic_unpaired_worst_case_correct": max(
            min(classify(model, pairs) for pairs in worlds.values()) for model in candidates
        ),
        "heldout_per_world": 2,
        "missing_modality_rows_abstained": len(left.keys() - right.keys()),
        "swapped_ids_change_optimum": fitted["equal"] != fitted["opposite"],
        "proof_status": "not-run",
    }


@dataclass(frozen=True)
class Interaction:
    user: str
    silo: str
    item: str


ITEM_EMBEDDING = {"a": (1, 0), "b": (1, 0), "c": (0, 1), "d": (0, 1)}


def authorized_edges(rows: list[Interaction], enrollment: dict[str, str]) -> None:
    if len(rows) != len(set(rows)):
        raise ValueError("duplicate-edge")
    counts = Counter(row.user for row in rows)
    for row in rows:
        if enrollment.get(row.user) != row.silo or row.item not in ITEM_EMBEDDING:
            raise ValueError("unauthorized-edge")
    if any(count > 2 for count in counts.values()):
        raise ValueError("user-contribution-cap")


def graph() -> dict[str, Any]:
    enrollment = {"tr0": "s0", "tr1": "s1", "te0": "s0", "te1": "s1"}
    train = [Interaction("tr0", "s0", "a"), Interaction("tr1", "s1", "c")]
    support = [Interaction("te0", "s0", "a"), Interaction("te1", "s1", "c")]
    truth = [Interaction("te0", "s0", "b"), Interaction("te1", "s1", "d")]
    rows = train + support + truth
    authorized_edges(rows, enrollment)
    assert not {i.user for i in train} & {i.user for i in support + truth}
    accepted = 0
    for query, target in zip(support, truth, strict=True):
        profile = ITEM_EMBEDDING[query.item]
        candidates = (item for item in ITEM_EMBEDDING if item != query.item)
        prediction = min(
            candidates,
            key=lambda item: (
                -sum(a * b for a, b in zip(profile, ITEM_EMBEDDING[item], strict=True)),
                item,
            ),
        )
        accepted += prediction == target.item

    try:
        authorized_edges([*rows, Interaction("te0", "s1", "d")], enrollment)
    except ValueError as error:
        rejected = str(error)
    else:
        raise AssertionError("unauthorized join accepted")
    return {
        "user_level_cap": 2,
        "train_users": len(train),
        "evaluation_users": len(support),
        "top1_hits": accepted,
        "targets": len(truth),
        "unauthorized_join_rejected": rejected,
        "common_item_vocabulary_size": len(ITEM_EMBEDDING),
        "user_adjacency": "replace or remove all edges of one user within the cap",
        "proof_status": "not-run",
    }


def time_series() -> dict[str, Any]:
    # Four observed phases, learned only on the two training entities and times 0..7.
    waveform = (2, 5, 2, -1)
    train = {
        entity: {t: waveform[t % 4] + offset for t in range(8)}
        for entity, offset in (("tr0", -1), ("tr1", 1))
    }
    profile = {
        phase: Fraction(sum(series[t] for series in train.values() for t in (phase, phase + 4)), 4)
        for phase in range(4)
    }
    # Simulated deterministic service costs; actual host CPU time is recorded separately.
    devices = (
        ("north", 0, 3, 64, 4),
        ("south", 1, 5, 64, 5),
        ("mountain", 4, 9, 32, 2),
        ("coast", -2, 2, 64, 4),
    )
    outcomes: dict[str, Any] = {}
    for entity, offset, compute_ms, memory_budget, available_at in devices:
        assert entity not in train
        series = {t: waveform[t % 4] + offset for t in range(8, 18)}
        start = process_time_ns()
        forecasts = {}
        for horizon in (1, 2):
            # Every history window lives wholly in held-out times. Epochs
            # 11 and 15 keep history and target windows disjoint.
            truth_times = [cutoff + horizon for cutoff in (11, 15)]
            errors = [abs(profile[t % 4] - series[t]) for t in truth_times]
            persistence = [abs(series[t - horizon] - series[t]) for t in truth_times]
            forecasts[str(horizon)] = {
                "seasonal_mae": str(sum(errors) / len(errors)),
                "persistence_mae": str(Fraction(sum(persistence), len(persistence))),
            }
        cpu_ns = max(1, process_time_ns() - start)
        # Serialize one bounded forecast and horizon. Nothing is sent.
        payload = pack("<qq", 1, int(profile[12 % 4]))
        # The modeled network delay excludes any transport headers.
        completion = available_at + compute_ms + 4
        completed = memory_budget >= 48
        admitted = completed and completion <= 12
        outcomes[entity] = {
            "forecast_error": forecasts,
            "actual_host_cpu_ns": cpu_ns,
            "modeled_completion_ms": completion if completed else None,
            "modeled_memory_budget_bytes": memory_budget,
            "completed": completed,
            "admitted": admitted,
            "payload_bytes": len(payload) if completed else 0,
        }
    return {
        "training_entities": sorted(train),
        "training_times": [0, 7],
        "test_times": [8, 17],
        "invited": len(outcomes),
        "completed": sum(result["completed"] for result in outcomes.values()),
        "admitted": sum(result["admitted"] for result in outcomes.values()),
        "modeled_deadline_ms": 12,
        "sources": outcomes,
        "proof_status": "not-run",
    }


def observations() -> dict[str, Any]:
    return {
        "89": robust(),
        "90": neural(),
        "91": language(),
        "92": transfer(),
        "93": correspondence(),
        "94": graph(),
        "95": time_series(),
    }
