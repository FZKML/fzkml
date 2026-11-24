"""Integrate uv/Rust manifests into the foundation's explicit dependency inventory."""

import hashlib
import json
import re
import tomllib
from pathlib import Path


def validate_ci_inventory(root: Path) -> None:
    lock = tomllib.loads((root / "uv.lock").read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())
    inventory = json.loads((root / "compliance/ci-dependencies.json").read_text())
    deps = {(d["name"], d["version"]): d for d in inventory["dependencies"]}
    packages = [p for p in lock["package"] if p["name"] != "fzkml-ci"]
    if set(deps) != {(p["name"], p["version"]) for p in packages} | {("uv", "0.9.11")}:
        raise ValueError("CI dependency inventory differs from uv lock")
    for p in packages:
        entry = deps[p["name"], p["version"]]
        artifacts = [p["sdist"]] + p["wheels"]
        if not {a["hash"].removeprefix("sha256:") for a in artifacts} <= set(
            entry["artifact_hashes"]
        ):
            raise ValueError("CI dependency artifact hash differs from inventory")
    for dep in deps.values():
        if not dep["license_files"] or not dep["license_expression"]:
            raise ValueError("CI dependency license missing")
        for notice in dep["license_files"]:
            path = root / notice["path"]
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("CI dependency notice path invalid")
            if hashlib.sha256(path.read_bytes()).hexdigest() != notice["sha256"]:
                raise ValueError("CI dependency notice digest differs")
    direct = project["project"]["dependencies"] + project["dependency-groups"]["dev"]
    for requirement in direct:
        if "==" not in requirement or tuple(requirement.split("==")) not in deps:
            # PyPI names are case-insensitive and normalize underscores/hyphens.
            normalized = requirement.lower().replace("_", "-")
            if "==" not in normalized or tuple(normalized.split("==")) not in deps:
                raise ValueError("CI direct dependency must match reviewed exact pin")
    bootstrap = (root / "tools-requirements.txt").read_text()
    hashes = set(re.findall(r"--hash=sha256:([a-f0-9]{64})", bootstrap))
    if not hashes or hashes != set(deps["uv", "0.9.11"]["artifact_hashes"]):
        raise ValueError("uv bootstrap hash differs from inventory")
    # No third-party Rust crates are currently approved. New ones need inventory review.
    cargo = tomllib.loads((root / "Cargo.lock").read_text())
    if cargo["package"] != [{"name": "fzkml-core", "version": "0.1.0"}]:
        raise ValueError("new Rust dependency requires inventory integration")
