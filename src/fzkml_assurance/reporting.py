"""Scope-locked review packet and historical all-book evidence index.

Reuses CI-05 claim validation and CI-06 rendering. It produces a book revision
proposal, not an edit of the canonical manuscript or scientific publication.
"""

from __future__ import annotations

import ast
import json
import subprocess
from typing import Any

from fzkml_ci.report import render, text
from fzkml_ci.validate import ROOT, load, require, validate_claims

from .common import BASE, blob, check_schema, file_sha, sha

SOURCE_FILES = [
    "claims/registry.json",
    "claims/traceability-v1.json",
    "docs/research/coverage.json",
    "docs/research/claim-context.json",
    "docs/research/manuscript.json",
    "experiments/m0/reporting-cases.json",
    "experiments/m0/replication-cards.json",
]
REVIEW_FILES = [
    "Cargo.lock",
    "uv.lock",
    "specs/numeric-contract-v1.json",
    "specs/private-transition-v1.json",
    "specs/aggregation-v1.json",
    "crates/fzkml-core/src/lib.rs",
    "crates/fzkml-core/src/proof.rs",
    "crates/fzkml-core/src/private.rs",
    "crates/fzkml-core/src/aggregation/mod.rs",
    "crates/fzkml-core/src/aggregation/crypto.rs",
    "crates/fzkml-core/src/aggregation/roles.rs",
    "crates/fzkml-core/src/aggregation/durable.rs",
    "crates/fzkml-core/src/aggregation/tests.rs",
    "crates/fzkml-core/src/private_transition/tests.rs",
    "specs/m0/security-v0.1.md",
    "docs/assurance.md",
    "docs/PRIVATE-TRANSITION.md",
    "docs/PROTECTED-AGGREGATION.md",
]


def read_source(path: str) -> Any:
    return json.loads(blob(BASE, path))


def refs(paths: list[str]) -> list[dict[str, str]]:
    return [
        {
            "path": p,
            "source_commit": BASE,
            "sha256": sha(blob(BASE, p)),
            "url": f"https://github.com/FZKML/fzkml/blob/{BASE}/{p}",
        }
        for p in paths
    ]


def generator() -> dict[str, str]:
    path = "src/fzkml_assurance/reporting.py"
    commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", path], cwd=ROOT, text=True
    ).strip()
    return {"path": path, "sha256": file_sha(path), "source_commit": commit or "uncommitted"}


def review_packet() -> dict[str, Any]:
    return {
        "version": 1,
        "issue": 107,
        "status": "awaiting-independent-review",
        "protocol_subject_commit": BASE,
        "reviewed_commit": None,
        "generator": generator(),
        "configuration": "v0.2-three-client-three-recipient-threshold2-research",
        "release_label": "unreviewed-research-candidate",
        "reviewer": "TBD — independent external reviewer",
        "appointment_status": "not-appointed",
        "packet_owner": "Codex Session 04",
        "packet_status": "prepared-for-maintainer-review",
        "distribution": "not-authorized",
        "reviewer_requirements": [
            "Relevant ZK-circuit, finite-field/fixed-point and Rust cryptography expertise.",
            "Conflicts of interest disclosed before appointment.",
            "Written severity-rated findings and remediation verification agreed.",
        ],
        "reviewers": [],
        "findings": [],
        "scope": {
            "included": [
                "Signed integer/RNE semantics and finite-field range connections.",
                "Actual private arithmetic circuit, commitment binding and local research setup.",
                "Pedersen VSS/proof/share/credential/state/observer composition "
                "in the v0.2 fixture.",
                "Durable authority/replay and accepted-set invariants under declared assumptions.",
            ],
            "excluded": [
                "Unreviewed backends/models, GPU, production ceremony or real deployment.",
                "Complete DP release/accountant, consensus, data authenticity or physical erasure.",
                "Security of later commits or CI/model candidates not in this protocol snapshot.",
            ],
        },
        "artifacts": refs(REVIEW_FILES),
        "prerequisites": [23, 26, 34, 36, 44, 50, 51, 52, 54, 55, 56, 57],
        "required_domains": [
            "cryptography",
            "integer-arithmetic",
            "privacy-composition",
            "distributed-state",
        ],
        "review_questions": [
            "Check commitments, proved witnesses and delivered values bind the same object.",
            "Check every integer/range/rounding equation rather than field equality alone.",
            "Check successor re-admission: input bound32 and output bound80 do not imply closure.",
            "Distinguish proof validity, admission, replay consumption and availability.",
            "Identify every observer, recipient corruption limit, authority trust and DP scope.",
        ],
        "limitations": [
            "No reviewer is appointed, contacted or represented as consenting.",
            "No external findings or remediation certification exists; internal "
            "CI is not an external audit.",
            "Review may be commissioned for this narrow configuration without "
            "closing comprehensive FZK-R069.",
            "Public source/fixtures only; no private manuscript, witness, "
            "credential secret or setup secret.",
        ],
    }


