# Scientific measurement requirements, version 0.1

Status: #14 specification; CI-04 (#15) owns the one executable result schema.
Source: Chapters 35, 38.3, 43.3, 58 and 80.1–80.3; exercised acceptance examples
are in `experiments/m0/reporting-cases.json`, explicitly fictional schema-use
cases rather than benchmark evidence. No successful scientific run is recorded.

A run identity binds the guarantee and observer, exact relation and numerical
semantics, public statement, algorithm/model and initialization, full-state vs
delta type, backend/setup/security parameters, parameter/key/program/circuit
digests, policy/roster/release versions, dataset/split/asset digests, source commit,
workflow revision and immutable environment. A model name alone is insufficient.
Published outputs need actual provenance and a human publication review; a
synthetic test's review marker must never masquerade as a benchmark approval.

Record CPU/GPU model, physical/concurrent/virtual workers, RAM/VRAM, operating
system, runner image, threads, toolchain, dependency lock hash, clocks and units.
Public experiment seeds reproduce only synthetic data, splits and scheduling.
Commitment blinding, protocol masks, secret noise/DP seeds and production
randomness are never published. A public seed cannot certify honest entropy.

Every invited repetition and every attempt has a stable ID, status, deadline,
reason, exclusion decision and retained raw measurements. Use CI-04 statuses
`not-run`, `unsupported`, `failed`, `inconclusive`, `successful`. A timeout is
`failed` with `timeout=true`; a verifier rejection is `failed` with a rejection
reason. A successful execution with insufficient statistical information is
`inconclusive`. Reaching a learning-quality target is separately recorded; an
executed computation need not have reached useful quality. No timings or
quality zeros stand in for missing observations.

## Cost accounting

Use one exclusive event ledger for preparation, setup/key generation, training,
witness construction, proving, transfer, aggregation, parsing/verification,
evaluation and authorized release. Each event has a cost ID, attempt ID, start
and end, resource, quantity/unit and inclusion/amortization policy. Shared setup
has one cost ID and explicit reuse references. Retries get new cost IDs; keep
the cost of failed and rejected attempts. Exclusive phase sums measure work;
end-to-end wall time is separately measured from earliest start to final
authorized release or deadline. Concurrent durations cannot be added as latency.
Do not add a setup total again to a total already containing its events. Peak
live memory is measured jointly; neither summing per-phase peaks nor taking the
largest single worker's peak measures aggregate concurrent memory.

Retain raw repetitions for every summary; state mean/median/quantiles, included
IDs, estimator, uncertainty procedure and failure/missingness denominator.
Separate cold setup, warm reusable setup, per-attempt work, cohort-tail latency,
unmet quality at the time cap, and total resource cost. An exclusion from paired
quality inference does not remove an attempt from resource or availability
reports. Retain negative and contradictory results with the same provenance.

## CI-04/CI-05 integration contract

The current shared 1.0.0 schema already names scenario statement/relation/numeric
semantics, provenance, public-vs-secret randomness, repetitions, statuses and
raw-linked summaries. Use it unchanged for those fields. Scientific context
that does not fit it remains in keyed experiment definitions and claim context;
do not add arbitrary properties to a closed schema or silently substitute
`prove` for witness-generation time.

Before benchmark use, #15 must resolve: explicit observer/guarantee identity,
an event ledger/reuse references, phases for preparation/witness/aggregation/
release, CPU vs GPU and non-workflow local provenance, retry/replicate grouping,
exact security parameters, uncertainty and time-to-quality censoring. A version
bump or reviewed companion schema is required; this document does not claim
the existing schema validates those extensions. The reporting cases provide
acceptance requirements, not a competing executable result schema. #16's
authoritative claim statuses remain separate from run outcomes and source
extraction states. Test success cannot promote scientific evidence status.
