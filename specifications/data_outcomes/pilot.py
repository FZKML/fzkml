"""Original synthetic industrial-shaped smoke pilot; no paper experiment reproduced."""

from __future__ import annotations

from fractions import Fraction as F
from typing import Any, TypedDict

from specifications.data_outcomes.design import check_split
from specifications.data_outcomes.reference import Row, digest, require, solve, statistics


class Observation(TypedDict):
    id: str
    entity: str
    duplicate_cluster: str
    site: int
    machine: int
    time: int
    x: F
    y: F


def run_pilot(available: bool = True, rights_approved: bool = True) -> dict[str, Any]:
    require(available and rights_approved, "pilot-source-unavailable-or-rights-denied")
    records: list[Observation] = []
    for site in range(6):
        for machine in range(12):
            for time in range(4):
                entity = f"synthetic-site{site}:machine{machine}"
                x = F(machine % 5 + time) + F(site, 10)
                y = 2 * x + 1 + F(2 * (site % 2) - 1, 10)
                records.append(
                    {
                        "id": f"{entity}:t{time}",
                        "entity": entity,
                        "duplicate_cluster": f"{entity}:t{time}",
                        "site": site,
                        "machine": machine,
                        "time": time,
                        "x": x,
                        "y": y,
                    }
                )
    train = [r for r in records if r["site"] < 4 and r["machine"] < 8 and r["time"] < 3]
    temporal = [r for r in records if r["site"] < 4 and r["machine"] >= 8 and r["time"] == 3]
    sites = [r for r in records if r["site"] >= 4 and r["time"] == 3]
    check_split(train, temporal, False)
    check_split(train, sites, True)
    matrix, rhs = statistics(tuple(Row(r["id"], (F(1), r["x"]), r["y"]) for r in train), F(1))
    weights = solve(matrix, rhs)
    mean = sum((r["y"] for r in train), F(0)) / len(train)

    def evaluate(rows: list[Observation]) -> dict[str, Any]:
        errors = [(weights[0] + weights[1] * r["x"] - r["y"]) ** 2 for r in rows]
        baseline = [(mean - r["y"]) ** 2 for r in rows]
        per_site = {
            site: [errors[i] for i, r in enumerate(rows) if r["site"] == site]
            for site in {r["site"] for r in rows}
        }
        return {
            "records": len(rows),
            "unique_entities": len({r["entity"] for r in rows}),
            "mse": str(sum(errors, F(0)) / len(rows)),
            "mean_baseline_mse": str(sum(baseline, F(0)) / len(rows)),
            "worst_site_mse": str(max(sum(v, F(0)) / len(v) for v in per_site.values())),
        }

    return {
        "kind": "original-synthetic-adaptation",
        "status": "completed-reference-pilot",
        "model": "two-feature-rational-ridge-fixed-sum-lambda1",
        "dataset_sha256": digest([{**r, "x": str(r["x"]), "y": str(r["y"])} for r in records]),
        "split_sha256": digest(
            {
                "train": [r["id"] for r in train],
                "temporal": [r["id"] for r in temporal],
                "sites": [r["id"] for r in sites],
            }
        ),
        "model_sha256": digest(
            {
                "weights": [str(v) for v in weights],
                "lambda": "1",
                "objective": "fixed-sum-ridge-half-scaled-v1",
            }
        ),
        "preprocessor_sha256": digest({"kind": "none", "feature_generator": "original-v1"}),
        "data_origin": "original-public-synthetic-Apache-2.0",
        "train_records": len(train),
        "train_unique_entities": len({r["entity"] for r in train}),
        "train_sites": 4,
        "source_holdout_sites": 2,
        "weights": [str(v) for v in weights],
        "temporal_holdout": evaluate(temporal),
        "site_holdout": evaluate(sites),
        "uncertainty": "not-estimated-single-deterministic-fixture",
        "paper_replication": False,
        "FZKML_gain": "not-tested",
        "genuine_proofs_verified": 0,
    }
