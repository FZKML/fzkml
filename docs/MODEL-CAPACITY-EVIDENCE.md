# Capacity, ridge and adapter research candidates

Issues #84, #86, #87 and #88 are implemented as bounded original synthetic
references on `codex/s04/model-capacity`, stacked on Session 04 PR #122. Existing
core cryptographic/ML files are unchanged. The new `fzkml-models` crate uses
already locked arkworks dependencies and performs genuine Groth16 setup,
proving and verification for two fixed relations. It is not a general-purpose
model-training prover or a deployment of private federated learning.

| Issue | Executed implementation | Remaining acceptance boundary |
| --- | --- | --- |
| #84 | Exact payload/proof/verification/queue budgets; independent scale axes; burst/deadline/dropout simulation; SQLite crash, retry, concurrent authority and restart tests | Physical client population, hardware distribution, real network traffic, production consensus/rollback resistance and deployment tail latency |
| #86 | Weighted rational sufficient statistics, exact solve, absolute objective, residual/perturbation certificates, source numeric payload/crossover fixtures; genuine two-record integer proof | Authenticated real raw records/features, protected vector statistics, complete DP accounting/mechanism, real frozen foundation model and independent review |
| #87 | Fixed-factor/dense equivalence, Gram identities, cross-term and rank-growth counterexamples, approximate 2x2 rank-one truncation, rounded delivered-message bounds; genuine two-client integer proof; full tiny frozen-layer forward work and quality | Protected coefficient aggregation and malicious federated orchestration, arbitrary rank/dimensions, real model training and empirical quality at a shared target |
| #88 | Typed full-state versus initialization-delta messages, fixed declared component masks and denominators, initialization/state metadata checks; hidden-state counterexample and whole-client bound | Cryptographic authentication of those metadata/eligibility decisions and hidden-state lineage, data-dependent masks and record-level private-state accounting |

Keep these issues open for their remaining research and review requirements.
Passing the candidate checks does not imply completion of every acceptance item.

## Reproduce and inspect evidence

Use the pinned Python 3.11.14, uv 0.9.11 and Rust 1.85.1 setup from the repository.

```sh
uv sync --locked
./scripts/validate
./scripts/models
./scripts/models --repetitions 3
```

The default command builds the native producer and requires both genuine
relations. No input file, external dataset, arbitrary command or GPU is accepted.
Repetitions are limited to three, native process timeouts to 240 seconds and
execution threads to two. `--references-only` explicitly records that mode and
cannot pass the genuine-proof receipt check. The required PR proof step invokes
the default command. The existing trusted nightly CPU lane runs three tiny
reference-only trials; schedules need the workflow on the default branch.

`reports/models/manifest.json` is an incremental closed-schema companion: source
SHA/dirty flag, real local/hosted identity, actual pinned software, hardware,
fixture/relation/program/lock digests, issue/engineering claim IDs, raw trials,
failures, resource observations and reproduction command. The native binary's
compiled source/contract/lock hashes must match the checked-out files. Completed
trials require every reference check and, in genuine mode, actual native proof
receipts with the correct independent outputs and mandatory negative counts.
The loader cryptographically reverifies canonical proof/verifying-key bytes and
rejects tampering; a stored boolean is insufficient. Key registration and
authorization remain external assumptions. Raw verifying keys are public data;
proving keys and commitment blindings are never exported.
Missing/mock/skipped proofs never count as genuine success. Failed attempted
work retains measured elapsed time; later repetitions stay pending.

Clean genuine runs additionally produce `reports/models/results.json` using the
unchanged shared result/bundle 1.1.0 schemas. Each new setup has distinct keys and
parameters, so these standard rows cover repetition zero only. All other raw
trials remain in the companion; they are not pooled under the first key. Local
workflow IDs are null. Scientific candidates have `approved=false`; the existing
proposed publication policy does not cover or approve this producer. Neither
workflow uploads nor report rendering are enabled for these candidates.

Setup/prove/verify are actual native wall timings. Proving includes circuit
synthesis. Negative setup has its own timing; other negative checks and key
serialization are included in the enclosing native process wall time. Child CPU
time is measured separately. Child peak RSS is the process-wide cumulative
maximum, not per-phase, joint-role or full-machine memory. The proof is 128 bytes;
public inputs, keys, commitments, protocol envelopes, transport and replication
are additional costs. Randomized proof/key bytes are not reproduction targets;
semantic outputs and rejected cases are.

