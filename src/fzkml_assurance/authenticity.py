"""CI-15: controller-owned native verifier, never receipt exit-code trust."""

from __future__ import annotations

import copy
import json
import os
import platform
import struct
import subprocess
import time
from typing import Any

from fzkml_ci.validate import ROOT, load, require, validate_bundle
from reference.numeric import encode

from .common import check_schema, file_sha, provenance, save, sha

CASES = [
    "positive",
    "development",
    "mock",
    "substituted-key",
    "forged-key-tag",
    "fake-proof",
    "changed-output",
    "trailing-byte",
    "skipped",
    "unsupported",
    "canceled",
]
CRYPTO_CASES = {"positive", "forged-key-tag", "fake-proof", "changed-output", "trailing-byte"}
FIXTURE = "assets/public/ci15-candidate-v1.json"


def validate_native(value: Any, require_candidate: bool = True) -> None:
    check_schema(value, "auth-native")
    require(
        value["program_digest"] == file_sha("crates/fzkml-assurance/src/main.rs")
        and value["dependency_digest"] == file_sha("Cargo.lock")
        and value["contract_digest"] == file_sha("specs/numeric-contract-v1.json")
        and value["core_digest"]
        == sha(
            (ROOT / "crates/fzkml-core/src/lib.rs").read_bytes()
            + (ROOT / "crates/fzkml-core/src/proof.rs").read_bytes()
        ),
        "authenticity-stale-program-or-contract",
    )
    require(
        value["controller_key_digest"] != "0" * 64 and value["parameters_digest"] != "0" * 64,
        "authenticity-real-setup-required",
    )
    require([r["case"] for r in value["cases"]] == CASES, "authenticity-negative-coverage")
    for row in value["cases"]:
        name = row["case"]
        require(
            row["mode"] == (name if name in {"development", "mock"} else "research-real")
            and row["status"]
            == (name if name in {"skipped", "unsupported", "canceled"} else "executed")
            and row["proof_bytes"] == (129 if name == "trailing-byte" else 128),
            "authenticity-case-payload-binding",
        )
        require(
            row["accepted"] is (name == "positive") and row["nominal_exit_code"] == 0,
            "authenticity-zero-exit-rejection",
        )
        require(
            row["native_verifier_called"] is (name in CRYPTO_CASES),
            "authenticity-verifier-execution",
        )
        matches = row["declared_key_digest"] == value["controller_key_digest"]
        require(
            row["key_matches_controller"] is matches and matches is (name != "substituted-key"),
            "authenticity-key-substitution",
        )
    candidate = next(r for r in value["cases"] if r["case"] == value["candidate"])
    require(value["candidate_accepted"] is candidate["accepted"], "authenticity-candidate-binding")
    if require_candidate:
        require(
            value["candidate"] == "positive" and value["candidate_accepted"] is True,
            "authenticity-candidate-not-genuine",
        )


