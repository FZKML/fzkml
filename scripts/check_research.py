"""Check scientific metadata consistency; never promote evidence strength."""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(records, key):
    result = {r[key]: r for r in records}
    require(len(result) == len(records), "duplicate " + key)
    return result


def local_file(root, relative):
    path = root / relative
    require(
        not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and path.is_file(),
        "invalid local evidence path",
    )
    return path


def validate(root=ROOT, ci_root=None):
    manuscript = read(root, "docs/research/manuscript.json")
    coverage = read(root, "docs/research/coverage.json")
    index = read(root, "docs/research/source-index.json")
    registry = read(root, "claims/registry.json")
    contexts = read(root, "docs/research/claim-context.json")["claims"]
    claims = unique(registry["claims"], "id")
    evidence = unique(registry["evidence"], "id")
    require(set(contexts) == set(claims), "claim context coverage differs")
    require(
        coverage["source_version"] == index["source_version"] == manuscript["source_version"],
        "source version mismatch",
    )
    require(
        manuscript["source_version"] == "text-" + manuscript["text_only_sha256"],
        "source digest/version mismatch",
    )
    require(
        bool(re.fullmatch(r"[a-f0-9]{64}", manuscript["text_only_sha256"])), "invalid text digest"
    )
    require(
        manuscript["observed_revision_id"] and manuscript["tab_id"],
        "missing manuscript revision/tab",
    )
    items = coverage["items"]
    for kind, count in (("chapter", 80), ("exercise", 48)):
        rows = [r for r in items if r["kind"] == kind]
        require(
            len(rows) == count and {r["number"] for r in rows} == set(range(1, count + 1)),
            "incomplete " + kind + " coverage",
        )
    require(len(items) == 128, "unexpected coverage item")
    mapped = set()
    for row in items:
        require(
            row["planned_issues"] and all(type(n) is int and n > 0 for n in row["planned_issues"]),
            "missing planned issue",
        )
        require(
            row["extraction_status"] in {"pending-extraction", "partial", "extracted"},
            "unknown extraction status",
        )
        require(
            row["source_location"]["tab_id"] == manuscript["tab_id"]
            and row["source_location"]["start_utf16"] < row["source_location"]["end_utf16"],
            "invalid source location",
        )
        require(set(row["claim_ids"]) <= claims.keys(), "dangling coverage claim")
        if row["extraction_status"] == "pending-extraction":
            require(not row["claim_ids"], "pending item has extracted claims")
        for cid in row["claim_ids"]:
            if row["kind"] == "chapter":
                require(
                    claims[cid]["source"]["chapter"] == row["number"],
                    "claim mapped to wrong chapter",
                )
            mapped.add(cid)
    require(mapped == claims.keys(), "unmapped registered claim")
    equations = unique(index["equations"], "id")
    require(
        len(equations) + len(index["non_chapter_equations"])
        == manuscript["native_equations"]["count"],
        "native equation count mismatch",
    )
    for eq in list(equations.values()) + index["non_chapter_equations"]:
        require(eq["start_utf16"] < eq["end_utf16"], "invalid equation range")
        require(
            eq["source_review"] == "pending-source-review",
            "native equation review requires an authorized inspected artifact",
        )
    for entry in evidence.values():
        local_file(root, entry["path"].split("::")[0])
    for cid, claim in claims.items():
        context = contexts[cid]
        require(
            re.fullmatch(r"FZK-[A-Z0-9]+-C\d{2}-[A-Z0-9]+-\d{3}", cid), "invalid stable claim ID"
        )
        require(
            cid.split("-")[1] == claim["source"]["edition"]
            and int(cid.split("-")[2][1:]) == claim["source"]["chapter"],
            "claim ID/source mismatch",
        )
        require(
            claim["source"]["version"] == context["source_version"] == manuscript["source_version"],
            "claim version mismatch",
        )
        for field in (
            "observer",
            "privacy_unit",
            "numerical_semantics",
            "required_validation",
            "implementation_status",
            "experiment_status",
        ):
            require(context[field], "missing scientific context: " + field)
        require(set(context["native_equation_ids"]) <= equations.keys(), "dangling source equation")
        require(
            context["source_location"]["heading_id"]
            == claim["source"]["section"].removeprefix("anchor."),
            "claim section/context mismatch",
        )
        require(
            context["specification"]
            in [evidence[e]["path"] for e in claim["evidence_ids"] if e in evidence],
            "unlinked specification",
        )
        require(set(claim["evidence_ids"]) <= evidence.keys(), "dangling claim evidence")
        require(
            claim["statement"] and claim["assumptions"] and claim["limitations"],
            "incomplete scoped claim",
        )
        if context["implementation_status"] == "unimplemented":
            require(
                claim["status"] not in {"implemented", "tested", "replicated"},
                "unimplemented claim promoted",
            )
        if context["experiment_status"] == "not-run":
            require(claim["status"] != "replicated", "unrun claim promoted")
        for attribute, expected in (
            ("formal_proof", "formal-proof"),
            ("independent_review", "independent-review"),
        ):
            for eid in claim[attribute]["artifact_ids"]:
                require(
                    eid in claim["evidence_ids"]
                    and eid in evidence
                    and evidence[eid]["kind"] == expected,
                    "wrong special evidence kind",
                )
        if claim["formal_proof"]["artifact_ids"]:
            require(
                context.get("formal_kernel") and context.get("formal_axioms") is not None,
                "formal artifact needs declared kernel/axioms",
            )
        if claim["status"] == "reviewed":
            require(claim["independent_review"]["artifact_ids"], "review status without review")

    matrix = read(root, "experiments/m0/capabilities.json")
    families = unique(matrix["families"], "family")
    require(len(families) == 12, "model family coverage gap")
    for family in families.values():
        require(set(family["assurance_modes"]) == set(matrix["modes"]), "assurance mode gap")
        require(
            set(family["assurance_modes"].values())
            <= {"planned", "implemented", "unsupported", "excluded"},
            "unknown capability status",
        )
        require(
            set(family["unproved_steps"])
            == {"preprocessing", "feature_extraction", "optimization", "randomness", "lineage"}
            and all(family["unproved_steps"].values()),
            "unproved-step coverage gap",
        )
    require(set(matrix["payload_types"]) == {"full-state", "delta"}, "payload type gap")
    for card in read(root, "experiments/m0/replication-cards.json")["cards"]:
        require(
            card["mode"] in {"reproduction", "replication", "adaptation"},
            "unknown replication mode",
        )
        require(
            set(card["population"])
            == {
                "source_sites",
                "training_clients",
                "held_out_sites",
                "virtual_clients",
                "physical_concurrent_participants",
            },
            "population ambiguity",
        )
        require(
            card["missing"] and card["resources"] and card["code_license"] and card["data_license"],
            "incomplete replication provenance",
        )
        require(
            card["execution_status"] == "not-run", "replication execution requires run artifacts"
        )
    obligations = read(root, "docs/research/security-obligations.json")["obligations"]
    unique(obligations, "id")
    for obligation in obligations:
        require(set(obligation["affected_claim_ids"]) <= claims.keys(), "dangling obligation claim")
        require(
            obligation["status"] == "open" and not obligation["review_artifact_ids"],
            "obligation closure requires independent review evidence",
        )

    cases = read(root, "experiments/m0/reporting-cases.json")
    require(
        {c["status"] for c in cases["cases"]}
        == {"successful", "failed", "not-run", "unsupported", "inconclusive"},
        "reporting outcome gap",
    )
    events = cases["accounting_example"]["events"]
    event_ids = unique(events, "cost_id")
    require(
        all(r["setup_cost_id"] in event_ids for r in cases["accounting_example"]["reuse"]),
        "dangling shared setup cost",
    )

    sys.path.insert(0, str(root / "scripts"))
    from research_fixtures import canonical_bytes, default_entities, generate, split

    payload = (root / "assets/public/synthetic-cross-silo-v1.json").read_bytes()
    require(payload == canonical_bytes(generate()), "fixture generation drift")
    parts = split(json.loads(payload)["records"], *default_entities())
    require(
        len(parts["train"]) == 32
        and len(parts["evaluation"]) == 16
        and len(parts["excluded"]) == 52,
        "fixture split count mismatch",
    )

    manifest_path = root / "docs/research/evidence-manifest.json"
    if manifest_path.exists():
        for artifact in read(root, "docs/research/evidence-manifest.json")["artifacts"]:
            path = local_file(root, artifact["path"])
            require(
                hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"],
                "research artifact checksum drift",
            )

    shared_schema = "not checked: CI-05 checkout not selected"
    if ci_root is None and (root / "schemas/claims-1.0.0.json").exists():
        sys.path.insert(0, str(root / "src"))
        from fzkml_ci.validate import validate_claims

        validate_claims(registry)
        shared_schema = "checked against CI-05 schema and semantic validator"
    if ci_root is not None:
        sys.path.insert(0, str(ci_root / "src"))
        from fzkml_ci.validate import schema

        schema(registry, "claims")
        shared_schema = "checked against CI-05 claims-1.0.0"

    return {
        "claims": len(claims),
        "chapters": 80,
        "exercises": 48,
        "source_equations_pending": manuscript["native_equations"]["count"],
        "by_status": dict(sorted(Counter(c["status"] for c in claims.values()).items())),
        "extraction": dict(sorted(Counter(r["extraction_status"] for r in items).items())),
        "unimplemented": sum(
            c["implementation_status"] == "unimplemented" for c in contexts.values()
        ),
        "untested": sum(c["experiment_status"] == "not-run" for c in contexts.values()),
        "contradicted": sum(c["status"] == "refuted" for c in claims.values()),
        "empirical_evidence": sum(e["kind"] == "experiment" for e in evidence.values()),
        "externally_reviewed": sum(
            bool(c["independent_review"]["artifact_ids"]) for c in claims.values()
        ),
        "formal_artifacts_with_declared_assumptions": sum(
            bool(c["formal_proof"]["artifact_ids"]) for c in claims.values()
        ),
        "shared_schema": shared_schema,
    }


