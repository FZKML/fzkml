"""Capture one honest local CPU transition proof and process peak memory."""

from __future__ import annotations

import json
import os
import platform
import resource
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    binary = ROOT / "target/release/fzkml-private"
    result = subprocess.run(
        [str(binary), "smoke", "0"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or "private-profile-failed")
    record = json.loads(result.stdout)
    if not record.get("verified") or record.get("proof_bytes") != 128:
        raise SystemExit("private-proof-profile-invalid")
    raw_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_bytes = int(raw_peak if sys.platform == "darwin" else raw_peak * 1024)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    record.update(
        peak_rss_bytes=peak_bytes,
        source_commit=commit,
        source_dirty=dirty,
        workflow_ref=os.environ.get("GITHUB_REF", "local"),
        workflow_run=int(os.environ.get("GITHUB_RUN_ID", "0")),
        workflow_attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
        platform=platform.platform(),
        architecture=platform.machine(),
        evidence_class="single-run-public-synthetic-diagnostic",
        limitation=(
            "One noisy tiny public fixture run; no performance, utility, production "
            "security, constant-time, or private-training claim."
        ),
    )
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/private-transition-profile.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
