#!/usr/bin/env python3
"""Check the local retained companion; optional real verification never accepts a mock."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from python.fzkml_math.collaborative import public_transcript, sha, verify

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--external", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve()
    report = json.loads((directory / "run.json").read_text())
    Draft202012Validator(
        json.loads((ROOT / "schemas/s02-protected-run-1.0.0.json").read_text())
    ).validate(report)
    if report["source_dirty"]:
        raise ValueError("dirty-source-is-not-retained-conformance-evidence")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", report["source_commit"], "HEAD"],
        cwd=ROOT,
        check=True,
    )
    for name, digest in report["digests"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("input-or-lock-drift:" + name)
    manifest = json.loads((directory / "proof-manifest.json").read_text())
    if manifest["source_commit"] != report["source_commit"] or len(manifest["proofs"]) != 9:
        raise ValueError("public-proof-inventory-mismatch")
    binary = ROOT / ".tools/co-runtime/co-circom"
    vk = ROOT / ".tools/co-snarks/test_vectors/Groth16/bn254/multiplier2/verification_key.json"
    if args.external:
        if (
            sha(binary) != report["software"]["coCircom_binary_sha256"]
            or sha(vk) != manifest["verification_key_sha256"]
        ):
            raise ValueError("external-verifier-or-key-mismatch")
    for row in manifest["proofs"]:
        paths = []
        for kind in ("proof", "output"):
            relative = Path(row[kind])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe-artifact-path")
            p = directory / relative
            if p.is_symlink() or sha(p) != row[kind + "_sha256"]:
                raise ValueError("public-artifact-integrity-failure")
            paths.append(p)
        public_transcript(*paths)
        if args.external:
            if not verify(binary, paths[0], vk, paths[1]):
                raise ValueError("retained-real-proof-rejected")
            with tempfile.TemporaryDirectory() as d:
                wrong = Path(d) / "wrong.json"
                wrong.write_text('["34"]')
                if verify(binary, paths[0], vk, wrong):
                    raise ValueError("wrong-output-accepted")
    print(
        "Retained source/digests and9 public proofs checked; real verifier used="
        + str(args.external)
    )


if __name__ == "__main__":
    main()