## Exact ridge relation and error meaning

For nonnegative authorized record weights `a_j`, the sum-loss objective is
`F(W)=sum_j a_j ||z_j^T W-y_j||²/2 + lambda ||W||F²/2`.
The implementation computes `S=sum a_j z_j z_j^T`, `T=sum a_j z_j y_j^T`,
the optional objective constant `q=sum a_j ||y_j||²`, and weight mass `m`.
`A=S+lambda I`, with `lambda>0`; exact PSD checks reject invalid curvature.
Weights enter both statistics. Combining a fixed multiset is invariant to its
partition/order; duplicate retained-record identifiers and feature/preprocessor
version mismatches reject. This says nothing about whether excluded clients were
representative or whether input records are authentic.

For `R=A What-T`, strong convexity gives parameter error squared at most
`||R||F²/lambda²` and excess objective at most `||R||F²/(2 lambda)`. The numerical
certificate binds statistics, model, regularizer, objective policy and the actual
residual. A weighted-mean objective instead uses `A=S+lambda m I`; the bounds are
scaled consistently, including the extra factor of `m` in the objective. A
candidate residual for altered/noisy statistics is not a clean-objective
certificate. The separate candidate-based perturbation bound accounts for
curvature/target error and solver residual using conservative exact rational
square-root upper bounds. It is conditional arithmetic, not a noisy mechanism or
a probability guarantee for unbounded random draws.

The native ridge proof fixes two rows, two features, one output, weights `(1,2)`,
integer coordinates/labels in `[-4,4]`, `lambda=1`, model coordinates `[-8,8]` and
zero residual. A blinded SHA-256 commitment binds the private feature/label bytes
to the same witness used in the statistic equations and a public context digest.
The independent fixture gives `S=diag(1,2)`, `T=(2,6)`, `W=(1,2)`, objective 4.
All ten output substitutions, changed context/commitment, malformed/trailing
proofs and a different verifying key reject: 15 negative checks.

There are `d(d+1)/2+dc` scalar statistics when symmetry is packed; the absolute
objective constant adds one. At four bytes/scalar the inspected source examples
give 1,488,384 bytes at `(d,c)=(768,100)` and 35,201,024 at `(4096,100)`. Relative
to a dense head per round, the exact crossovers are `R>969/200` and `R>4297/200`.
Cryptographic expansion, wider accumulators, feature extraction, downloads and
different learning outcomes are excluded. For one unweighted record and full
vectorization, squared add/remove sensitivity is bounded by
`C_z^4+C_z² C_y²`; replacement admits four times that squared bound. Weighted,
packed-triangle or whole-client mechanisms need their matching bounds/metrics.
Counts, clean statistics and residual certificates can themselves disclose data.
No DP mechanism, accountant or epsilon is claimed.

## Fixed factors, delivered values and heterogeneous state

With one common fixed `A0` and normalized public weights, linearity gives
`sum p_i B_i A0=(sum p_i B_i)A0`. Independently averaging both factors generally
introduces cross terms: the scalar pairs `(A,B)=(1,1),(-1,-1)` have mean product 1
and product of means 0. Summing two rank-one coordinate projectors gives rank-two
identity. The optional floating-point 2x2 SVD approximation reports its error;
it is never an exact rank-preserving aggregation claim.

The reference verifies `||BA0||F²=tr(B^T B A0 A0^T)` exactly. Basis/version,
initialization, clipping, quantum and public weights are part of the policy ID.
It checks the norm of the actual rounded dense message, so coefficient clipping
alone cannot hide a violated delivered bound. Rounding each client product before
aggregation can differ from rounding the aggregate product. For fixed cohorts,
masks and weights and hard delivered norm `C`, replacement sensitivity is at most
`2 p_max C`. Neither this bound nor linear post-processing constructs a private
release mechanism.

The native adapter proof fixes two private 2x1 coefficient factors, public
`A0=(1,0)`, equal weights, zero initialization, integer dense products and each
client's squared coefficient norm at most 9. Exact range constraints enforce that
bound before the public numerator sum. All eight output substitutions, context/
commitment changes, malformed/trailing proofs and a different key reject: 13
negative checks. Its single prover sees both clients' witnesses. It is not a
distributed prover or a protected vector aggregation protocol. The public result
is the clean summed coefficient/dense numerator, and no privacy is claimed
against that prover or against information inferable from that output.

