# Privacy and performance evidence for issues #60–#65

Status: implemented CPU references and analytical reproductions; independent domain review and downstream scientific dependencies remain pending.

The manuscript-source vectors are in `assets/public/privacy-performance-golden-v1.json`; source equations, revision, verified inputs and approximation tolerances are retained there. The private source export is excluded from the repository.

## Actual native CPU observation

Source commit: `2a356c78203ed492131c023165ef9a1c5f19bdd7`. Command: `PYTHONPATH=src uv run --locked python -m fzkml_research.experiment --output /tmp/native-profile.json`. Fresh output path required. Raw retained observations, warmups and event/resource ledgers: [native-profile-v1.json](native-profile-v1.json).

Hardware: Apple M3 Pro, arm64, 3.11.14, one single-threaded worker; Darwin-25.5.0. This was a local execution, with no invented workflow run ID.

| Implementation | Mean kernel ms | Mean whole invocation ms | Mean launch/import/IPC ms | Max worker RSS bytes | Temporary output bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| reference | 3.666333 | 76.909173 | 69.297937 | 31670272 | 23966 |
| transposed | 1.777785 | 73.975236 | 68.369854 | 31637504 | 23966 |

The arithmetic-only ratio is 2.062; the whole-invocation ratio is 1.040. This is six raw repetitions per implementation on one noisy host, plus one retained warmup each. It is a diagnostic observation, not a statistically established performance gain. Launch/import costs dominate, so a kernel-only speed number would overstate practical benefit.

The numerical relation and output digests match exactly. RSS is the worker process lifetime high-water value, including interpreter/imports; it excludes coordinator memory and is not aggregate concurrent RAM. Local buffer-copy bytes are not network traffic, and the fsynced temporary output is not an authorized protected model release. GPU/VRAM, actual training/proving and protected aggregation remain not-run. A crashed profiling child currently aborts this narrow runner; retry/completion studies must use the operational journal and reviewed full-pipeline adapter rather than infer failed child resources.

## Issue scope and remaining acceptance evidence

| Issue | Evidence supplied | Still required |
| --- | --- | --- |
| #60 | Exact source residual counterexample, kernel construction, replay/version/tape binding, conservative emitted-function diameters and postclip alternative | Authenticated proof/state integration and transcript privacy review (#26/#45/#54) |
| #61 | Original Chapter 48.2 numbers, exact-binomial construction, independent rational checks, model-run/calibration/multiplicity/failure guards, observer/power/inconclusive reporting | Independent statistical review and real preregistered attack/training-run manifests |
| #62 | Original Chapter 56.4 bound; exact fixed classifier counts, held-out version/query ledger, missingness/shift allowances | Finite-arithmetic DP sampler/protected computation and durable observer accounting (#55/#57), independent privacy/domain review |
| #63 | Original Amdahl/batch values, exclusive event/retry/setup/live-resource accounting, native timings/worker memory/disk/copy observations, censored certified-quality time | Actual complete protected path (#33/#46), joint all-role resource telemetry and failure accounting |
| #64 | Shared CI-11 comparison, same-assurance/observer/numeric/setup/payload/hardware guards, unavailable candidates retained | Real adequate multi-backend proof/payload adapters (#21/#33/#44), measured security/resource tradeoffs and independent review |
| #65 | Exact CPU modular layout alternative, independent/adversarial arithmetic checks and measured workload effects | Integration conformance (#26/#34); GPU explicitly not-run; no approximate ML path introduced |

## Validation and interpretation

`./scripts/validate` passes locally, including the foundation checks and 70 Python tests, including retained-artifact integrity and raw-aggregation checks. Hosted head checks are linked from PR #71. The inherited real-proof/required-cpu gate from #68 remains unavailable until its adapter exists; it is not bypassed. No issue is closed or scientific evidence automatically promoted by passing arithmetic tests.

Hosted validation exposed an inherited preinstalled Rust/Clippy conflict before the real-proof gate. Rust-installing workflows now source `scripts/install-rust-toolchain`, isolating RUSTUP_HOME/CARGO_HOME in the job temporary directory. Workflow review hashes are updated with that explicit change; no trust cache or required proof check is weakened.
