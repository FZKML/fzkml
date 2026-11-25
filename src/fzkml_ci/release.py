"""Digest inventory and independent, identity-constrained release verification."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .research import proof_results, write
from .validate import ROOT, Invalid, load, require, require_publication

REPOSITORY = "FZKML/fzkml"
WORKFLOW = "FZKML/fzkml/.github/workflows/release.yml"
FILES = {"libfzkml_core.rlib", "results.json", "dependencies.json", "REPRODUCE.md", "source.tar.gz"}


def sha(path: Path) -> str:
    # Release artifacts have a distinct 16 MiB cap; never follow links.
    require(path.is_file() and not path.is_symlink(), "release-file-type")
    require(path.stat().st_size <= 16 * 1024 * 1024, "release-size-limit")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory: Path, commit: str, tag: str) -> dict[str, Any]:
    require(re.fullmatch(r"[a-f0-9]{40}", commit) is not None, "release-source-sha")
    require(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) is not None, "release-tag")
    require({p.name for p in directory.iterdir()} == FILES, "release-file-set")
    proof_results(load(directory / "results.json"))
    require_publication(load(directory / "results.json"))
    return {
        "version": 1,
        "repository": REPOSITORY,
        "workflow": WORKFLOW,
        "commit": commit,
        "tag": tag,
        "status": "built-unattested",
        "files": {name: sha(directory / name) for name in sorted(FILES)},
        "retention": {
            "location": f"https://github.com/{REPOSITORY}/releases/tag/{tag}",
            "policy": "Keep tagged evidence indefinitely; mirror before removal.",
        },
        "limitations": [
            "Provenance does not establish algorithmic security or performance.",
            "rlib is an experimental Rust library, not a protocol implementation.",
        ],
    }


def verify(directory: Path, commit: str, tag: str, attest: bool = True) -> None:
    manifest = load(directory / "manifest.json")
    require(
        set(manifest)
        == {
            "version",
            "repository",
            "workflow",
            "commit",
            "tag",
            "status",
            "files",
            "retention",
            "limitations",
        },
        "release-manifest-fields",
    )
    require(
        manifest["version"] == 1
        and manifest["repository"] == REPOSITORY
        and manifest["workflow"] == WORKFLOW
        and manifest["commit"] == commit
        and manifest["tag"] == tag
        and manifest["status"] == "built-unattested",
        "release-source-policy",
    )
    require(set(manifest["files"]) == FILES, "release-inventory")
    require(
        {p.name for p in directory.iterdir()} == FILES | {"manifest.json"}, "release-extra-file"
    )
    for name in FILES:
        require(sha(directory / name) == manifest["files"][name], "release-digest-mismatch")
    proof_results(load(directory / "results.json"))
    require_publication(load(directory / "results.json"))
    require(
        all(
            row["provenance"]["source_commit"] == commit
            for row in load(directory / "results.json")["results"]
        ),
        "results-source-mismatch",
    )
    if attest:
        # Caller supplies independently reviewed commit/tag; do not derive policy from the bundle.
        for name in ["manifest.json", "libfzkml_core.rlib"]:
            subprocess.run(
                [
                    "gh",
                    "attestation",
                    "verify",
                    str(directory / name),
                    "--repo",
                    REPOSITORY,
                    "--signer-workflow",
                    WORKFLOW,
                    "--source-digest",
                    commit,
                    "--source-ref",
                    f"refs/tags/{tag}",
                    "--deny-self-hosted-runners",
                ],
                check=True,
            )


def build(directory: Path, tag: str) -> None:
    require(not directory.exists(), "release-directory-must-be-new")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    proof_results(load(ROOT / "research" / "proof-results.json"))
    directory.mkdir(parents=True)
    for source, target in [
        ("target/release/libfzkml_core.rlib", "libfzkml_core.rlib"),
        ("research/proof-results.json", "results.json"),
        ("compliance/dependency-inventory.json", "dependencies.json"),
        ("docs/REPRODUCE.md", "REPRODUCE.md"),
    ]:
        shutil.copyfile(ROOT / source, directory / target)
    with (directory / "source.tar.gz").open("wb") as stream:
        subprocess.run(
            ["git", "archive", "--format=tar.gz", "HEAD"], cwd=ROOT, stdout=stream, check=True
        )
    write(directory / "manifest.json", inventory(directory, commit, tag))
    verify(directory, commit, tag, attest=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["build", "verify"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    try:
        if args.operation == "build":
            build(args.directory, args.tag)
        else:
            require(args.commit is not None, "expected-commit-required")
            require(re.fullmatch(r"[a-f0-9]{40}", args.commit) is not None, "expected-commit")
            require(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.tag) is not None, "expected-tag")
            verify(args.directory, args.commit, args.tag)
    except (Invalid, OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        print("release verification failed", file=sys.stderr)
        return 1
    print(
        "release built (unattested)" if args.operation == "build" else "release provenance verified"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