The tiny quality experiment executes the full frozen 2x2 backbone and adapter
forward path for two original synthetic records. It counts eight backbone and
eight adapter multiplications, rather than calling two trainable parameters the
whole workload. A restricted basis has mean squared vector error 1/2 on this
fixture, while the fully expressive dense target can fit exactly. This is a
constructed expressiveness check, not a training speedup or real-model accuracy
result. Large representation counts in the fixture are analytic only.

For heterogeneous components, full-state and initialization-delta messages cannot
mix. The supplied declared eligibility mask must match absent/present values;
denominators sum only eligible weights. The inspected teaching fixture gives
`(3,8)` versus zero-padded `(3,4)`. These are metadata conformance checks, not
cryptographic eligibility authentication. Empty component cohorts reject.

One record can flip persistent hidden state shared by every gradient, changing
their clipped average by `2C` instead of `2C/n`. The API rejects that hidden-state
case under record-level sensitivity assumptions. Its whole-client path requires
an explicit norm bound on the delivered vector and fixed masks/weights. The
heterogeneous bound uses the largest per-component normalized weight. Public
data-dependent masks, an unaccounted state transition, or changed denominators
require a different analysis and are not silently accepted.

## Capacity and recovery scope

The capacity example uses the source's declared hypothetical assumptions, not
observed hardware: ten million enrolled devices, twenty thousand selected,
65,536 32-bit coordinates, forty routing buckets, a 2 KiB budgeted proof envelope
and 5 ms assumed verifier service. Client payload is 5,242,880,000 bytes and proof
traffic 40,960,000 bytes. Verification is 100 CPU-seconds; an ideal 64-worker lower
bound is 25/16 seconds. A single ideal 1 Gbit/s ingress needs at least
131072/3125 seconds for raw client payload alone.

The conditional forty-partial payload is 10 MiB only if that representation and
32-bit accumulator range are justified. Missing range evidence is explicitly
uncertified. Supplying a full signed-32-bit coordinate hard bound for twenty
thousand additions rejects a 32-bit accumulator; a wider accumulator increases
the final-stage payload. Replication is separate from client upload. Model size,
record count, enrollment, selected clients, physical concurrency, trace steps and
arrivals remain separate axes. No unmeasured trace-length proof cost is inferred.

Queue observations are deterministic simulations with zero physical client
processes and one physical driver. Burst/deadline/dropout/invalid/overload outcomes
remain in the denominator; accepted-only latency would hide completion bias.
Utilization is an elementary load budget and cannot establish real tail latency.
No protected cleartext bucket releases are authorized by a routing calculation.

The recovery fixture uses public integers and one SQLite authority with atomic
transactions. It rejects conflicting retries and context/roster drift, fails on
unavailable committed payloads, rolls back an injected pre-commit failure and
returns the same persisted receipt after restart or concurrent local finalizers.
This demonstrates local idempotence, not distributed consensus, external
exactly-once delivery, rollback resistance or transcript privacy. A changed
accepted roster/output is a new authorization and privacy question.

## Source, licensing and review

The canonical owner-provided manuscript's readable connector response was
inspected on 2026-11-25: illustrated research edition 1.1, modified
2026-11-23T17:06:44.925Z, sections 50.4, 68.2–68.4, 72.1–72.5 and 76.2–76.6.
Its numeric prose supports the listed fixtures; native equation transcription
was not performed. Original derivations/counterexamples are labeled separately.
No manuscript text/export is committed. The engineering registry uses reference
edition `S04M5`; it does not change Session 03's authoritative manuscript registry
or claim independent review.

Related primary research: [Fed3R, ICML 2024](https://proceedings.mlr.press/v235/fani-24a.html)
uses closed-form ridge classifiers over pretrained features;
[FFA-LoRA, ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/4e243e95c913b367775d71d7182b99d9-Abstract-Conference.html)
fixes one factor for federated adaptation. These motivate useful learning
boundaries; they are not evidence that this candidate implements their complete
empirical systems or a malicious-secure proof/aggregation protocol. No paper code
or external dataset/model is imported. Original code/docs/fixtures are Apache-2.0,
use existing dependency notices and the maintainer-authorized DCO identity.
Independent mathematical, cryptographic, privacy and systems review remain open.
