"""Exact finite-law parameter conformance; no deployed sampler or full-view DP claim."""

from __future__ import annotations

import hashlib
from fractions import Fraction
from pathlib import Path
from typing import Any

from specifications.ci_assurance.rounds import require


def weights(q: int) -> tuple[int, ...]:
    require(type(q) is int and 3 <= q <= 31 and q % 2 == 1, "unsupported-ring")
    return tuple(2 ** (q // 2 - min(z, q - z)) for z in range(q))


def ticket_map(q: int) -> tuple[int, ...]:
    return tuple(z for z, count in enumerate(weights(q)) for _ in range(count))


def clipped_query(values: tuple[int, int, int], q: int = 17) -> int:
    require(all(type(v) is int for v in values), "integer-query-required")
    return sum(max(-1, min(1, v)) for v in values) % q


def check_parameters(config: dict[str, Any], theorem: Path) -> dict[str, Any]:
    expected = {
        "mechanism": "finite-cyclic-geometric-v1",
        "sampler": "ideal-uniform-ticket-map-v1",
        "released_value": "residue-mod-q",
        "q": 17,
        "scale": 1,
        "clipping": 1,
        "cohort": 3,
        "privacy_unit": "client",
        "query": "clipped-three-slot-sum-v1",
        "amplification": "none",
        "amplification_factor": 1,
        "claim_scope": "released-residue-only",
    }
    require(
        set(config)
        == set(expected)
        | {"adjacency", "sensitivity", "theorem_sha256", "releases", "budget_ratio"},
        "parameter-fields",
    )
    require(
        all(type(config[k]) is type(v) and config[k] == v for k, v in expected.items()),
        "mechanism-sampler-query-mismatch",
    )
    require(
        config["theorem_sha256"] == hashlib.sha256(theorem.read_bytes()).hexdigest(),
        "theorem-version-mismatch",
    )
    sensitivity = {"add-remove-fixed-zero-slot": 1, "replace-fixed-slot": 2}.get(
        config["adjacency"]
    )
    if sensitivity is None:
        raise ValueError("adjacency-sensitivity-mismatch")
    require(
        type(config["sensitivity"]) is int and config["sensitivity"] == sensitivity,
        "adjacency-sensitivity-mismatch",
    )
    law = weights(config["q"])
    ratio = max(
        Fraction(law[z], law[(z + shift) % len(law)])
        for z in range(len(law))
        for shift in range(-sensitivity, sensitivity + 1)
    )
    require(
        type(config["budget_ratio"]) is int and 1 <= config["budget_ratio"] <= 16,
        "accountant-budget",
    )
    releases = config["releases"]
    require(isinstance(releases, list) and 1 <= len(releases) <= 8, "release-list-budget")
    seen: dict[str, str] = {}
    noise: set[str] = set()
    composed = Fraction(1)
    fresh = 0
    for item in releases:
        require(
            set(item) == {"id", "noise_instance", "cached_retransmission"}
            and all(
                isinstance(item[k], str) and 1 <= len(item[k]) <= 32
                for k in ("id", "noise_instance")
            )
            and type(item["cached_retransmission"]) is bool,
            "release-binding-shape",
        )
        rid, nid = item["id"], item["noise_instance"]
        if rid in seen:
            require(
                item["cached_retransmission"] and seen[rid] == nid, "unaccounted-repeated-release"
            )
        else:
            require(
                not item["cached_retransmission"] and nid not in noise, "noise-reuse-or-false-cache"
            )
            fresh += 1
            require(fresh <= 2, "reference-release-budget")
            seen[rid] = nid
            noise.add(nid)
            composed *= ratio
        require(composed <= config["budget_ratio"], "composed-privacy-budget-exceeded")
    return {
        "single_release_ratio": str(ratio),
        "composed_ratio": str(composed),
        "fresh_releases": fresh,
        "ticket_count": sum(law),
        "system_dp_established": False,
    }
