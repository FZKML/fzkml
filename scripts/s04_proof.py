"""CI-only adapter to Session 02's real native backend and independent oracle.

No core implementation changes, development receipts, public proof randomness,
or local fake workflow identities. The public fixture is explicitly synthetic.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.machinery
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from fzkml_ci.research import proof_results, write
from fzkml_ci.validate import ROOT, load, require


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def rejected(operation: Callable[[], bool]) -> bool:
    try:
        value = operation()
    except (ValueError, TypeError):
        return True
    return value is False


def check() -> dict[str, Any]:
    entire = time.perf_counter()
    from fzkml_native import CONTRACT_SHA256, CanonicalBatch, ResearchSession, _native

    from reference.numeric import encode, evaluate

    extension = Path(_native.__file__).resolve()
    require(
        any(str(extension).endswith(s) for s in importlib.machinery.EXTENSION_SUFFIXES),
        "native-extension-required",
    )
    require(extension.is_relative_to(Path(sys.prefix).resolve()), "fresh-native-wheel-required")
    contract = (ROOT / "specs/numeric-contract-v1.json").read_bytes()
    require(CONTRACT_SHA256 == hashlib.sha256(contract).hexdigest(), "compiled-relation-drift")
    fixture = load(ROOT / "assets/public/numeric-v1.json")
    require(fixture["contract_sha256"] == CONTRACT_SHA256, "golden-contract-drift")
    raw = encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1])
    golden = next(v for v in fixture["valid"] if v["canonical_hex"] == raw.hex())
    expected = evaluate(raw)
    require(expected == golden["expected"] and expected["output"] == 9, "independent-oracle-drift")
    batch = CanonicalBatch(raw)
    require(batch.evaluate() == expected["output"], "native-oracle-disagreement")
    preparation = time.perf_counter() - entire
    started = time.perf_counter()
    session = ResearchSession()
    setup = time.perf_counter() - started
    proved = session.prove(batch)
    started = time.perf_counter()
    require(session.verify(batch, proved) is True, "real-proof-verification-failed")
    verification = time.perf_counter() - started
    require(type(proved.proof) is bytes and len(proved.proof) == 128, "real-proof-encoding")
    changed = CanonicalBatch(encode(8, [16, -8, 24], [16, -16, 8], [2, 1, 1]))
    started = time.perf_counter()
    other = ResearchSession()
    negative_setup = time.perf_counter() - started
    started = time.perf_counter()
    negatives = {
        "changed-output": rejected(lambda: session.verify(batch, replace(proved, output=10))),
        "changed-public-count": rejected(lambda: session.verify(changed, proved)),
        # Call the native verifier directly: do not satisfy this via the Python key-id guard.
        "wrong-verifying-key": rejected(
            lambda: other._session.verify(raw, proved.output, proved.proof)
        ),
        "malformed-proof": rejected(
            lambda: session.verify(batch, replace(proved, proof=b"\x00" * 128))
        ),
        "trailing-proof-byte": rejected(
            lambda: session.verify(batch, replace(proved, proof=proved.proof + b"\x00"))
        ),
    }
    require(all(value is True for value in negatives.values()), "negative-proof-case-accepted")
    negative_verification = time.perf_counter() - started
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    record = {
        "version": 1,
        "backend": "ark-groth16-0.5.0-bn254",
        "proof_mode": "research-real",
        "assurance": "public-arithmetic-only",
        "source_commit": source,
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT
            )
        ),
        "adapter_digest": sha(Path(__file__).read_bytes()),
        "contract_digest": sha(contract),
        "program_digest": sha((ROOT / "crates/fzkml-core/src/lib.rs").read_bytes()),
        "circuit_digest": sha((ROOT / "crates/fzkml-core/src/proof.rs").read_bytes()),
        "native_extension_digest": sha(extension.read_bytes()),
        "parameters_digest": "sha256:" + session.parameters_id,
        "key_digest": "sha256:" + session.key_id,
        "verified": True,
        "proof_bytes": len(proved.proof),
        "expected_output": 9,
        "oracle_matches": True,
        "negatives": negatives,
        "seconds": {
            "prepare": preparation,
            "negative-setup": negative_setup,
            "negative-verify": negative_verification,
            "end-to-end": time.perf_counter() - entire,
            "setup": setup,
            "witness": proved.witness_seconds,
            "prove": proved.proving_seconds,
            "verify": verification,
        },
        "workflow_run": int(os.environ["GITHUB_RUN_ID"])
        if os.environ.get("GITHUB_RUN_ID")
        else None,
        "limitations": [
            "Fresh local research setup; no production setup or security claim.",
            "All inputs public; no private-transition/protected-protocol assurance.",
            "One proof shared across three cases; these are not independent proof samples.",
            "Logical proof bytes exclude keys/transport; peak process RSS is unavailable.",
            "Adapter wall time includes negatives; build/install wall time is in the journal.",
        ],
    }
    return record


def result_bundle(record: dict[str, Any]) -> dict[str, Any]:
    require(record["source_dirty"] is False, "dirty-source-not-publishable")
    local = record["workflow_run"] is None
    version = "1.1.0"
    base = load(ROOT / "examples/results.json")["results"][0]
    results = []
    for name in ["tiny-proof", "native-circuit-conformance", "negative-cases"]:
        row = copy.deepcopy(base)
        row["schema_version"] = version
        row.update(run_id=f"synthetic:s04-{name}")
        row["scenario"].update(
            id=name,
            statement="public-exact-linear-three-client",
            relation_version="fzknum-1.0.0",
            numerical_semantics="fixed16-rne",
            backend=record["backend"],
            security_mode="research",
            **{
                k: record[k]
                for k in ["program_digest", "circuit_digest", "parameters_digest", "key_digest"]
            },
        )
        for kind in ["model", "dataset"]:
            row["scenario"][kind] = {
                "id": f"synthetic:s04-{kind}",
                "version": "numeric-v1",
                "digest": sha((ROOT / "assets/public/numeric-v1.json").read_bytes()),
                "license": "Apache-2.0",
                "publication": "permitted",
            }
        row["provenance"].update(
            source_commit=record["source_commit"],
            workflow_run=record["workflow_run"],
            workflow_path=next(
                (
                    p
                    for p in [
                        ".github/workflows/cpu.yml",
                        ".github/workflows/reports.yml",
                        ".github/workflows/language.yml",
                    ]
                    if p + "@" in os.environ.get("GITHUB_WORKFLOW_REF", "")
                ),
                None,
            ),
            toolchain="rust-1.85.1-python-3.11.14",
            dependency_digest=sha(
                (ROOT / "Cargo.lock").read_bytes() + (ROOT / "uv.lock").read_bytes()
            ),
        )
        if local:
            row["provenance"].update(execution_kind="local", workflow_path=None, workflow_run=None)
        else:
            row["provenance"]["execution_kind"] = "github-actions"
            require(row["provenance"]["workflow_path"] is not None, "unsupported-workflow-identity")
        row["provenance"]["hardware"].update(
            cpu=platform.machine(),
            os=platform.system(),
            memory_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
            runner_image_revision=os.environ.get("ImageVersion", "unavailable"),
        )
        row["randomness"]["protocol_randomness"] = "private-not-recorded"
        row["outcome"] = {
            "status": "successful",
            "reason": "Fresh real Groth16 verification and mandatory negatives passed.",
        }
        phases = {
            "tiny-proof": {k: k for k in ["setup", "witness", "prove", "verify", "end-to-end"]},
            "native-circuit-conformance": {"prepare": "prepare"},
            "negative-cases": {"setup": "negative-setup", "verify": "negative-verify"},
        }[name]
        measurements = [
            {"phase": phase, "quantity": "time", "unit": "s", "value": record["seconds"][key]}
            for phase, key in phases.items()
        ]
        if name == "tiny-proof":
            measurements.append(
                {
                    "phase": "communicate",
                    "quantity": "communication",
                    "unit": "byte",
                    "value": record["proof_bytes"],
                }
            )
        row["repetitions"] = [
            {
                "id": "rep1",
                "attempt": 1,
                "status": "successful",
                "timeout": False,
                "excluded": False,
                "reason": "Mandatory case executed; no skip/mock allowance.",
                "measurements": measurements,
                "quality": "not-measured",
            }
        ]
        row["metrics"] = []
        row["limitations"] = record["limitations"]
        row["publication_review"] = {
            "approved": False,
            "review_id": "synthetic:reviewed-public-fixture-policy",
        }
        results.append(row)
    bundle = {"schema_version": version, "results": results}
    proof_results(bundle)
    return bundle


def main() -> int:
    (ROOT / "research/proof-check.json").unlink(missing_ok=True)
    (ROOT / "research/proof-results.json").unlink(missing_ok=True)
    try:
        record = check()
        write(ROOT / "research/proof-check.json", record)
        if record["workflow_run"] is not None or record["source_dirty"] is False:
            write(ROOT / "research/proof-results.json", result_bundle(record))
        print(
            "Real Groth16 verified; five mandatory negatives rejected; independent golden output=9."
        )
        print("Assurance: public arithmetic only; private/protocol/DP claims remain unavailable.")
        return 0
    except Exception:
        print("genuine-proof check failed; no successful receipt emitted")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
