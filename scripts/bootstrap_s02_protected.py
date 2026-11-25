#!/usr/bin/env python3
"""Explicit optional network setup; never invoked automatically by PR CPU tests."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    lock = json.loads((ROOT / "experiments/s02-protected/runtime-lock.json").read_text())
    tools = ROOT / ".tools"
    tools.mkdir(exist_ok=True)
    source = tools / "co-snarks"
    if not source.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                lock["tag"],
                lock["repository"],
                str(source),
            ],
            check=True,
        )
    actual = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != lock["source_commit"]:
        raise ValueError("external-source-commit-mismatch")
    key = platform.system() + "-" + platform.machine()
    artifact = lock["archives"][key]
    runtime = tools / "co-runtime"
    runtime.mkdir(exist_ok=True)
    archive = runtime / "runtime.tar.gz"
    if (
        not archive.exists()
        or hashlib.sha256(archive.read_bytes()).hexdigest() != artifact["sha256"]
    ):
        urllib.request.urlretrieve(artifact["url"], archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != artifact["sha256"]:
        raise ValueError("external-runtime-digest-mismatch")
    with tarfile.open(archive) as tar:
        member = tar.getmember("co-circom")
        if not member.isfile() or member.size > 100_000_000:
            raise ValueError("unexpected-runtime-archive")
        incoming = tar.extractfile(member)
        if incoming is None:
            raise ValueError("missing-runtime")
        with (runtime / "co-circom").open("wb") as output:
            shutil.copyfileobj(incoming, output)
        (runtime / "co-circom").chmod(0o755)
    npm = tools / "snarkjs"
    npm.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "experiments/s02-protected/snarkjs-lock.json", npm / "package-lock.json")
    (npm / "package.json").write_text(
        json.dumps({"private": True, "dependencies": {"snarkjs": "0.7.5"}})
    )
    subprocess.run(
        ["npm", "ci", "--prefix", str(npm), "--ignore-scripts", "--no-audit", "--no-fund"],
        check=True,
    )
    print("External experimental runtimes installed from pinned sources; not redistributed.")


if __name__ == "__main__":
    main()
