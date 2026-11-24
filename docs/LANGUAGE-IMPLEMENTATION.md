# Language implementation and evidence

This branch implements #9/#27/#29/#30/#31 on top of PR #67's locked CPU and
result-schema foundation. It does not close related research #26/#28 or claim
agreement with a private manuscript. The candidate relation is deliberately small
and independently reviewable; architecture/security review remains required.

## Reproduce on Linux

Use Rust 1.85.1, Python 3.11.14 and uv 0.9.11, as specified by the CI foundation.
From the repository root run:

```sh
uv sync --locked --group ml
./scripts/validate
./scripts/validate-language
```

The second command builds the Rust checked/debug path and runs its tests. The
language command checks debug and release CLIs against 261 accepted and 11 rejected
independent vectors plus 1,040 signed rounding cases, checks constrained witnesses
against the Python oracle's expected results, runs release proof tests, and builds
three deliberate rounding/endianness/range mutants. All must be detected. Mutants
use a separate target directory and cannot replace the actual CLI or wheel.
Failure records include a minimal rounding case or a greedily shrunk canonical
batch; this is a counterexample reducer, not a proof of global minimality.

The language command then builds a wheel with maturin 1.8.3, checks its Rust
dependency notices, installs it in a clean virtual environment without dependencies,
runs a synthetic smoke case, installs it in the locked ML environment, and runs
eight binding/oracle/PyTorch tests and the phase profile. Linux is the initial CI
support target; a local macOS arm64 build is supplementary evidence, not a claim
of universal wheel support. No package is published by this change.

## Python API and ownership

`CanonicalBatch(data: bytes)` validates exactly 84 immutable bytes through Rust.
`evaluate()` returns the exact integer aggregate. `ResearchSession()` owns one
fresh local keypair; `prove(batch)` returns a typed `ProofResult` with integer
output, proof bytes, contract version, verifying-key digest, and timings.
`verify(batch, result)` checks the same statement and session. The compiled
contract digest is exposed so a stale wheel cannot silently pass new fixtures.

PyBytes lengths are checked before copying: 84 input bytes and 128 proof bytes.
No arbitrary vectors, tensor shapes or caller-provided serialized keys are allocated
by Rust. Invalid bytes/ranges return ValueError; wrong Python types return TypeError
(or OverflowError for non-i64 output); backend panics are contained and converted
to RuntimeError. Diagnostics contain static codes, not input values. The API does
not print inputs, witnesses, proof randomness, or setup trapdoors. Current scenario
inputs are all public, but callers should still avoid logging future private data.

One batch crosses per operation. Owned Rust byte copies and immutable keys outlive
GIL release during setup/proving/verification. Native calls can be issued from
Python threads; the caller controls concurrency and memory spent on multiple
sessions. There is no per-element FFI loop or service-level resource scheduler.
The PyTorch profile temporarily changes process-wide deterministic settings and
restores them and the CPU RNG state; serialize it with other PyTorch work.

## Profiles and result schema

`reports/language-profile.json` records model/optimizer/preprocessor/dtype, fixture
seed, exact dependency/contract hashes, source commit and dirty state, platform,
thread count, key digest, proof size/validity, separate quality differences, and
phase times in seconds. Setup, training, conversion/copying, host witness generation,
proving and verification have separate hooks. Backend proving includes its own
constraint synthesis and QAP witness mapping; no claim of isolating that internal
subphase is made. Fixture seeds never seed cryptographic randomness.

On GitHub CI, `reports/language-result.json` is additionally validated against the
shared result schema 1.0.0 from #15. Raw coarse-phase repetitions are retained and
summary metrics name their aggregation. Detailed conversion/witness phases and
quality differences remain in the companion profile; no incompatible experiment
schema replaces the shared contract. Local runs have no GitHub workflow identity
and produce only the local profile rather than invent a workflow run number.

The workflow runs on small PR CPU inputs and weekly on the default branch, where
an additional 2,048 seeded valid cases exercise the release path. It has
read-only permissions, no secrets, no cache sharing and no artifact publication.
Logs contain only the fixed original public synthetic profile. Release artifact
publication remains the separate CI release workstream; no public raw data or
restricted models are adopted here.

## Actual local evidence and limits

On 2026-11-24, the macOS arm64 prototype passed its initial Rust arithmetic,
constraint-mutation and proof-key/public-input rejection tests; debug/release
oracle conformance; all three deliberately broken Rust variants; wheel license
bundle checks; and all eight Python integration tests. One local profile verified
a 128-byte proof and produced integer aggregate 9 (0.5625) versus floating
aggregate 0.5546875: absolute difference 0.0078125, with zero input-quantization
error for that representable fixture. Timings are machine-specific, single-run
measurements; the retained profile and CI logs are the evidence, not these values
as a performance promise. The uncommitted local profile is explicitly marked dirty.

No accelerator is proposed. This profile cannot establish scalability, privacy,
learning utility, constant-time execution, cryptographic strength, or production
setup quality. Independent review of relation constraints, no-wrap reasoning,
backend/setup assumptions, dependencies, and API boundaries remains necessary.
