# CPU and research lane contract

Local foundation checks use `./scripts/validate`. The mandatory scientific gate
uses `./scripts/research proof`, exactly as the CPU workflow. `required-cpu`
runs even after upstream failure and accepts only success from both jobs; failure,
skip, cancellation or timeout cannot satisfy it. Jobs are capped at 15 minutes;
research matrix max-parallel is 2. Required PR checks need no GPU.

The current proof adapter is explicitly unavailable. This PR must remain draft:
LANG-03 and FZK-R013/R014/R015 must implement a reviewed executable adapter and
real, fresh CI-04 results for tiny proof, native/circuit conformance and negative
cases. The gate rejects synthetic/development backends, skipped repetitions,
missing/zero circuit/program/key identities and failed outcomes. Metadata checks
cannot establish that an adapter performs real cryptography; reviewers must inspect
its implementation and negative-case coverage. Require `required-cpu` in branch
rules after reviewing its first real hosted run and measured CPU budget.

Scheduled/manual CPU research checks out only the default branch; dispatch accepts
no ref, command or configuration. The reviewed fixed matrix is `contract` and
`tiny-reference`. The first profile repeats contract tests, not a scientific
benchmark. The second remains unavailable until the adapter exists. Research-supplied
fuzz corpora and multi-process scenarios remain dependencies; no substitute is
reported as scientific evidence. Adding them requires code/profile review.

Each profile caps repetitions (5), time per repetition (120 seconds), threads (2),
and declared input size (1 MB); default inputs are repository-owned fixtures only.
External inputs and arbitrary seed/corpus paths are not accepted. A real adapter
must enforce the same input bound before expanding its input surface. No warmup is
performed in these profiles. Initial journal publication precedes execution;
repetitions are atomically persisted with fsync after each transition. Raw stdout
is discarded, and failure emits a bounded profile/repetition reproducer.

Final upload is best effort. A separate default-branch `workflow_run` consumer
reads job metadata using `actions: read`, never downloads/executes artifacts, and
records cancelled/timed-out/lost runs with unknown repetitions. Join journals by
run ID, attempt, source SHA and profile. Missing journals stay inconclusive; a job
success alone never reconstructs per-repetition success. Diagnostics expire after
7 days, reconciliation after 14. Download relevant journals before expiration.

The GPU workflow has no GPU runner, provider credentials or provisioning code. It
fails after the protected `gpu-research` environment gate. A variable alone cannot
enable paid work. A later reviewed implementation must bind the default-branch
SHA and allowlisted profile; record provider, budget, maximum jobs/devices/time,
device/driver metadata, ephemeral isolation, scoped OIDC and provider-side TTL
cleanup that also survives cancellation/runner loss. Until those controls are
implemented and a maintainer authorizes the specific provider/budget, no GPU run
can occur. There is no GPU dependency in required CPU checks.

# Fair comparison policy

`fzkml_ci.benchmark.compare` consumes the shared result schema, extended with
optional `benchmark` declarations. Match relation/statement, numerical semantics,
security parameters, dataset/model versions, workload, quality threshold and
hardware. Backend identity may differ; unmatched proof statements cannot be ranked.
Security equivalence still requires human review. Declare warmups, cached work,
setup amortization, and all setup/compile, witness, proving, aggregation,
verification, transfer and total phases. Use setup for compilation; do not hide
precomputation. Mark unavailable/not-applicable phases explicitly. Declare peak
memory, proof size and communication, with reasons for unavailable values. Keep
failed, timed-out, excluded and retried repetitions in CI-04 records and count
resource use once. Do not average only successful runs without the failure count.

All shared-runner timing comparisons are diagnostic, with raw repetitions, sample
variance and failure counts. Strict regression thresholds require a separately
reviewed calibration on comparable hardware with a preregistered noise-aware
threshold, minimum repetitions and environment controls. No threshold is enabled
here. One circuit, model or machine cannot support a global fastest claim. The
policy supplies the CI side of FZK-R035/R036; it does not duplicate their experiments.
