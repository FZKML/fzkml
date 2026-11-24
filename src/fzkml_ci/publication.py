"""Digest-bound public-synthetic policy enforcement, separate from scientific review.

The checked-in proposal has no human approval. Merely setting a record's boolean
does not authorize S04 publication. Policy approval is governed by protected source
review; this validator does not certify the honesty of a reviewer declaration.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .validate import ROOT, bounded_file, load, public_tree, require, validate_bundle


def canonical_digest(value: Any) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    )


def policy_digest(policy: dict[str, Any]) -> str:
    return canonical_digest(
        {k: v for k, v in policy.items() if k not in {"status", "human_approval"}}
    )


def authorize(
    bundle: dict[str, Any],
    claims: dict[str, Any],
    policy: dict[str, Any] | None = None,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load(root / "ci/publication-policy.json") if policy is None else policy
    public_tree(policy)
    require(
        set(policy)
        == {
            "version",
            "id",
            "status",
            "scope",
            "producer_files",
            "schemas",
            "allowed_scenarios",
            "allowed_outcomes",
            "limitations",
            "human_approval",
        },
        "publication-policy-fields",
    )
    require(
        policy["version"] == 1 and policy["id"] == "s04-public-synthetic-v1",
        "publication-policy-version",
    )
    approval = policy["human_approval"]
    require(
        policy["status"] == "approved" and isinstance(approval, dict),
        "publication-policy-human-review-pending",
    )
    require(
        set(approval) == {"reviewer", "date", "scope", "policy_digest", "evidence_url"},
        "publication-human-approval-fields",
    )
    require(
        all(isinstance(v, str) and bool(v.strip()) for v in approval.values()),
        "publication-review-identity",
    )
    require(approval["policy_digest"] == policy_digest(policy), "publication-policy-approval-drift")
    require(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", approval["date"]) is not None
        and approval["evidence_url"].startswith("https://github.com/FZKML/fzkml/"),
        "publication-review-evidence",
    )
    require(
        os.environ.get("GITHUB_REPOSITORY") == "FZKML/fzkml"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and os.environ.get("S04_PUBLICATION_CONTEXT") == "protected-public-reports"
        and ".github/workflows/reports.yml@" in os.environ.get("GITHUB_WORKFLOW_REF", ""),
        "publication-trusted-source-required",
    )
    run = os.environ.get("GITHUB_RUN_ID", "")
    require(run.isdigit() and int(run) > 0, "publication-real-workflow-required")
    for mapping in [policy["producer_files"], policy["schemas"]]:
        require(isinstance(mapping, dict) and 0 < len(mapping) <= 20, "publication-allowlist-size")
        for relative, expected in mapping.items():
            parts = Path(relative).parts
            require(
                not Path(relative).is_absolute()
                and ".." not in parts
                and (not relative.startswith(".") or relative.startswith(".github/workflows/")),
                "publication-allowlist-path",
            )
            path = root / relative
            require(
                not any((root / Path(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1)),
                "publication-allowlist-symlink",
            )
            actual = "sha256:" + hashlib.sha256(bounded_file(path)).hexdigest()
            require(actual == expected, "publication-producer-or-schema-drift")
    validate_bundle(bundle, claims)
    require(
        bundle["schema_version"] == "1.1.0" and 1 <= len(bundle["results"]) <= 3,
        "publication-scoped-bundle-required",
    )
    require(
        {r["scenario"]["id"] for r in bundle["results"]} <= set(policy["allowed_scenarios"]),
        "publication-scenario-scope",
    )
    fixture_digest = (
        "sha256:" + hashlib.sha256(bounded_file(root / "assets/public/numeric-v1.json")).hexdigest()
    )
    for row in bundle["results"]:
        require(
            row["outcome"]["status"] in policy["allowed_outcomes"]
            and row["publication_review"]["approved"] is False,
            "publication-candidate-state",
        )
        require(
            row["provenance"].get("execution_kind") == "github-actions"
            and row["provenance"]["workflow_run"] == int(run)
            and row["provenance"]["source_commit"] == os.environ.get("GITHUB_SHA"),
            "publication-execution-identity",
        )
        require(
            row["scenario"]["statement"] == "public-exact-linear-three-client"
            and row["scenario"]["backend"] == "ark-groth16-0.5.0-bn254"
            and row["scenario"]["security_mode"] == "research",
            "publication-relation-scope",
        )
        require(
            all(
                row["scenario"][kind]["id"] == f"synthetic:s04-{kind}"
                and row["scenario"][kind]["license"] == "Apache-2.0"
                and row["scenario"][kind]["digest"] == fixture_digest
                for kind in ["model", "dataset"]
            ),
            "publication-input-scope",
        )
    approved = copy.deepcopy(bundle)
    for row in approved["results"]:
        row["publication_review"] = {
            "approved": True,
            "review_id": "public:s04-public-synthetic-v1",
        }
    receipt = {
        "version": 1,
        "status": "authorized-under-reviewed-policy",
        "policy_digest": policy_digest(policy),
        "human_policy_approver": approval["reviewer"],
        "human_policy_approval_date": approval["date"],
        "approval_evidence": approval["evidence_url"],
        "automated_verifier": "fzkml-s04-policy-v1",
        "workflow_run": int(run),
        "source_commit": os.environ["GITHUB_SHA"],
        "scope": policy["scope"],
        "candidate_digest": canonical_digest(bundle),
        "authorized_results_digest": canonical_digest(approved),
        "claims_digest": canonical_digest(claims),
        "producer_digests": policy["producer_files"],
        "schema_digests": policy["schemas"],
        "limitations": [
            "Policy authorization is not per-run human scientific review.",
            "No independent cryptographic, privacy or performance assurance is asserted.",
        ],
    }
    return approved, receipt
