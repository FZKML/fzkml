#!/usr/bin/env python3
"""Retain bounded synthetic M4 calculations, real local proofs, and unsupported states."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import time
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from python.fzkml_math.collaborative import (
    SOURCE_COMMIT,
    inspect_multiplier,
    prove,
    public_transcript,
    sha,
    verify,
)
from python.fzkml_math.pq_audit import audit
from python.fzkml_math.progress import capacity, miss_probability, pipeline
from python.fzkml_math.protected import (
    Paillier,
    exact_product,
    require_prover_profile,
    sumcheck_counterexample,
)

ROOT = Path(__file__).resolve().parents[1]


def trusted_baseline(source: Path, binary: Path, out: Path) -> dict[str, Any]:
    out.mkdir()
    v = source / "test_vectors/Groth16/bn254/multiplier2"
    # Pin the actual public package API; singleThread fixes arithmetic-worker mode.
    program = """const fs=require('fs'); const s=require(process.argv[1]);
    (async()=>{let r=await s.groth16.prove(
    process.argv[2],process.argv[3],undefined,{singleThread:true});
    fs.writeFileSync(process.argv[4],JSON.stringify(r.proof));
    fs.writeFileSync(process.argv[5],JSON.stringify(r.publicSignals));})().catch(e=>{console.error(e);process.exit(1)});"""
    start = time.perf_counter()
    r = subprocess.run(
        [
            "node",
            "-e",
            program,
            str(ROOT / ".tools/snarkjs/node_modules/snarkjs"),
            str(v / "circuit.zkey"),
            str(v / "witness.wtns"),
            str(out / "proof.json"),
            str(out / "public.json"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    seconds = time.perf_counter() - start
    if r.returncode or not verify(
        binary, out / "proof.json", v / "verification_key.json", out / "public.json"
    ):
        raise ValueError("trusted-baseline-proof-failed")
    return {
        "status": "verified",
        "backend": "snarkjs0.7.5 Groth16 singleThread",
        "seconds": seconds,
        "verification": "pinned independent coCircom verifier accepted",
        "proof_json_bytes": (out / "proof.json").stat().st_size,
        "communication_bytes": 0,
        "protocol_rounds": 0,
        "max_rss_bytes": None,
        "rss_status": "not-instrumented",
        "public_transcript": public_transcript(out / "proof.json", out / "public.json"),
        "limitations": [
            "Different prover implementation/runtime; no speedup ratio inferred.",
            "Reads the complete public synthetic witness; trusted prover baseline.",
        ],
    }


def he_repetition() -> dict[str, Any]:
    start = time.perf_counter()
    key = Paillier.generate()
    setup = time.perf_counter() - start
    start = time.perf_counter()
    c = key.encrypt(3)
    encrypted_seconds = time.perf_counter() - start
    start = time.perf_counter()
    product = key.multiply_public(c, 11)
    evaluation = time.perf_counter() - start
    start = time.perf_counter()
    result = key.decrypt(product)
    decryption = time.perf_counter() - start
    if result != exact_product(3, 11):
        raise ValueError("HE-exact-semantics-mismatch")
    # Valid ciphertext modification is deliberately accepted: Paillier is malleable.
    tampered = product * (1 + key.n) % (key.n**2)
    altered = key.decrypt(tampered)
    if altered != 34:
        raise ValueError("unexpected-malleability-negative")
    try:
        key.decrypt(0)
    except ValueError:
        nonunit_rejected = True
    else:
        nonunit_rejected = False
    return {
        "status": "completed",
        "modulus_bits": key.n.bit_length(),
        "output": result,
        "key_generation_seconds": setup,
        "encryption_seconds": encrypted_seconds,
        "evaluation_seconds": evaluation,
        "decryption_seconds": decryption,
        "end_to_end_seconds": setup + encrypted_seconds + evaluation + decryption,
        "online_seconds": encrypted_seconds + evaluation + decryption,
        "ciphertext_payload_bytes_each": (2 * key.n.bit_length() + 7) // 8,
        "logical_messages": 2,
        "protocol_round_trips": 1,
        "communication_scope": (
            "Two fixed-width ciphertext payloads, simulated local transfers; no measured network."
        ),
        "malformed_ciphertext_rejected": nonunit_rejected,
        "valid_malleation": {
            "decoded": altered,
            "detected_by_HE": False,
            "detected_by_synthetic_oracle": altered != result,
        },
        "key_material_retained": False,
        "limitations": [
            "Original unaudited variable-time Python crypto reference; no deployment security.",
            "Client holds complete decryption key and can decrypt every ciphertext it sees.",
            (
                "Evaluator knows coefficient11. Authorized product and an operand"
                " reveal the other operand."
            ),
            "No CCA integrity, range proof, computation proof, threshold key or PQ protection.",
            "No claim to hide the evaluator coefficient from the full-key decrypting client.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--external", action="store_true")
    parser.add_argument("--repetitions", type=int, choices=range(1, 4), default=3)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise ValueError("fresh-output-directory-required")
    out.mkdir(parents=True)
    source = ROOT / ".tools/co-snarks"
    binary = ROOT / ".tools/co-runtime/co-circom"
    lock = json.loads((ROOT / "experiments/s02-protected/runtime-lock.json").read_text())
    configuration = json.loads(
        (ROOT / "experiments/s02-protected/pq-inventory-v1.json").read_text()
    )
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))
    report: dict[str, Any] = {
        "schema_version": "s02-protected-run-1.0.0",
        "kind": "local-candidate-research",
        "planning_issue_claim_ids": ["FZK-R042", "FZK-R043", "FZK-R044", "FZK-R045"],
        "source_commit": source_sha,
        "source_dirty": source_dirty,
        "source_approval": "not-independent-review; DCO pending for new commits",
        "hardware": {
            "os": platform.system(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "gpu": "not-used",
            "isolation": "shared local host",
        },
        "software": {
            "python": platform.python_version(),
            "coCircom_source": SOURCE_COMMIT,
            "node": subprocess.check_output(["node", "--version"], text=True).strip()
            if args.external
            else None,
        },
        "digests": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                ROOT / "experiments/s02-protected/runtime-lock.json",
                ROOT / "experiments/s02-protected/snarkjs-lock.json",
                ROOT / "experiments/s02-protected/pq-inventory-v1.json",
                ROOT / "tests/vectors/book/progress-v1.json",
                ROOT / "Cargo.lock",
                ROOT / "uv.lock",
            ]
        },
        "observer_model": {
            "trusted_harness": (
                "Owns public synthetic full witness, shared host, all relay traffic and tool files."
            ),
            "REP3_workers": (
                "Each holds two additive shares; at most one passive corrupt "
                "worker under assumed private channels."
            ),
            "network": (
                "Pinned upstream0.10 uses raw TCP; loopback demonstration does "
                "not supply private authenticated channels."
            ),
            "HE": (
                "Key owner knows a and full secret key; evaluator knows b and "
                "receives Enc(a); both receive only declared product as output."
            ),
            "authorized_output": (
                "Product33; possession of either nonzero operand recovers the "
                "other. No output privacy/DP claim."
            ),
            "attestation": (
                "No TEE, hardware attestation, quote or certificate verification executed."
            ),
        },
        "pipeline": [pipeline(w, fail_height=f) for w in (1, 2, 4, 8) for f in (None, 4)],
        "sampling": {
            "capacity_upper_bound": str(capacity(F(1, 5), F(2), 8)),
            "one_bad_detection": str(1 - miss_probability(100000, 1, 1000)),
            "one_percent_bad_exact_miss": float(miss_probability(100000, 1000, 1000)),
            "one_percent_bad_miss_upper": float(F(99, 100) ** 1000),
            "type": "exact fixed-trace without-replacement calculation; not a training proof",
        },
        "sumcheck_negative": sumcheck_counterexample(3, 8),
        "pq_inventory_audit": [audit(c) for c in configuration["configurations"]],
        "matched_workload": {
            "function": "signed integer a*b",
            "a": 3,
            "b": 11,
            "expected": 33,
            "encoding": (
                "Exact integers; abs(inputs)<=32, abs(product)<=1024; field/modulus no wrap."
            ),
            "dataset_provenance": (
                "Public upstream synthetic arithmetic fixture; no learning data/model."
            ),
            "preprocessor": "identity",
            "model": "one scalar coefficient11",
            "he": [],
            "collaborative_proofs": [],
            "trusted_prover": [],
            "attested_execution": {
                "status": "not-run",
                "reason": "real attestation backend/quote verifier unavailable",
            },
        },
        "negative_runs": [],
        "limitations": [
            "No manuscript/claim status promotion, merge or independent security approval.",
            (
                "Simulation clocks are exact model outputs; local process timings"
                " are diagnostics on this host."
            ),
            (
                "No WAN latency/bandwidth emulation, distributed physical "
                "machines, production input owners or private channels."
            ),
            "No DP theorem or statistical generalization from these deterministic examples.",
            "Private operands/model coefficient are not authenticated by input "
            "commitments in the selected external circuit.",
            "Protocol round trips and combined live coordinator/cluster memory remain unmeasured.",
            (
                "External proofs check one field multiplication; they do not "
                "certify full FZKML training or integer range constraints."
            ),
        ],
        "reproduction_command": (
            "PYTHONPATH=.:src .venv/bin/python scripts/run_s02_protected.py "
            ".tools/fresh-run --external --repetitions 3"
        ),
    }

    def retain() -> None:
        schema = json.loads((ROOT / "schemas/s02-protected-run-1.0.0.json").read_text())
        Draft202012Validator(schema).validate(report)
        (out / "run.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    retain()
    if args.external:
        actual = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != SOURCE_COMMIT or actual != lock["source_commit"]:
            raise ValueError("external-source-mismatch")
        if (
            subprocess.check_output([str(binary), "--version"], text=True).strip()
            != "co-circom 0.10.0"
        ):
            raise ValueError("external-version-mismatch")
        for p, digest in lock["external_files"].items():
            if sha(source / p) != digest:
                raise ValueError("external-fixture-or-source-mismatch:" + p)
        archive = ROOT / ".tools/co-runtime/runtime.tar.gz"
        platform_key = platform.system() + "-" + platform.machine()
        if sha(archive) != lock["archives"][platform_key]["sha256"]:
            raise ValueError("runtime-archive-mismatch")
        with tarfile.open(archive) as tar:
            entry = tar.extractfile("co-circom")
            if entry is None or hashlib.sha256(entry.read()).hexdigest() != sha(binary):
                raise ValueError("runtime-binary-differs-from-pinned-archive")
        report["software"]["coCircom_binary_sha256"] = sha(binary)
        report["external_relation"] = inspect_multiplier(source)
        require_prover_profile(1, True, 3)
        for i in range(args.repetitions):
            baseline = trusted_baseline(source, binary, out / f"trusted-{i}")
            baseline.update(repetition=i, excluded=False)
            report["matched_workload"]["trusted_prover"].append(baseline)
            he = he_repetition()
            he.update(repetition=i, excluded=False)
            report["matched_workload"]["he"].append(he)
            for delay in (0, 0.005):
                run = prove(source, binary, out / f"rep3-{i}-{delay}", delay=delay)
                run.update(repetition=i, excluded=False)
                if not run["verified"]:
                    report["negative_runs"].append({"unexpected_positive_failure": run})
                    retain()
                    raise ValueError("expected-real-proof-not-verified")
                transcript = public_transcript(
                    out / f"rep3-{i}-{delay}" / "proof0.json",
                    out / f"rep3-{i}-{delay}" / "public0.json",
                )
                run["public_transcript"] = transcript
                report["matched_workload"]["collaborative_proofs"].append(run)
                retain()
        for name, kwargs in [
            ("missing-share", {"missing": True}),
            ("malformed-share", {"malformed": True}),
        ]:
            negative = prove(source, binary, out / name, timeout=2, **kwargs)
            report["negative_runs"].append(
                {"case": name, "expected": "not-verified", "result": negative}
            )
            if negative["verified"]:
                raise ValueError("negative-proof-accepted")
            retain()
        example = out / "rep3-0-0"
        altered = out / "altered-public.json"
        altered.write_text('["34"]')
        wrong = verify(
            binary,
            example / "proof0.json",
            source / "test_vectors/Groth16/bn254/multiplier2/verification_key.json",
            altered,
        )
        report["negative_runs"].append({"case": "wrong-public-output", "accepted": wrong})
        if wrong:
            raise ValueError("wrong-output-accepted")
        malformed = out / "malformed-proof.json"
        malformed.write_text("{}")
        accepted = verify(
            binary,
            malformed,
            source / "test_vectors/Groth16/bn254/multiplier2/verification_key.json",
            example / "public0.json",
        )
        report["negative_runs"].append({"case": "malformed-proof", "accepted": accepted})
        if accepted:
            raise ValueError("malformed-proof-accepted")
        # Retain public proofs and outputs; exclude shares, private logs and configs.
        artifacts = out / "public-artifacts"
        artifacts.mkdir()
        for f in ("proof0.json", "public0.json"):
            shutil.copyfile(example / f, artifacts / f)
        report["public_artifacts"] = {f.name: sha(f) for f in artifacts.iterdir()}
    retain()
    print(
        "S02 protected reference run retained. Attestation not-run; no "
        "full-stack PQ configuration supported."
    )


if __name__ == "__main__":
    main()
