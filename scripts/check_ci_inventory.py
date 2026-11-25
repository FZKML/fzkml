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
        artifacts = ([p["sdist"]] if "sdist" in p else []) + p.get("wheels", [])
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
    direct = project["project"]["dependencies"] + [
        dependency for group in project["dependency-groups"].values() for dependency in group
    ]
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
    cargo = tomllib.loads((root / "Cargo.lock").read_text())
    local = {(p["name"], p["version"]) for p in cargo["package"] if "source" not in p}
    if local != {("fzkml-core", "0.1.0"), ("fzkml-python", "0.1.0"), ("fzkml-models", "0.1.0")}:
        raise ValueError("local Rust package metadata differs from reviewed workspace")
    native = json.loads((root / "compliance/rust-dependencies.json").read_text())
    registry = {(d["name"], d["version"]): d for d in native["dependencies"]}
    locked = {(p["name"], p["version"]): p for p in cargo["package"] if "source" in p}
    if registry.keys() != locked.keys():
        raise ValueError("Rust dependency inventory differs from Cargo.lock")
    for key, package in locked.items():
        entry = registry[key]
        if entry["sha256"] != package["checksum"] or entry["source"] != package["source"]:
            raise ValueError("Rust source checksum differs from inventory")
        if not entry["selected_license"] or not entry["license_files"]:
            raise ValueError("Rust dependency licensing missing")
        for notice in entry["license_files"]:
            path = root / notice["path"]
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Rust notice path invalid")
            if hashlib.sha256(path.read_bytes()).hexdigest() != notice["sha256"]:
                raise ValueError("Rust notice checksum differs")
