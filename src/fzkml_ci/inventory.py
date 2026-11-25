"""Lock-derived transitive SPDX inventory; unresolved rights remain visible."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .research import write
from .validate import ROOT, require


def generate(root: Path = ROOT) -> dict[str, Any]:
    lock = tomllib.loads((root / "uv.lock").read_text())
    rust = tomllib.loads((root / "Cargo.lock").read_text())
    licenses: dict[tuple[str, str], str] = {}
    # Consume reviewed provenance inventories, including the CI foundation inventory when present.
    for path in sorted((root / "compliance").glob("*dependencies.json")):
        document = json.loads(path.read_text())
        for dep in document.get("dependencies", []):
            licenses[(dep["name"].lower().replace("_", "-"), dep["version"])] = dep.get(
                "license", dep.get("license_expression", "NOASSERTION")
            )
    packages = []
    findings = []
    all_packages = [("pypi", p) for p in lock["package"]]
    all_packages += [("cargo", p) for p in rust["package"]]
    tools = (root / "tools-requirements.txt").read_text()
    for name, version in re.findall(r"^([A-Za-z0-9_-]+)==([^\s]+)", tools, re.MULTILINE):
        all_packages.append(("pypi", {"name": name, "version": version}))
    seen = set()
    for ecosystem, package in all_packages:
        name, version = package["name"], package["version"]
        identity = (ecosystem, name, version)
        if identity in seen:
            continue
        seen.add(identity)
        identifier = f"SPDXRef-{ecosystem}-{name}"
        license_id = (
            "Apache-2.0"
            if name in {"fzkml-core", "fzkml-ci", "fzkml-models"}
            else licenses.get((name.lower().replace("_", "-"), version), "NOASSERTION")
        )
        if license_id == "NOASSERTION":
            findings.append(
                {
                    "package": identifier,
                    "status": "unresolved-license",
                    "action": "Review upstream terms and retain required notices.",
                }
            )
        location = package.get("sdist", {}).get("url", "NOASSERTION")
        entry = {
            "name": name,
            "SPDXID": identifier,
            "versionInfo": version,
            "downloadLocation": location,
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": license_id,
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:{ecosystem}/{name}@{version}",
                }
            ],
        }
        packages.append(entry)
    digests = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ["uv.lock", "Cargo.lock", "tools-requirements.txt"]
    }
    document_id = hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "fzkml-locked-dependencies",
        "documentNamespace": f"https://github.com/FZKML/fzkml/sbom/{document_id}",
        "creationInfo": {"creators": ["Tool: fzkml-ci-0.1.0"], "created": "2026-11-24T00:00:00Z"},
        "packages": packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": package["SPDXID"],
            }
            for package in packages
        ],
    }
    require(len(packages) <= 1000, "inventory-package-limit")
    return {
        "version": 1,
        "lock_digests": digests,
        "sbom": sbom,
        "findings": findings,
        "limitations": [
            "Includes all lock packages, including platform-conditional dependencies.",
            "No compatibility/rights conclusion; datasets and model terms are separate.",
            "Hosted runner tools and stdlib are external infrastructure.",
        ],
    }


if __name__ == "__main__":
    document = generate()
    write(ROOT / "compliance" / "dependency-inventory.json", document)
    write(ROOT / "dist" / "dependencies.spdx.json", document["sbom"])
