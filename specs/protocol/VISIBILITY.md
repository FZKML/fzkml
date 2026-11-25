# Witness and computing-role inventory v1 — #52

`experiments/protocol/observers.json` is the executable role/flow inventory. It
separates clients, trusted clusters, ordinary outsourced provers, collaborative
provers, coordinators, committees, telemetry, artifacts and attested provers. No
external computing role is permitted without its explicit trust/cryptographic/
attestation assumption. Proposed roles are marked unimplemented; this reference
runs locally on original synthetic data.

An ordinary remote prover receiving a plaintext witness sees records, model and
optimizer openings, intermediate values and proof coins even if its final proof
is zero knowledge. A trusted cluster has the same visibility under a different
operational trust policy. A collaborative prover would see specified shares plus
protocol leakage; hiding requires a selected protocol and collusion threshold,
not the label 'distributed'. An attested worker sees plaintext inside its TEE;
the host-isolation claim needs measured code, attestation verification, key
provisioning, anti-rollback and side-channel assumptions. None is implemented.

`Witness` disables generated repr output; `public_execution` selects a fixed
public event rather than serializing witness fields or exception text. It omits
record/witness hashes, private paths, randomness, arbitrary narratives and
fine-grained timing. The coarse accepted/rejected/failed bit and fixed policy
identity remain public leakage. The event states `proof_mode=none`; no norm check
or event establishes witness privacy. Public data is passed through CI-10's
existing `public_tree`, not a second secret-pattern validator.

Declared public surfaces are the reference CLI stdout/stderr, public event JSON,
retained reference observations, and CI-04 generated report files. Tests insert
original synthetic canaries into private notes, coins and exception messages,
execute both success and failure paths, and inspect these surfaces. A deliberate
leaky control is detected by the same validator. Source fixtures intentionally
contain canary definitions and are excluded from this 'absence' assertion.

This is a regression test with known strings, not a proof of noninterference.
It cannot rule out transformed/encoded leaks, arbitrary custom logs, OS writes,
subprocesses, remote telemetry, crash dumps, timing, caches, memory inspection or
malicious compute callbacks. No redirection claims to sandbox arbitrary code.
An actual backend/transport needs another data-flow review and canary run before
its artifacts are eligible for public publication (#33/#46). Raw worker output
must never be silently promoted into the allowlisted public artifacts.