def validate_review(packet: dict[str, Any], require_reviewed: bool = False) -> None:
    check_schema(packet, "review-packet")
    require(packet["protocol_subject_commit"] == BASE, "review-scope-drift")
    require(packet["artifacts"] == refs(REVIEW_FILES), "review-artifact-drift")
    require(
        packet["release_label"] == "unreviewed-research-candidate"
        and packet["reviewed_commit"] is None
        and not packet["reviewers"],
        "no-independent-review-appointed",
    )
    require(
        packet["appointment_status"] == "not-appointed"
        and packet["distribution"] == "not-authorized"
        and packet["reviewer"] == "TBD — independent external reviewer"
        and packet["packet_owner"] == "Codex Session 04",
        "review-distribution-not-authorized",
    )
    for finding in packet["findings"]:
        require(
            set(finding) == {"id", "severity", "disposition", "scope_commit", "regressions"},
            "finding-fields",
        )
        require(
            finding["scope_commit"] == BASE
            and finding["severity"] in {"critical", "high", "medium", "low", "informational"}
            and finding["disposition"] in {"open", "fixed", "refuted", "deferred"},
            "finding-scope",
        )
        if finding["disposition"] == "fixed":
            require(bool(finding["regressions"]), "fixed-finding-needs-regression")
            for ref in finding["regressions"]:
                path, name = ref.split("::")
                functions = {
                    n.name
                    for n in ast.walk(ast.parse(blob(BASE, path)))
                    if isinstance(n, ast.FunctionDef)
                }
                require(name.startswith("test_") and name in functions, "finding-regression-link")
    require(not require_reviewed, "independent-review-pending-not-a-CI-pass")


def coverage_status(claims: list[dict[str, Any]], contexts: dict[str, Any]) -> str:
    if any(c["status"] == "refuted" for c in claims):
        return "contradicted"
    if any(c["status"] == "inconclusive" for c in claims):
        return "inconclusive"
    if claims and all(c["kind"] == "definition" for c in claims):
        return "not-executable"
    if any(c["status"] in {"tested", "replicated", "reviewed"} for c in claims):
        require(
            all(c["status"] not in {"replicated", "reviewed"} for c in claims)
            or all(c["evidence_ids"] for c in claims),
            "reported-promotion-without-evidence",
        )
        if all(
            contexts[c["id"]]["implementation_status"] == "reference-implemented"
            for c in claims
            if c["status"] == "tested"
        ):
            return "tested-analytic-reference"
        return "ci-conformance-only"
    return "not-run"


