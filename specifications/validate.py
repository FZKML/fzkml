"""Offline source/evidence checks. Metadata validity is not scientific verification."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
Json = dict[str, Any]


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def local_file(root: Path, reference: str) -> Path:
    """Reject traversal, private locations and symlinks, including ancestor links."""
    parts = PurePosixPath(reference).parts
    require(parts and not reference.startswith("/"), "absolute/empty artifact path")
    require(
        ".." not in parts and not any(p.startswith(".") for p in parts),
        "unsafe artifact path: " + reference,
    )
    path = root
    for part in parts:
        path /= part
        require(not path.is_symlink(), "symlink artifact path: " + reference)
    require(
        path.is_file() and path.resolve().is_relative_to(root.resolve()),
        "missing/local-only artifact: " + reference,
    )
    return path


def read(root: Path, reference: str) -> Json:
    return json.loads(local_file(root, reference).read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def indexed(rows: list[Json], key: str) -> dict[str, Json]:
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), "duplicate " + key)
    return result


def checked_ref(root: Path, ref: Json) -> Path:
    reference, separator, symbol = ref["path"].partition("::")
    path = local_file(root, reference)
    require(digest(path) == ref["sha256"], "artifact hash mismatch: " + reference)
    if separator:
        require(reference.startswith("tests/") and path.suffix == ".py", "invalid test reference")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {
            method.name
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            if any(
                (isinstance(base, ast.Attribute) and base.attr == "TestCase")
                or (isinstance(base, ast.Name) and base.id == "TestCase")
                for base in node.bases
            )
            for method in node.body
            if isinstance(method, ast.FunctionDef)
        }
        require(symbol.startswith("test_") and symbol in functions, "missing named test: " + symbol)
    return path


def schemas(root: Path) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name in (
        "schemas/claims-1.0.0.json",
        "claims/schema-v1.json",
        "claims/source-map-schema-v1.json",
        "claims/traceability-schema-v1.json",
        "claims/candidate-evidence-schema-v1.json",
        "specifications/m4/schema-v1.json",
        "specifications/m4/report-schema-v1.json",
        "specifications/data_outcomes/schema-v1.json",
        "specifications/data_outcomes/report-schema-v1.json",
        "specifications/data_outcomes/factorial-schema-v1.json",
        "specifications/data_outcomes/adoption-schema-v1.json",
        "specifications/data_outcomes/sector-schema-v1.json",
        "specifications/ci_assurance/schema-v1.json",
        "specifications/ci_assurance/fixture-schema-v1.json",
        "specifications/ci_assurance/report-schema-v1.json",
    ):
        schema = read(root, name)
        Draft202012Validator.check_schema(schema)
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(schema["$id"], resource)
    # Registry has no network retrieval callback: unknown references fail closed.
    return registry


def check_schema(root: Path, name: str, data: Json, registry: Registry[Any]) -> None:
    try:
        Draft202012Validator(read(root, name), registry=registry).validate(data)
    except Exception as error:
        raise ValueError("schema validation failed: " + name + ": " + str(error)) from error


def check_source(root: Path, source: Json, manuscript: Json) -> dict[str, Json]:
    nodes = indexed(source["nodes"], "id")
    version, edition = manuscript["source_version"], manuscript["edition_id"]
    require(
        source["edition"] == edition and source["source_version"] == version,
        "source map version/edition mismatch",
    )
    editions = read(root, "claims/editions-v1.json")
    edition_record = indexed(editions["editions"], "id")[edition]
    require(
        editions["current_edition"] == edition
        and all(
            edition_record[key] == manuscript[key]
            for key in ("source_version", "observed_revision_id", "text_only_sha256")
        ),
        "edition migration required",
    )
    coverage = read(root, "docs/research/coverage.json")
    index = read(root, "docs/research/source-index.json")
    require(
        coverage["source_version"] == index["source_version"] == version,
        "source inventory version mismatch",
    )
    locations: dict[str, Json] = {}
    for row in coverage["items"]:
        locations[f"{row['kind']}:{row['number']}"] = row["source_location"]
        if row["kind"] == "chapter":
            locations["heading:" + row["source_location"]["heading_id"]] = row["source_location"]
    for row in index["sections"]:
        locations["heading:" + row["source_location"]["heading_id"]] = row["source_location"]
    for row in index["equations"] + index["non_chapter_equations"]:
        heading = row.get("section_heading_id")
        locations[row.get("id", f"native-{row['start_utf16']}")] = {
            "tab_id": manuscript["tab_id"],
            "start_utf16": row["start_utf16"],
            "end_utf16": row["end_utf16"],
            "heading_id": heading,
            "url": manuscript["canonical_url"] + ("#heading=" + heading if heading else ""),
        }
    aliases: dict[str, str] = {}
    for node in nodes.values():
        require(node["source_version"] == version, "node source version mismatch")
        for alias in node["aliases"]:
            require(alias not in aliases, "duplicate source alias")
            aliases[alias] = node["id"]
            require(
                alias in locations and node["location"] == locations[alias], "source locator drift"
            )
        parent = node["parent_id"]
        if parent is not None:
            require(parent in nodes and parent != node["id"], "dangling source parent")
            require(nodes[parent]["chapter"] == node["chapter"], "source parent chapter mismatch")
            require(nodes[parent]["kind"] in {"chapter", "section"}, "invalid parent kind")
            visited = {node["id"]}
            while parent is not None:
                require(parent not in visited and parent in nodes, "source parent cycle/dangling")
                visited.add(parent)
                parent = nodes[parent]["parent_id"]
        loc = node["location"]
        require(
            loc["tab_id"] == manuscript["tab_id"] and 0 <= loc["start_utf16"] < loc["end_utf16"],
            "invalid source range",
        )
        require(
            (
                loc["url"] == manuscript["canonical_url"]
                or loc["url"].startswith(manuscript["canonical_url"] + "#")
            ),
            "wrong source URL",
        )
        kind, number = node["kind"], node["number"]
        if kind in {"chapter", "exercise", "equation"}:
            code = {"chapter": "CH", "exercise": "EX", "equation": "EQ"}[kind]
            width = 4 if kind == "equation" else 3
            require(node["id"] == f"FZK-{edition}-{code}-{number:0{width}d}", "unstable source ID")
        else:
            require(node["id"] == f"FZK-{edition}-SEC-{loc['heading_id']}", "unstable section ID")
        if node["inspection_status"] == "equation-markup-inspected":
            record = read(root, node.get("inspection_record", ""))
            inspected = record.get("inspected_native_equation_ids", [])
            # First inspection record uses equation_review records rather than a flat list.
            inspected += [r["id"] for r in record.get("equation_review", [])]
            if not inspected:
                inspected = record.get("native_equation_ids", [])
            require(
                record["source_version"] == version
                and any(a in inspected for a in node["aliases"]),
                "missing equation inspection",
            )
            require(record.get("independent_review") is False, "source inspection is not review")
            require(
                re.fullmatch(r"[0-9a-f]{64}", record.get("export_sha256", "")),
                "missing inspected export digest",
            )
            require(
                record["export_sha256"] == edition_record["authorized_export_sha256"],
                "equation export version mismatch",
            )
    for kind, count in (("chapter", 80), ("exercise", 48), ("equation", 417)):
        values = [n["number"] for n in nodes.values() if n["kind"] == kind]
        require(
            len(values) == count and set(values) == set(range(1, count + 1)),
            "incomplete stable " + kind + " inventory",
        )
    equations = sorted(
        (n for n in nodes.values() if n["kind"] == "equation"),
        key=lambda n: n["location"]["start_utf16"],
    )
    require([n["number"] for n in equations] == list(range(1, 418)), "equation ordering drift")
    inspected_count = sum(n["inspection_status"] == "equation-markup-inspected" for n in equations)
    require(
        inspected_count == manuscript["native_equations"]["inspected_count"],
        "inspected equation count mismatch",
    )
    require(aliases.keys() == locations.keys(), "incomplete source alias inventory")
    return nodes


def successful(evidence: Json) -> bool:
    execution = evidence["execution"]
    return bool(
        execution
        and execution["outcome"] == "successful"
        and execution["source_commit"] == evidence["source_commit"]
    )


def claim_binding(claim: Json, record: Json) -> str:
    """Digest of the exact assertion and context an external artifact must address."""
    binding = {key: claim[key] for key in ("id", "source", "statement", "scope", "assumptions")}
    binding["relation_id"] = record["relation_id"]
    binding["specification"] = record["specification"]
    return hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def check_attestation(root: Path, item: Json) -> None:
    checked_ref(root, item)
    execution, formal, review = item["execution"], item["formal"], item["review"]
    if execution:
        require(execution["source_commit"] == item["source_commit"], "execution commit mismatch")
        if execution["kind"] == "observed-github-actions":
            require(
                re.fullmatch(
                    r"https://github.com/FZKML/fzkml/actions/runs/[0-9]+", execution["run_url"]
                ),
                "invalid hosted execution link",
            )
    if formal:
        require(item["kind"] == "formal-proof", "formal evidence kind mismatch")
        require(
            successful(item) and execution["kind"] == "trusted-checker-receipt",
            "formal proof needs successful checker execution",
        )
        for field in ("checked_artifact", "receipt"):
            checked_ref(root, formal[field])
        receipt = read(root, formal["receipt"]["path"])
        for key in (
            "statement_id",
            "statement_sha256",
            "kernel",
            "kernel_version",
            "axioms",
            "source_commit",
            "checker_exit_code",
            "claim_binding_sha256",
        ):
            require(receipt.get(key) == formal[key], "formal receipt mismatch: " + key)
        require(formal["source_commit"] == item["source_commit"], "formal commit mismatch")
        require(
            receipt.get("artifact_sha256") == formal["checked_artifact"]["sha256"],
            "formal checked artifact mismatch",
        )
    require((item["kind"] == "formal-proof") == (formal is not None), "missing formal declaration")
    if review:
        require(item["kind"] == "independent-review", "review evidence kind mismatch")
        checked_ref(root, review["artifact"])
        date.fromisoformat(review["date"])
        require(review["reviewed_source_commit"] == item["source_commit"], "review commit mismatch")
        require(review["reviewer"] not in review["independent_from"], "self review")
        receipt = read(root, review["artifact"]["path"])
        require(
            all(receipt.get(key) == value for key, value in review.items() if key != "artifact"),
            "independent review receipt mismatch",
        )
    require(
        (item["kind"] == "independent-review") == (review is not None), "missing review declaration"
    )
    replication = item["replication"]
    if replication:
        require(
            item["kind"] == "experiment" and successful(item),
            "replication needs successful experiment execution",
        )
        checked_ref(root, replication["result"])
        for ref in replication["raw_artifacts"]:
            checked_ref(root, ref)
        result = read(root, replication["result"]["path"])
        schema_path = "schemas/result-" + replication["result_schema"] + ".json"
        # Result 1.1 is usable only when its canonical reviewed schema is present.
        check_schema(root, schema_path, result, schemas(root))
        require(
            result["outcome"]["status"] == "successful"
            and result["provenance"]["source_commit"] == item["source_commit"],
            "replication outcome/commit mismatch",
        )
        require(
            replication["operator"] not in replication["independent_from"],
            "replication operator is not independent",
        )
    require(item["kind"] == "experiment" or replication is None, "replication kind mismatch")


def validate(root: Path = ROOT) -> Json:
    root = root.resolve()
    registry = read(root, "claims/registry.json")
    trace = read(root, "claims/traceability-v1.json")
    source = read(root, "claims/source-map-v1.json")
    manuscript = read(root, "docs/research/manuscript.json")
    contexts = read(root, "docs/research/claim-context.json")["claims"]
    local_schemas = schemas(root)
    check_schema(root, "claims/schema-v1.json", registry, local_schemas)
    check_schema(root, "claims/traceability-schema-v1.json", trace, local_schemas)
    check_schema(root, "claims/source-map-schema-v1.json", source, local_schemas)
    require(
        trace["source_version"] == manuscript["source_version"], "trace source version mismatch"
    )
    nodes = check_source(root, source, manuscript)
    claims = indexed(registry["claims"], "id")
    # Use this checker's own reviewed code, never code from the --root data input.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from specifications.ci_assurance.parameters import check_parameters
    from specifications.ci_assurance.planner import plan_matrix
    from specifications.data_outcomes.design import (
        check_sector_source,
        validate_adoption,
        validate_factorial,
    )

    assurance_path = "specifications/ci_assurance/"
    assurance = read(root, assurance_path + "contracts-v1.json")
    check_schema(root, assurance_path + "schema-v1.json", assurance, local_schemas)
    assurance_contracts = indexed(assurance["contracts"], "id")
    require(
        [(c["id"], c["issue"]) for c in assurance["contracts"]]
        == [(f"CI-{i + 16}", i + 111) for i in range(5)],
        "incomplete CI assurance coverage",
    )
    fixture = read(root, assurance_path + "fixtures-v1.json")
    check_schema(root, assurance_path + "fixture-schema-v1.json", fixture, local_schemas)
    fixture_ids = {row["id"] for row in fixture["traces"]}
    require(
        len(fixture_ids) == len(fixture["traces"])
        and fixture_ids == set(assurance_contracts["CI-16"]["fixture_ids"]),
        "CI assurance fixture reference mismatch",
    )
    test_tree = ast.parse(local_file(root, "tests/test_ci_assurance.py").read_text())
    assurance_tests = {
        node.name
        for node in ast.walk(test_tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    for contract in assurance_contracts.values():
        require(
            set(contract["required_tests"]) <= assurance_tests,
            "missing CI assurance test",
        )
    for reference in assurance["dependency_interfaces"]:
        checked_ref(root, reference)
    # This single schema-fixed hidden path is allowed; generic evidence paths remain strict.
    workflow_path = root / ".github" / "workflows" / "cpu.yml"
    require(
        workflow_path.is_file()
        and not any(
            path.is_symlink()
            for path in (root / ".github", root / ".github/workflows", workflow_path)
        ),
        "unsafe CI assurance workflow path",
    )
    workflow = workflow_path.read_text()
    require(
        "timeout-minutes: 20" in workflow
        and "contents: read" in workflow
        and "persist-credentials: false" in workflow
        and "./scripts/validate" in workflow,
        "CI assurance bounded workflow reference mismatch",
    )
    check_parameters(fixture["parameters"], local_file(root, assurance_path + "dp-geometric-v1.md"))
    matrix = read(root, assurance_path + "matrix-v1.json")
    review = read(root, assurance_path + "matrix-review-v1.json")
    require(
        set(review)
        == {
            "schema_version",
            "scope",
            "synthetic_digests",
            "live_approved_digests",
            "human_approval",
            "dispatch_supported",
        }
        and review["schema_version"] == "1.0.0"
        and review["scope"] == "synthetic-test-only"
        and review["live_approved_digests"] == []
        and review["human_approval"] is None
        and review["dispatch_supported"] is False,
        "CI assurance live approval not established",
    )
    plan_matrix(
        matrix,
        frozenset(review["synthetic_digests"]),
        local_file(root, assurance_path + "dataset-v1.json"),
        local_file(root, assurance_path + "software-v1.json"),
    )

    data_contract = read(root, "specifications/data_outcomes/contracts-v1.json")
    check_schema(root, "specifications/data_outcomes/schema-v1.json", data_contract, local_schemas)
    outcome_contracts = indexed(data_contract["contracts"], "id")
    require(
        len(outcome_contracts) == 5
        and {row["issue"] for row in outcome_contracts.values()} == {101, 102, 103, 104, 105},
        "incomplete data/outcome coverage",
    )
    require(
        data_contract["source_version"] == trace["source_version"]
        and data_contract["source_edition"] == manuscript["edition_id"],
        "data/outcome source version mismatch",
    )
    source_review = read(root, data_contract["source_review"])
    require(
        source_review["source_version"] == trace["source_version"]
        and source_review["observed_snapshot_revision"] == manuscript["observed_revision_id"]
        and source_review["migration_status"] == "pending-source-impact-review"
        and source_review["independent_review"] is False,
        "data/outcome historical source inspection mismatch",
    )
    require(set(source_review["source_refs"]) <= nodes.keys(), "dangling outcome inspection source")
    for section in source_review["source_sections"]:
        sid = section["source_id"]
        require(
            sid in nodes
            and nodes[sid]["kind"] == "section"
            and section["range_utf16"][0] == nodes[sid]["location"]["start_utf16"]
            and section["range_utf16"][1] > section["range_utf16"][0]
            and section["tab_id"] == manuscript["tab_id"],
            "outcome inspection locator mismatch",
        )
    required_file = local_file(root, "tests/test_data_outcomes.py")
    outcome_tests = {
        node.name
        for node in ast.walk(ast.parse(required_file.read_text()))
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    for row in outcome_contracts.values():
        require(set(row["source_refs"]) <= nodes.keys(), "dangling data/outcome source reference")
        require(set(row["affected_claim_ids"]) <= claims.keys(), "dangling affected outcome claim")
        require(set(row["required_tests"]) <= outcome_tests, "missing data/outcome test")
    for name, validator in (("factorial", validate_factorial), ("adoption", validate_adoption)):
        plan = read(root, f"specifications/data_outcomes/{name}-v1.json")
        check_schema(
            root, f"specifications/data_outcomes/{name}-schema-v1.json", plan, local_schemas
        )
        validator(plan)
        if name == "factorial":
            checked_ref(root, {"path": plan["extends"], "sha256": plan["extends_sha256"]})
    sector_cards = read(root, "specifications/data_outcomes/sector-cards-v1.json")
    check_schema(
        root, "specifications/data_outcomes/sector-schema-v1.json", sector_cards, local_schemas
    )
    cards = indexed(sector_cards["cards"], "id")
    require(
        {row["sector"] for row in cards.values()}
        == {"healthcare", "fraud", "industrial", "drug-discovery"},
        "incomplete sector coverage",
    )
    for card in cards.values():
        check_sector_source(card)
    m4 = read(root, "specifications/m4/contracts-v1.json")
    check_schema(root, "specifications/m4/schema-v1.json", m4, local_schemas)
    contracts = indexed(m4["contracts"], "id")
    require(
        len(contracts) == 4 and {row["issue"] for row in contracts.values()} == {76, 77, 78, 79},
        "incomplete M4 contract coverage",
    )
    require(
        m4["source_version"] == trace["source_version"]
        and m4["source_edition"] == manuscript["edition_id"],
        "M4 source version mismatch",
    )
    review = read(root, m4["source_review"])
    require(
        review["source_version"] == trace["source_version"]
        and review["observed_revision_id"] == manuscript["observed_revision_id"]
        and review["independent_review"] is False,
        "M4 source inspection mismatch",
    )
    for section in review["sections"]:
        sid = section["source_id"]
        require(
            sid in nodes
            and nodes[sid]["kind"] == "section"
            and section["range_utf16"][0] == nodes[sid]["location"]["start_utf16"]
            and section["range_utf16"][1] > section["range_utf16"][0],
            "M4 inspection locator mismatch",
        )
    tests = local_file(root, "tests/test_m4_contracts.py")
    names = {
        node.name
        for node in ast.walk(ast.parse(tests.read_text()))
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    for row in contracts.values():
        require(set(row["source_refs"]) <= nodes.keys(), "dangling M4 source reference")
        require(set(row["required_tests"]) <= names, "missing M4 required test")
    candidates = read(root, "claims/candidate-evidence-v1.json")
    check_schema(root, "claims/candidate-evidence-schema-v1.json", candidates, local_schemas)
    candidate_records = indexed(candidates["records"], "id")
    for candidate in candidate_records.values():
        require(
            candidate["source_version"] == trace["source_version"],
            "candidate source version mismatch",
        )
        require(
            candidate["source_map_sha256"] == digest(local_file(root, "claims/source-map-v1.json")),
            "candidate source map digest mismatch",
        )
        observation = candidate["observation"]
        date.fromisoformat(observation["date"])
        require(
            observation["discovered"] == observation["passed"] + len(observation["skipped"]),
            "candidate skipped tests counted as passed",
        )
        hosted = candidate["hosted_check_scope"]
        require(
            hosted["language_source_commit"] == candidate["source_commit"]
            and hosted["language_math_discovered"]
            == hosted["language_math_passed"] + hosted["language_math_skipped"]
            and hosted["language_total_tests"] >= hosted["language_math_discovered"],
            "candidate hosted execution scope mismatch",
        )
        for reference in candidate["files"]:
            parts = PurePosixPath(reference["path"]).parts
            require(
                parts
                and not reference["path"].startswith("/")
                and not any(part.startswith(".") for part in parts),
                "unsafe candidate path",
            )
            expected_url = (
                "https://github.com/FZKML/fzkml/blob/"
                + candidate["source_commit"]
                + "/"
                + reference["path"]
            )
            require(reference["url"] == expected_url, "candidate immutable URL mismatch")
        indexed(candidate["vectors"], "id")
        for vector in candidate["vectors"]:
            require(
                all(
                    sid in nodes and nodes[sid]["chapter"] == vector["chapter"]
                    for sid in vector["source_refs"]
                ),
                "candidate source mapping mismatch",
            )
            require(
                all(
                    cid in claims and claims[cid]["source"]["chapter"] == vector["chapter"]
                    for cid in vector["claim_ids"]
                ),
                "candidate claim mapping mismatch",
            )
    for vector in read(root, "specifications/source-inputs-v1.json")["vectors"]:
        if "candidate_validation_record" in vector:
            require(
                vector["candidate_validation_catalog"] == "claims/candidate-evidence-v1.json"
                and vector["candidate_validation_record"] in candidate_records,
                "missing candidate validation record",
            )
            candidate = candidate_records[vector["candidate_validation_record"]]
            require(
                any(
                    vector["claim_id"] in row["claim_ids"]
                    and set(vector["source_refs"]) <= set(row["source_refs"])
                    for row in candidate["vectors"]
                ),
                "candidate source-input mismatch",
            )
    evidence = indexed(registry["evidence"], "id")
    records = indexed(trace["records"], "claim_id")
    attestations = indexed(trace["evidence"], "evidence_id")
    require(claims.keys() == records.keys() == contexts.keys(), "incomplete claim traceability")
    require(evidence.keys() == attestations.keys(), "incomplete evidence attestations")
    relations = indexed(trace["relations"], "id")
    for reference in [*relations.values(), trace["protocol"]]:
        checked_ref(root, reference)
    protocol = read(root, trace["protocol"]["path"])
    require(
        protocol["protocol_id"] == trace["protocol"]["id"]
        and protocol["source_version"] == trace["source_version"],
        "protocol identity mismatch",
    )
    local_file(root, protocol["normative_document"])
    for profile in protocol["profiles"]:
        require(
            profile["relation_id"] in relations
            and profile["specification"] == relations[profile["relation_id"]]["path"],
            "profile relation mismatch",
        )
    for eid, item in attestations.items():
        canonical = evidence[eid]
        require(
            all(item[key] == canonical[key] for key in ("kind", "path", "scope")),
            "evidence contract mismatch",
        )
        check_attestation(root, item)
    formal_count = reviewed_count = 0
    for cid, claim in claims.items():
        record, context = records[cid], contexts[cid]
        require(record["author"] == claim["owner"], "claim author mismatch")
        require(
            record["source_version"] == claim["source"]["version"] == trace["source_version"],
            "claim source version mismatch",
        )
        require(claim["source"]["edition"] == manuscript["edition_id"], "claim edition mismatch")
        expected = {f"FZK-{manuscript['edition_id']}-CH-{claim['source']['chapter']:03d}"}
        expected.add(
            f"FZK-{manuscript['edition_id']}-SEC-{context['source_location']['heading_id']}"
        )
        for alias in context["native_equation_ids"]:
            found = [n["id"] for n in nodes.values() if alias in n["aliases"]]
            require(len(found) == 1, "missing claim equation")
            expected.add(found[0])
        require(set(record["source_refs"]) == expected, "claim source mapping mismatch")
        for sid in expected:
            require(
                sid in nodes and nodes[sid]["chapter"] == claim["source"]["chapter"],
                "claim source chapter mismatch",
            )
        require(
            claim["source"]["section"] == "anchor." + context["source_location"]["heading_id"],
            "claim section mismatch",
        )
        expected_equation = (
            context["native_equation_ids"][0].replace("native-", "native.")
            if context["native_equation_ids"]
            else "none"
        )
        require(claim["source"]["equation"] == expected_equation, "claim equation alias mismatch")
        require(
            record["specification"]["path"] == context["specification"],
            "claim specification mismatch",
        )
        checked_ref(root, record["specification"])
        relation = record["relation_id"]
        expected_relation = (
            "analytic-reference-v1"
            if context["implementation_status"] == "reference-implemented"
            else "m0-two-feature-v0.1"
            if cid.split("-")[2] in {"C03", "C07", "C40", "C43"}
            else None
        )
        require(
            relation == expected_relation and (relation is None or relation in relations),
            "claim relation mismatch",
        )
        require(record["evidence_ids"] == claim["evidence_ids"], "claim evidence binding mismatch")
        require(set(record["evidence_ids"]) <= evidence.keys(), "dangling claim evidence")
        linked = [attestations[eid] for eid in record["evidence_ids"]]
        for reference in record["implementation"]:
            checked_ref(root, reference)
        if record["source_inspection"]:
            inspection = read(root, record["source_inspection"])
            require(
                inspection["source_version"] == trace["source_version"],
                "claim inspection version mismatch",
            )
        if claim["status"] in {"implemented", "tested", "replicated"}:
            require(record["implementation"], "implemented status without implementation")
        if claim["status"] == "tested":
            require(
                any(e["kind"] == "unit-test" and successful(e) for e in linked),
                "tested status without successful test evidence",
            )
            require(
                all(
                    any(
                        e["source_commit"] == ref["source_commit"]
                        for e in linked
                        if e["kind"] == "unit-test" and successful(e)
                    )
                    for ref in record["implementation"]
                ),
                "tested implementation commit mismatch",
            )
        if claim["status"] == "replicated":
            require(
                any(
                    e["kind"] == "experiment" and successful(e) and e.get("replication")
                    for e in linked
                ),
                "replication requires raw result manifest and execution",
            )
            for item in linked:
                replication = item["replication"]
                if not replication:
                    continue
                require(
                    record["author"] in replication["independent_from"]
                    and replication["reproduces_evidence_id"] in evidence
                    and replication["reproduces_evidence_id"] != item["evidence_id"],
                    "replication missing independent prior evidence",
                )
                result = read(root, replication["result"]["path"])
                require(
                    cid in result["claim_ids"]
                    and result["scenario"]["relation_version"] == relation,
                    "replication claim/relation mismatch",
                )
        formal_ids = claim["formal_proof"]["artifact_ids"]
        review_ids = claim["independent_review"]["artifact_ids"]
        require(
            set(formal_ids + review_ids) <= set(record["evidence_ids"]),
            "unbound formal/review evidence",
        )
        for eid in formal_ids:
            declaration = attestations[eid]["formal"]
            require(
                declaration is not None
                and declaration["statement_id"] == cid
                and declaration["statement_sha256"]
                == hashlib.sha256(claim["statement"].encode()).hexdigest(),
                "formal statement mismatch",
            )
            require(
                declaration["axioms"] == claim["formal_proof"]["assumptions"],
                "formal assumptions mismatch",
            )
            require(
                declaration["claim_binding_sha256"] == claim_binding(claim, record),
                "formal claim context mismatch",
            )
        for eid in review_ids:
            review = attestations[eid]["review"]
            require(
                review is not None
                and record["author"] in review["independent_from"]
                and review["reviewer"] != record["author"],
                "missing independent reviewer",
            )
            require(
                review["claim_binding_sha256"] == claim_binding(claim, record),
                "review claim context mismatch",
            )
            receipt = read(root, review["artifact"]["path"])
            require(
                receipt.get("claim_id") == cid
                and receipt.get("source_version") == record["source_version"],
                "independent review source mismatch",
            )
        if claim["status"] == "reviewed":
            require(review_ids, "reviewed status without independent review")
        if claim["evidence_class"] == "formal":
            require(formal_ids, "formal classification without proof artifacts")
        formal_count += bool(formal_ids)
        reviewed_count += bool(review_ids)
    return {
        "schema_version": "1.0.0",
        "claims": len(claims),
        "source_nodes": len(nodes),
        "status_counts": dict(sorted(Counter(c["status"] for c in claims.values()).items())),
        "inspected_equations": manuscript["native_equations"]["inspected_count"],
        "pending_equations": 417 - manuscript["native_equations"]["inspected_count"],
        "declared_formal_artifacts": formal_count,
        "declared_independent_reviews": reviewed_count,
        "candidate_external_records": len(candidate_records),
        "m4_contracts": len(contracts),
        "data_outcome_contracts": len(outcome_contracts),
        "ci_assurance_contracts": len(assurance_contracts),
        "trust": "Metadata checked; external receipts/reviews require trusted verification.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.root), indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("research contract invalid: " + str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
