"""Original deterministic synthetic records; no external inputs or training."""

import argparse
import hashlib
import json
from pathlib import Path


def canonical_bytes(value):
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def generate(seed=20261124):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be a public uint32")
    records = []
    for site in range(4):
        for entity in range(12):
            for visit, event_time in enumerate((2, 8)):
                token = f"fzkml-synthetic-v1:{seed}:{site}:{entity}:{visit}"
                entropy = hashlib.sha256(token.encode("ascii")).digest()
                features = [entropy[0] % 33 - 16, entropy[1] % 33 - 16]
                target = (features[0] - features[1]) // 4
                # Fixed hand-checkable case, independent of any private source.
                if (site, entity, visit) == (0, 0, 0):
                    features, target = [16, -8], 4
                group = f"synthetic:s{site}-e{entity}-v{visit}"
                record = {
                    "record_id": group + "-a",
                    "entity_id": f"synthetic:s{site}-e{entity}",
                    "source_id": f"synthetic:source-{site}",
                    "duplicate_group": group,
                    "event_time": event_time,
                    "label_available_at": event_time + 1,
                    "features": features,
                    "target": target,
                    "label_quality": "synthetic-exact",
                }
                records.append(record)
                if (entity, visit) == (0, 0):
                    records.append(dict(record, record_id=group + "-b"))
    return {
        "schema_version": "synthetic-records-1.0",
        "seed": seed,
        "source_inputs": [],
        "scale": 16,
        "records": sorted(records, key=lambda r: r["record_id"]),
    }


def default_entities():
    train = {f"synthetic:s{s}-e{e}" for s in range(4) for e in range(8)}
    evaluation = {f"synthetic:s{s}-e{e}" for s in range(4) for e in range(8, 12)}
    return train, evaluation


def split(records, train_entities, evaluation_entities, cutoff=4, evaluation_end=12):
    """Unseen-entity, future-time split; retain exclusion reasons."""
    if train_entities & evaluation_entities:
        raise ValueError("training/evaluation entity policy overlaps")
    if cutoff >= evaluation_end:
        raise ValueError("invalid temporal window")
    if len({r["record_id"] for r in records}) != len(records):
        raise ValueError("duplicate record ID")
    groups = {}
    result = {"train": [], "evaluation": [], "excluded": []}
    for row in sorted(records, key=lambda r: r["record_id"]):
        content = {k: v for k, v in row.items() if k != "record_id"}
        group = row["duplicate_group"]
        if group in groups:
            if groups[group] != content:
                raise ValueError("inconsistent duplicate-group payload")
            reason = "duplicate"
        else:
            groups[group] = content
            entity = row["entity_id"]
            time = row["event_time"]
            available = row["label_available_at"]
            if available < time:
                raise ValueError("label predates record")
            if entity in train_entities and time <= cutoff and available <= cutoff:
                result["train"].append(row)
                continue
            if (
                entity in evaluation_entities
                and cutoff < time <= evaluation_end
                and available <= evaluation_end
            ):
                result["evaluation"].append(row)
                continue
            reason = "entity-or-temporal-policy"
        result["excluded"].append({"record_id": row["record_id"], "reason": reason})
    for field in ("entity_id", "duplicate_group"):
        if {r[field] for r in result["train"]} & {r[field] for r in result["evaluation"]}:
            raise ValueError("split leakage: " + field)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261124)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_bytes(canonical_bytes(generate(args.seed)))


if __name__ == "__main__":
    main()
