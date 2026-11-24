"""Validate explicit file coverage, pinned dependencies, and public asset provenance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_path(root, relative):
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError("unsafe path: " + relative)
    if any(part.lower() in {"private", "restricted", ".git"} for part in p.parts):
        raise ValueError("excluded path: " + relative)
    candidate = root / p
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("symlink or escaped path: " + relative)
    if not candidate.is_file():
        raise ValueError("missing file: " + relative)
    return candidate


def need(record, fields, context):
    missing = [f for f in fields if f not in record or record[f] in (None, "", [])]
    if missing:
        raise ValueError(context + ": missing " + ", ".join(missing))


def repository_files(root):
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "-z"], cwd=root
    )
    return set(raw.decode().rstrip("\0").split("\0")) - {""}


def validate(root, paths=None):
    coverage = read_json(root / "compliance/files.json")
    known = set(coverage["approved_licenses"])
    files = coverage["files"]
    actual = repository_files(root) if paths is None else set(paths)
    if actual != set(files):
        raise ValueError("license coverage gap: missing=%s stale=%s" %
                         (sorted(actual - set(files)), sorted(set(files) - actual)))
    for name, record in files.items():
        path = public_path(root, name)
        need(record, ["license", "origin", "attribution", "license_files"], name)
        if record["license"] not in known:
            raise ValueError("unreviewed license: " + name)
        for notice in record["license_files"] + record.get("notice_files", []):
            public_path(root, notice)
            if notice not in files:
                raise ValueError("uninventoried license/notice: " + notice)
        if record["origin"] == "upstream":
            need(record, ["source", "version", "sha256", "modifications"], name)
            if digest(path) != record["sha256"]:
                raise ValueError("upstream checksum mismatch: " + name)
        elif record["origin"] != "original":
            raise ValueError("unknown file origin: " + name)

    deps = read_json(root / "compliance/dependencies.json")
    for dep in deps["dependencies"]:
        need(dep, ["name", "version", "source", "license", "scope", "notices",
                   "sha256", "artifact_hashes", "license_files"], "dependency")
        if dep["license"] not in known or not re.fullmatch(r"[a-f0-9]{64}", dep["sha256"]):
            raise ValueError("unknown license or invalid checksum: " + dep["name"])
        if dep["scope"] != "development-only; not distributed":
            raise ValueError("distribution scope needs review: " + dep["name"])
        for license_file in dep["license_files"]:
            public_path(root, license_file)
    requirements = []
    lock = (root / "requirements-dev.txt").read_text().replace("\\\n", " ")
    for line in lock.splitlines():
        if line and not line.startswith("#"):
            parts = line.split()
            requirements.append(parts[0])
            dep = next((d for d in deps["dependencies"]
                        if d["name"] + "==" + d["version"] == parts[0]), None)
            if dep is None or set(parts[1:]) != {"--hash=sha256:" + h for h in dep["artifact_hashes"]}:
                raise ValueError("dependency artifact hash lock differs from inventory")
    pinned = sorted(d["name"] + "==" + d["version"] for d in deps["dependencies"])
    if sorted(requirements) != pinned:
        raise ValueError("dependency inventory differs from pinned requirements")
    # Additional runtime/build package manifests need an explicit new inventory integration.
    for name in actual:
        basename = Path(name).name
        if (basename in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod",
                         "Pipfile", "setup.py", "setup.cfg", "poetry.lock"}
                or (basename.startswith("requirements") and name != "requirements-dev.txt")):
            raise ValueError("new package/dependency manifest requires inventory integration: " + name)

    manifest = read_json(root / "assets/manifest.json")
    ids = set()
    registered = set()
    for asset in manifest["assets"]:
        need(asset, ["id", "kind", "source", "version", "path", "sha256", "terms",
                     "attribution", "intended_use", "permissions", "review"], "asset")
        if asset["id"] in ids or asset["path"] in registered:
            raise ValueError("duplicate asset id/path")
        ids.add(asset["id"])
        registered.add(asset["path"])
        permissions = asset["permissions"]
        for action in ("download", "experiment", "repository", "release", "generated_outputs"):
            if permissions.get(action) not in ("allowed", "forbidden", "review-required"):
                raise ValueError("missing explicit asset permission: " + action)
        if permissions["repository"] != "allowed" or permissions["release"] != "allowed":
            raise ValueError("restricted/unapproved asset cannot enter public source archive")
        if asset["review"].get("status") != "approved":
            raise ValueError("asset terms review is unresolved")
        need(asset["review"], ["reviewer", "date", "decision"], "asset review")
        need(asset["terms"], ["license", "text"], "asset terms")
        if asset["terms"]["license"] not in known:
            raise ValueError("unknown asset terms")
        public_path(root, asset["terms"]["text"])
        if asset["kind"] == "synthetic-fixture":
            need(asset, ["generation", "source_inputs"], "synthetic fixture")
            need(asset["generation"], ["method", "configuration"], "generation")
        path = public_path(root, asset["path"])
        if asset["path"] not in files or digest(path) != asset["sha256"]:
            raise ValueError("asset checksum/coverage mismatch: " + asset["id"])
    # These directories are reserved for inventoried data/model/generated payloads.
    payloads = {p for p in actual if p.startswith(("assets/public/", "tests/fixtures/",
                                                 "models/", "checkpoints/", "datasets/"))}
    if payloads != registered:
        raise ValueError("asset registry coverage gap: " + str(sorted(payloads ^ registered)))
    return {"files": len(files), "dependencies": len(deps["dependencies"]), "assets": len(ids)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.root), sort_keys=True))
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print("governance check failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