def evidence_index() -> dict[str, Any]:
    registry = read_source("claims/registry.json")
    validate_claims(registry)
    coverage = read_source("docs/research/coverage.json")
    context = read_source("docs/research/claim-context.json")["claims"]
    records = {r["claim_id"]: r for r in read_source("claims/traceability-v1.json")["records"]}
    manuscript = read_source("docs/research/manuscript.json")
    claims = {c["id"]: c for c in registry["claims"]}
    items = []
    for row in coverage["items"]:
        selected = [claims[c] for c in row["claim_ids"]]
        items.append(
            {
                "kind": row["kind"],
                "number": row["number"],
                "title": row["title"],
                "status": coverage_status(selected, context),
                "source_review": row["source_review"],
                "extraction_status": row["extraction_status"],
                "source_url": row["source_location"]["url"],
                "claim_ids": row["claim_ids"],
                "planned_issues": row["planned_issues"],
                "evidence_ids": sorted({e for c in selected for e in c["evidence_ids"]}),
                "reason": "Only listed claims/references are covered, not the entire item.",
            }
        )
    claim_rows = []
    for claim in registry["claims"]:
        claim_rows.append(
            {
                "id": claim["id"],
                "source": claim["source"],
                "status": claim["status"],
                "statement": claim["statement"],
                "declared_evidence_class": claim["evidence_class"],
                "relation_id": records[claim["id"]]["relation_id"],
                "scope": claim["scope"],
                "assumptions": claim["assumptions"],
                "limitations": claim["limitations"],
                "evidence_ids": claim["evidence_ids"],
                "formal_artifact_ids": claim["formal_proof"]["artifact_ids"],
                "independent_review_ids": claim["independent_review"]["artifact_ids"],
            }
        )
    return {
        "version": 1,
        "issue": 108,
        "status": "book-update-proposal-not-applied",
        "source_commit": BASE,
        "edition": manuscript["edition_id"],
        "source_version": coverage["source_version"],
        "canonical_book": manuscript["canonical_url"],
        "generator": generator(),
        "inputs": refs(SOURCE_FILES),
        "coverage": items,
        "claims": claim_rows,
        "reporting_fixture_cases": read_source("experiments/m0/reporting-cases.json")["cases"],
        "reporting_fixture_classification": "Fictional acceptance cases, not actual experiments.",
        "replication_cards": [
            {
                "id": r["id"],
                "execution_status": r["execution_status"],
                "source_url": r["source_url"],
                "mode": r["mode"],
                "missing": r["missing"],
            }
            for r in read_source("experiments/m0/replication-cards.json")["cards"]
        ],
        "classes": {
            "ci_conformance": "Recorded separately from theorem/security/privacy/utility support.",
            "empirical_field_study": "not-run",
            "mathematical_derivations": "Only the five scoped analytic references are tested.",
            "security_arguments": "specified/planned; no security theorem certified by CI.",
            "independent_review": "not-commissioned",
        },
        "ci_execution_ledger": load(ROOT / "ci/assurance/ci-execution-ledger-v1.json"),
        "ci_execution_ledger_digest": file_sha("ci/assurance/ci-execution-ledger-v1.json"),
        "candidate_results": [
            {
                "producer": "Session04 PR127 model candidates",
                "source_commit": BASE,
                "state": "executed-CI-conformance-scientific-publication-unapproved",
                "ci_run": "https://github.com/FZKML/fzkml/actions/runs/45520402482",
                "configuration": "docs/MODEL-CAPACITY-EVIDENCE.md",
                "fixture": "assets/public/model-capacity-v1.json",
                "fixture_digest": sha(blob(BASE, "assets/public/model-capacity-v1.json")),
                "artifact_policy": "Raw science needs publication review; not embedded.",
                "hardware_provenance": "Hosted image logs; field hardware not inventoried.",
                "uncertainty": "Tiny public fixtures only; no private training/DP/utility claim.",
            }
        ],
        "corrections": [
            {
                "id": "relation-scope",
                "status": "proposed-scope-caveat",
                "scope": "M0 half-up/two-feature differs from fzknum RNE/one-feature.",
                "evidence": "specifications/relations/fzknum-1.0.0.json",
                "book_source_claim_status_changed": False,
            },
            {
                "id": "toy-evaluation-overlap",
                "status": "invalid-development-prototype",
                "scope": "Overlapping development pilot excluded; final holdout disjoint.",
                "evidence": "ci/assurance/benchmark-plan-v1.json",
                "book_source_claim_status_changed": False,
            },
            {
                "id": "rne-tie-translation",
                "status": "proposed-scope-caveat",
                "scope": "RNE(.5)=0, RNE(1.5)=2: translation/sensitivity needs review.",
                "evidence": "assets/public/ci14-golden-v1.json",
                "book_source_claim_status_changed": False,
            },
        ],
        "publication_review": {"approved": False, "canonical_manuscript_edited": False},
        "limitations": [
            "Historical pinned source edition, not an assertion about the latest "
            "manuscript revision.",
            "Unmapped/not-extracted is not the same as disproved or not executable.",
            "Failed/inconclusive/refuted items cannot be dropped or converted to supported claims.",
            "Candidate CI evidence is not independent review, DP/security proof "
            "or universal model improvement.",
        ],
    }


