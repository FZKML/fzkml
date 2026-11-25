"""Conservative policy for this repository's small public CPU workflows.

This is a regression check, not a general GitHub Actions security analyzer.
Workflow ownership and protected refs remain administrator-enforced controls.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from pathlib import Path
from typing import Any

import yaml

from .validate import ROOT, bounded_file, load, require

RESEARCH_WORKFLOWS = {
    "cpu.yml",
    "research.yml",
    "research-reconcile.yml",
    "codeql.yml",
    "gpu.yml",
    "release.yml",
    "language.yml",
    "reports.yml",
}


def check_research_workflow(name: str, data: bytes) -> None:
    # These new trust boundaries use reviewed exact templates. Changes to both
    # workflow and digest registry require CODEOWNERS review, just like policy code.
    approved = load(ROOT / "ci" / "workflow-digests.json")
    require(name in RESEARCH_WORKFLOWS, "unreviewed-research-workflow")
    require(hashlib.sha256(data).hexdigest() == approved.get(name), "workflow-review-required")


ACTIONS = {
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
    "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9",
}


def check_workflow(workflow: dict[str, Any]) -> None:
    # BaseLoader preserves the YAML key 'on' and treats all scalar values as strings.
    triggers = workflow.get("on")
    require(isinstance(triggers, dict), "explicit-workflow-triggers-required")
    assert isinstance(triggers, dict)
    require(
        bool(triggers)
        and set(triggers) <= {"pull_request", "push", "workflow_dispatch", "schedule"},
        "unsafe-trigger",
    )
    require(workflow.get("permissions") == {}, "workflow-permissions-must-be-empty")
    serialized = str(workflow)
    require(
        not re.search(r"secrets\.|self-hosted|restore-cache|save-cache|actions/cache", serialized),
        "privilege-or-cache-boundary",
    )
    require("env" not in workflow and "defaults" not in workflow, "global-execution-configuration")
    jobs = workflow.get("jobs", {})
    require(isinstance(jobs, dict) and 0 < len(jobs) <= 6, "job-count-limit")
    if "schedule" in triggers:
        require(
            triggers["schedule"] == [{"cron": "37 4 * * 1"}] and set(jobs) == {"language"},
            "schedule-not-reviewed",
        )
    for job_name, job in jobs.items():
        require(isinstance(job, dict) and "uses" not in job, "reusable-job-not-reviewed")
        require(job.get("runs-on") == "ubuntu-24.04", "ephemeral-runner-required")
        timeout = job.get("timeout-minutes", "")
        require(str(timeout).isdigit() and 1 <= int(timeout) <= 30, "bounded-timeout-required")
        require(job.get("permissions") == {"contents": "read"}, "job-read-only-required")
        if "pull_request" in triggers:
            require("environment" not in job, "untrusted-environment")
        if "environment" in job:
            require(job["environment"] == "public-reports", "publication-environment")
            require(triggers.get("push") == {"branches": ["main"]}, "protected-report-ref")
            require(
                job.get("if") == "github.ref == 'refs/heads/main'", "protected-report-condition"
            )
        strategy = job.get("strategy", {})
        if strategy:
            require(
                set(strategy) <= {"matrix", "max-parallel", "fail-fast"}, "strategy-not-reviewed"
            )
            matrix = strategy.get("matrix", {})
            require(isinstance(matrix, dict) and bool(matrix), "matrix-shape")
            require(not {"include", "exclude"} & matrix.keys(), "matrix-include-not-reviewed")
            size = 1
            for values in matrix.values():
                require(
                    isinstance(values, list) and 0 < len(values) <= 8, "bounded-matrix-required"
                )
                size *= len(values)
            require(size <= 16, "matrix-size-limit")
        steps = job.get("steps", [])
        require(isinstance(steps, list) and 0 < len(steps) <= 20, "step-count-limit")
        uploaded = False
        for step in steps:
            require(isinstance(step, dict), "step-shape")
            action = step.get("uses")
            if action:
                require(action in ACTIONS, "action-not-allowlisted-or-pinned")
                config = step.get("with", {})
                if action.startswith("actions/checkout@"):
                    allowed = [{"persist-credentials": "false"}]
                    if job_name in {"governance", "dco"}:
                        allowed.append({"persist-credentials": "false", "fetch-depth": "0"})
                    require(config in allowed, "checkout-trust-boundary")
                elif action.startswith("actions/setup-python@"):
                    require(config == {"python-version": "3.11.14"}, "python-pin-or-cache-policy")
                else:
                    require(not uploaded, "multiple-artifact-uploads")
                    require(
                        config
                        == {
                            "name": "public-report-${{ github.sha }}",
                            "path": "dist/",
                            "retention-days": "7",
                            "if-no-files-found": "error",
                            "include-hidden-files": "false",
                        },
                        "artifact-upload-policy",
                    )
                    require(
                        "environment" in job and "pull_request" not in triggers,
                        "trusted-upload-required",
                    )
                    require(step.get("if") is None, "upload-condition-not-reviewed")
                    uploaded = True
            else:
                script = step.get("run", "")
                require(isinstance(script, str) and bool(script), "run-step-required")
                require("${{" not in script, "expression-in-shell")
                require(not uploaded, "execution-after-upload")
        if uploaded:
            require(
                steps[-2].get("run") == "./scripts/verify-public-report",
                "upload-without-verification",
            )


def check_repository(directory: Path = ROOT / ".github" / "workflows") -> None:
    paths = sorted(itertools.chain(directory.glob("*.yml"), directory.glob("*.yaml")))
    require(bool(paths), "no-workflows")
    for path in paths:
        require(path.name in RESEARCH_WORKFLOWS | {"governance.yml"}, "workflow-not-registered")
        data = bounded_file(path)
        if path.name in RESEARCH_WORKFLOWS:
            check_research_workflow(path.name, data)
            if path.name != "cpu.yml":
                continue
        workflow = yaml.load(data, Loader=yaml.BaseLoader)
        require(isinstance(workflow, dict), "workflow-shape")
        check_workflow(workflow)