def result(state: dict[str, Any]) -> dict[str, Any]:
    native, p = state["native"], state["provenance"]
    require(
        state["status"] == "completed" and not p["source_dirty"],
        "clean-authenticity-result-required",
    )
    path = None if p["execution_kind"] == "local" else ".github/workflows/cpu.yml"
    require(
        path is None or ".github/workflows/cpu.yml@" in p["workflow_ref"],
        "authenticity-workflow-identity",
    )
    row = copy.deepcopy(load(ROOT / "examples/results.json")["results"][0])
    row.update(schema_version="1.1.0", run_id="synthetic:ci15-proof-authenticity", claim_ids=[])
    row["scenario"].update(
        id="ci15-proof-authenticity",
        statement="public-fzknum-controller-owned-key",
        relation_version="fzknum-1.0.0",
        numerical_semantics="fixed16-rne",
        backend=native["backend"],
        security_mode="research",
        program_digest="sha256:" + native["program_digest"],
        circuit_digest="sha256:" + native["core_digest"],
        parameters_digest="sha256:" + native["parameters_digest"],
        key_digest="sha256:" + native["controller_key_digest"],
    )
    for kind in ["model", "dataset"]:
        row["scenario"][kind] = {
            "id": f"synthetic:ci15-{kind}",
            "version": "1.0.0",
            "digest": "sha256:"
            + sha(
                struct.pack("<q", 8)
                if kind == "model"
                else encode(8, [16, -8, 24], [16, -16, 8], [1, 2, 1])
            ),
            "license": "Apache-2.0",
            "publication": "permitted",
        }
    row["provenance"].update(
        source_commit=p["source_commit"],
        execution_kind=p["execution_kind"],
        workflow_path=path,
        workflow_run=p["workflow_run"],
        toolchain="rust-1.85.1-python-3.11.14",
        dependency_digest="sha256:" + p["dependency_digest"],
    )
    row["provenance"]["hardware"].update(
        cpu=platform.machine(),
        os=platform.system(),
        memory_bytes=os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
        runner_image_revision=os.environ.get("ImageVersion", "unavailable"),
    )
    row["randomness"]["protocol_randomness"] = "private-not-recorded"
    row["outcome"] = {
        "status": "successful",
        "reason": "Controller verified actual proof; ten zero-exit negatives rejected.",
    }
    row["repetitions"] = [
        {
            "id": "rep0",
            "attempt": 1,
            "status": "successful",
            "timeout": False,
            "excluded": False,
            "reason": "Fresh setup; no imported key/receipt verdict.",
            "quality": "not-measured",
            "measurements": [
                {"phase": phase, "quantity": "time", "unit": "s", "value": native[key]}
                for phase, key in [
                    ("setup", "setup_seconds"),
                    ("witness", "witness_seconds"),
                    ("prove", "prove_seconds"),
                ]
            ],
        }
    ]
    row["repetitions"][0]["measurements"].append(
        {
            "phase": "verify",
            "quantity": "time",
            "unit": "s",
            "value": native["cases"][0]["verification_seconds"],
        }
    )
    row["metrics"] = []
    row["limitations"] = native["limitations"] + [
        "Negative setup/proving and all rejection cases are retained in the "
        "companion, not hidden in these phases.",
        "circuit_digest hashes circuit source; constraint matrices are not serialized.",
    ]
    row["publication_review"] = {
        "approved": False,
        "review_id": "synthetic:ci15-publication-review-pending",
    }
    bundle = {"schema_version": "1.1.0", "results": [row]}
    validate_bundle(bundle, load(ROOT / "claims/registry.json"))
    return bundle


def run() -> int:
    fixture = load(ROOT / FIXTURE)
    require(
        set(fixture) == {"version", "candidate_case"}
        and fixture["version"] == "ci15-1.0.0"
        and fixture["candidate_case"] in CASES,
        "authenticity-fixture",
    )
    state: dict[str, Any] = {
        "version": 1,
        "issue": 110,
        "status": "running",
        "provenance": provenance(),
        "fixture": FIXTURE,
        "fixture_digest": file_sha(FIXTURE),
        "native": None,
        "actual_process_exit": None,
        "seconds": None,
        "limitations": [
            "Conformance gate for the pinned public arithmetic proof only; no security/DP theorem.",
            "CI status never substitutes for independent review.",
        ],
    }
    save("authenticity-run.json", state)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(ROOT / "target/release/fzkml-assurance"), "auth", fixture["candidate_case"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
        state["actual_process_exit"] = completed.returncode
        require(
            completed.returncode == 0 and len(completed.stdout) <= 32_000,
            "authenticity-producer-execution",
        )
        state["native"] = json.loads(completed.stdout)
        validate_native(state["native"])
        state["status"] = "completed"
        if not state["provenance"]["source_dirty"]:
            save("authenticity-results.json", result(state))
    except Exception:
        state["status"] = "failed"
    finally:
        state["seconds"] = time.perf_counter() - started
        save("authenticity-run.json", state)
    if state["status"] != "completed":
        accepted = state["native"].get("candidate_accepted") if state["native"] else None
        print(
            f"CI-15 failed closed: actual producer exit={state['actual_process_exit']}; "
            f"candidate accepted={accepted}."
        )
        return 1
    print("CI-15: controller verified actual proof; ten zero-exit invalid receipts rejected.")
    return 0