def validate_index(value: dict[str, Any]) -> None:
    check_schema(value, "evidence-index")
    for kind, total in [("chapter", 80), ("exercise", 48)]:
        rows = [r for r in value["coverage"] if r["kind"] == kind]
        require(
            len(rows) == total and {r["number"] for r in rows} == set(range(1, total + 1)),
            "all-book-coverage-required",
        )
    require(len(value["coverage"]) == 128, "coverage-cardinality")
    registry = read_source("claims/registry.json")
    require(
        {c["id"]: c["status"] for c in value["claims"]}
        == {c["id"]: c["status"] for c in registry["claims"]},
        "source-claim-status-promotion-or-omission",
    )
    require(
        value["publication_review"] == {"approved": False, "canonical_manuscript_edited": False},
        "book-publication-review-pending",
    )
    require(value == evidence_index(), "source-evidence-omission-or-promotion")


def markdown(index: dict[str, Any], packet: dict[str, Any]) -> str:
    lines = [
        "# Proposed book evidence update",
        "",
        "Unapplied proposal; scientific publication approval is pending.",
        f"Historical source `{index['source_commit']}`, edition `{index['edition']}`.",
        "CI conformance, analytic references, empirical studies, security "
        "arguments and external review remain separate.",
        "",
        "| Item | Coverage status | Claims | Source |",
        "| --- | --- | --- | --- |",
    ]
    for row in index["coverage"]:
        name = f"Chapter {row['number']}" if row["kind"] == "chapter" else f"D.{row['number']}"
        claim_text = ", ".join(row["claim_ids"]) or "none extracted"
        lines.append(
            f"| {name} | {row['status']} | {claim_text} | [locator]({row['source_url']}) |"
        )
    lines += ["", "## Actual hosted CI observations", ""]
    for observation in index["ci_execution_ledger"]["observations"]:
        lines.append(
            f"- [{observation['purpose']}]({observation['url']}): "
            f"{observation['outcome']}; source `{observation['source_commit']}`, "
            f"checkout `{observation['checkout_commit']}`."
        )
    lines += ["", "## Source claims and checked scope", ""]
    for c in index["claims"]:
        lines += [
            f"- `{c['id']}`: {c['status']}; {c['declared_evidence_class']}; "
            f"relation `{c['relation_id']}`.",
            f"  Scope: {text(c['scope'])} Assumptions: {text('; '.join(c['assumptions']))}",
        ]
    lines += ["", "## Counterevidence and untested ledger", ""]
    lines += [
        f"- {c['id']}: {text(c['scope'])} Source claim status unchanged."
        for c in index["corrections"]
    ]
    lines += [
        "- Raw candidate scientific results remain unapproved and withheld from "
        "publication; execution metadata is retained.",
        "- Field study, matched privacy budgets, physical heterogeneous devices "
        "and independent review remain not-run.",
        f"- Review scope is `{packet['protocol_subject_commit']}`; "
        "no reviewer or reviewed release label exists.",
        "",
        "## Existing CI-06 infrastructure report",
        "",
        "The canonical CI-06 renderer remains authoritative for its approved "
        "synthetic metadata fixtures.",
        "Scientific candidates with approved=false are not fed to that publication renderer.",
        "",
    ]
    # Reuse the existing renderer rather than defining a competing result format.
    fixture = load(ROOT / "examples/results.json")
    canonical = render(fixture, read_source("claims/registry.json"))
    lines.append(
        "Canonical CI-06 fixture summary digest: `" + sha(canonical["summary.json"].encode()) + "`."
    )
    lines.append("Reproduce metadata fixtures: `./scripts/build-public-report`.")
    return "\n".join(lines) + "\n"


def build(check: bool = False) -> int:
    packet, index = review_packet(), evidence_index()
    validate_review(packet)
    validate_index(index)
    outputs = {
        "review-packet-v1.json": json.dumps(packet, sort_keys=True, indent=2) + "\n",
        "evidence-index-v1.json": json.dumps(index, sort_keys=True, indent=2) + "\n",
        "book-evidence-proposal.md": markdown(index, packet),
    }
    destination = ROOT / "docs/assurance"
    destination.mkdir(parents=True, exist_ok=True)
    for name, contents in outputs.items():
        path = destination / name
        if check:
            require(path.read_text() == contents, "noncanonical-review-or-book-proposal")
        else:
            path.write_text(contents)
    print("Prepared/verified historical all-book proposal and unreviewed scope-locked packet.")
    return 0