def report(summary):
    lines = [
        "# Research coverage at the M0 specification snapshot",
        "",
        "Generated by `scripts/check_research.py --write-report`. This is metadata",
        "coverage, not scientific verification. No training/proof benchmark has run.",
        "",
        "| Category | Count |",
        "| --- | --- |",
    ]
    for key in (
        "claims",
        "chapters",
        "exercises",
        "source_equations_pending",
        "unimplemented",
        "untested",
        "contradicted",
        "empirical_evidence",
        "externally_reviewed",
        "formal_artifacts_with_declared_assumptions",
    ):
        lines.append(f"| {key.replace('_', ' ')} | {summary[key]} |")
    lines += [
        "",
        "Claim statuses: " + json.dumps(summary["by_status"], sort_keys=True) + ".",
        "Extraction states: " + json.dumps(summary["extraction"], sort_keys=True) + ".",
        "",
        "Pending extraction includes every unextracted exercise and chapter. Partial",
        "extraction identifies selected prose claims only. Native equations remain",
        "pending-source-review. Required tests and independent reviews are obligations,",
        "not passing evidence. Formal artifacts, if later supplied, retain their axioms",
        "and checked scope; no all-book-proven status is generated.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--ci-root", type=Path)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    try:
        summary = validate(args.root, args.ci_root)
        if args.write_report:
            (args.root / "docs/research/coverage-report.md").write_text(report(summary))
        print(json.dumps(summary, sort_keys=True))
    except (ValueError, KeyError, OSError) as error:
        print("research check failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
