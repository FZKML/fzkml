"""Deterministic escaped reports, generated only from validated public records."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from .validate import (
    ARTIFACTS,
    MAX_FILE,
    MAX_TOTAL,
    require,
    require_publication,
    validate_artifacts,
    validate_bundle,
)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def text(value: Any) -> str:
    # Escape Markdown metacharacters as entities; HTML receives a separate escape pass.
    return "".join(c if c.isalnum() or c in " .,:-/" else f"&#{ord(c)};" for c in str(value))


def render(bundle: dict[str, Any], claims: dict[str, Any]) -> dict[str, str]:
    coverage = validate_bundle(bundle, claims)
    require_publication(bundle)
    summary: dict[str, Any] = {"schema_version": "1.0.0", "coverage": coverage, "runs": []}
    lines = [
        "# FZKML v0.1 research report",
        "",
        "Infrastructure report. Scientific claim extraction: pending R001. "
        "Empty coverage is not evidence that the book is verified.",
        "",
        "Inputs: [retained raw repetitions](results.json), [claim registry](claims.json).",
        "",
        f"Registered claims: {coverage['total']}; unmapped: {len(coverage['unmapped'])}.",
        "",
    ]
    for status, ids in coverage["by_status"].items():
        lines.append(f"- {status}: {len(ids)}" + ("; " + ", ".join(map(text, ids)) if ids else ""))
    lines.append("")
    for claim in sorted(claims["claims"], key=lambda c: c["id"]):
        lines += [
            f"## Claim {text(claim['id'])}",
            "",
            f"{text(claim['statement'])}",
            "",
            f"- Scope: {text(claim['scope'])}",
            f"- Kind/evidence class: {text(claim['kind'])} / {text(claim['evidence_class'])}",
            f"- Status: {claim['status']}",
            f"- Assumptions: {text('; '.join(claim['assumptions']))}",
            f"- Formal proof scope: {text(claim['formal_proof']['scope'])}",
            f"- Independent review scope: {text(claim['independent_review']['scope'])}",
            f"- Evidence IDs: {text(', '.join(claim['evidence_ids'])) or 'unmapped'}",
            "",
        ]
    plots: list[str] = []
    for result in sorted(bundle["results"], key=lambda r: r["run_id"]):
        s = result["scenario"]
        hardware = result["provenance"]["hardware"]
        comparison = {
            key: s[key]
            for key in (
                "statement",
                "relation_version",
                "numerical_semantics",
                "backend",
                "security_mode",
                "parameters_digest",
                "key_digest",
                "program_digest",
                "circuit_digest",
                "model",
                "dataset",
            )
        }
        comparison["hardware"] = hardware
        group = hashlib.sha256(canonical(comparison).encode()).hexdigest()[:16]
        status = result["outcome"]["status"]
        summary["runs"].append(
            {"run_id": result["run_id"], "status": status, "comparison_group": group}
        )
        lines += [
            f"## {text(result['run_id'])}",
            "",
            f"Status: **{status}**. {text(result['outcome']['reason'])}",
            "",
        ]
        lines += [
            f"- Claim IDs: {', '.join(map(text, result['claim_ids'])) or 'unmapped'}",
            f"- Statement/relation: {text(s['statement'])} / {text(s['relation_version'])}",
            f"- Numerical semantics: {text(s['numerical_semantics'])}",
            f"- Backend/security: {text(s['backend'])} / {text(s['security_mode'])}",
            f"- Hardware: {text(canonical(hardware).strip())}",
            f"- Comparison group: {group}; separate groups must not be ranked together.",
            f"- Source: https://github.com/FZKML/fzkml/commit/{result['provenance']['source_commit']}",
            (
                f"- Workflow run: https://github.com/FZKML/fzkml/actions/runs/{result['provenance']['workflow_run']}"
                if result["provenance"].get("execution_kind") != "local"
                else "- Execution: local; no workflow run."
            ),
            f"- Raw repetitions: results.json, run {text(result['run_id'])}",
            "",
        ]
        for rep in result["repetitions"]:
            lines += [
                f"Repetition {text(rep['id'])}: {rep['status']}; attempt {rep['attempt']}; "
                f"timeout {rep['timeout']}; excluded {rep['excluded']}; "
                f"quality {rep['quality']}. {text(rep['reason'])}",
                "",
            ]
            for measurement in rep["measurements"]:
                lines.append(
                    f"- Raw {measurement['phase']} {measurement['quantity']}: "
                    f"{measurement['value']} {measurement['unit']}"
                )
        for m in result["metrics"]:
            label = f"{m['phase']} {m['quantity']} {m['aggregation']}"
            lines += [
                f"- {label}: {m['value']} {m['unit']}; repetitions "
                + ", ".join(map(text, m["repetition_ids"]))
            ]
            # Plot raw repetitions within each metric on its own labelled linear axis.
            values = [
                next(
                    v["value"]
                    for v in rep["measurements"]
                    if all(v[k] == m[k] for k in ("phase", "quantity", "unit"))
                )
                for rep in result["repetitions"]
                if rep["id"] in m["repetition_ids"]
            ]
            high = max(values) or 1
            y = 40 + len(plots) * 100
            points = " ".join(
                f"{12 + j * 450 / max(1, len(values) - 1):.3f},{y + 65 - v * 50 / high:.3f}"
                for j, v in enumerate(values)
            )
            markers = "".join(
                f'<circle cx="{12 + j * 450 / max(1, len(values) - 1):.3f}" '
                f'cy="{y + 65 - v * 50 / high:.3f}" r="3" fill="#275e8e"/>'
                for j, v in enumerate(values)
            )
            plots.append(
                f'<text x="12" y="{y}">{html.escape(result["run_id"] + " " + label)}</text>'
                f'<polyline points="{points}" fill="none" stroke="#275e8e"/>'
                + markers
                + f'<path d="M12 {y + 10} V{y + 65} H462" fill="none" stroke="#555"/>'
                f'<text x="490" y="{y + 30}">y: 0 to {high} {m["unit"]}; '
                f"x: repetition index; aggregate: {m['value']}</text>"
            )
        lines += ["", "Limitations:", ""] + ["- " + text(v) for v in result["limitations"]] + [""]
        if not result["metrics"]:
            lines += ["Costs/quality: not measured. No plotted values are inferred.", ""]
    markdown = "\n".join(lines) + "\n"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" '
        f'height="{max(90, 80 + len(plots) * 100)}" role="img">'
        "<title>Independent metric panels; no cross-group leaderboard</title>"
        + ("".join(plots) or '<text x="12" y="40">No measured metrics; experiments not run.</text>')
        + "</svg>\n"
    )
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "img-src 'self'; style-src 'unsafe-inline'\">"
        "<title>FZKML research report</title><body><pre>"
        + html.escape(markdown)
        + '</pre><img src="plots.svg" alt="Independent measurement panels"></body></html>\n'
    )
    return {
        "results.json": canonical(bundle),
        "claims.json": canonical(claims),
        "summary.json": canonical(summary),
        "report.md": markdown,
        "report.html": page,
        "plots.svg": svg,
    }


def write_report(bundle: dict[str, Any], claims: dict[str, Any], destination: Path) -> None:
    rendered = render(bundle, claims)
    sizes = [len(value.encode()) for value in rendered.values()]
    require(max(sizes) <= MAX_FILE and sum(sizes) <= MAX_TOTAL, "rendered-size-limit")
    # Never follow an existing output path, including an attacker-created symlink.
    destination.mkdir(parents=False, exist_ok=False)
    for name, contents in rendered.items():
        with (destination / name).open("x", encoding="utf-8") as stream:
            stream.write(contents)
    verify_report(destination)


def verify_report(directory: Path) -> None:
    from .validate import bounded_file, load

    validate_artifacts(directory)
    expected = render(load(directory / "results.json"), load(directory / "claims.json"))
    require(set(expected) == ARTIFACTS, "report-path-allowlist")
    for name, value in expected.items():
        require(bounded_file(directory / name) == value.encode(), "noncanonical-report")
