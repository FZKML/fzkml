# Scoped privacy and performance contracts, version 1

Issues #60–#65 implement original CPU research/reference code in
`src/fzkml_research/`. These contracts supplement the shared CI-04 result schema
and CI-11 comparison policy; they do not implement a new proof backend or a
production privacy mechanism. Independent privacy, statistics, arithmetic and
systems review remains required by GOVERNANCE.md. No formal-proof artifact is
claimed by passing these tests.

## Source and evidence

The canonical manuscript is the owner-authorized
[Google Doc](https://docs.google.com/document/d/14tD223seyGYrtYZJOuPKtH0lwlKo4To4p4aRHhKI9RY/edit).
`assets/public/privacy-performance-golden-v1.json` records its observed revision,
text and Markdown-export hashes, source-snapshot edition, section, unnumbered
equation locator, Docs UTF-16 ranges, verified inputs and rounded expected values
for each book golden. `MS20261124` identifies the observation, not an
author-declared published edition. The Markdown export was necessary because the
Docs paragraph API omits native equation contents. No full manuscript or private
prose is redistributed. These are hypothetical analytical examples, not training
experiments or primary-paper replications. New constructed kernel/negative cases
are separately labeled synthetic constructions in tests.

## #60: Actual transmitted function and sequential compression

Vectors and residuals use exact Python Fractions; fresh inputs must satisfy
L2 norm at most C. Top-one ties select the lowest coordinate. The state hash
binds residual, round, parent state, model lineage, compressor version, mode,
dimension, C and a public synthetic coordinate tape. Replayed rounds, changed
policies, different lineage and exhausted random tapes fail. These hashes are
neither hiding commitments nor a sequential cryptographic proof. They are a
reference contract for #45, which still owns authenticated protocol state.

For top-one, Q(z) retains one coordinate of z. For the unbiased random-coordinate
example Q(z)=d*z[J]*e[J], the declared tape fixes J at each step; unbiasedness
requires genuinely uniform J and is not claimed for a fixed teaching tape.
The reference demonstrates the manuscript's two fresh (3/5,3/5) updates producing
(3/5,0), then (0,6/5) under error feedback. Fresh clipping therefore does not
establish the same bound on the emitted vector. The postclip variant clips that
single emitted coordinate to [-C,C] and sets the next residual to combined input
minus the *actual clipped emission*, preserving the modified recurrence.

Conservative L2 replacement diameters for one emission are:

| Mode | Without feedback | With feedback after t preceding rounds |
| --- | --- | --- |
| top-one | 2C | 2(t+1)C |
| unbiased random coordinate | 2dC | 2d(C+R_t), R_0=0, R_(t+1)=max(1,d-1)(C+R_t) |
| top-one then postclip | 2C | 2C |

Derivation: each emitted norm is bounded by the norm of its input for top-one,
or d times that norm for random-coordinate compression. For top-one the residual
norm is no larger than the combined-input norm; for random-coordinate compression
the residual linear operator has norm at most max(1,d-1). Triangle inequality
gives the recurrences, and twice the radius bounds the distance between emissions
from any two allowed histories. The postclip range gives a history-independent
diameter. These are conservative output-range bounds, not tight local Lipschitz
constants or a complete DP theorem. Add/remove bounds depend on the exact absence
mapping; this implementation does not silently replace replacement adjacency.
Observer-visible indices, lengths, residuals, timing and repeated emissions still
require the transcript analysis in #54/#57. The chosen reference alternative is
explicit post-emission clipping when a fixed emitted bound is required; retaining
the original recurrence instead requires the larger state-dependent bounds.

Exact RREF constructs a nonzero vector in a noninjective encoder's kernel.
Scaling it preserves its zero projection while growing its dense norm. The API
rejects projected-bound-to-dense-bound inference. A separately justified inverse
operator bound for an injective encoder is outside this reference.

## #61: Independent-run privacy audit

An AuditPlan fixes attack event/threshold, observer, adjacency, privacy unit,
calibration set and family size before confirmation. Trial/model-run/randomization
IDs must be distinct and disjoint from calibration runs. Declared independence
and actual model provenance still require design review; unique strings alone
cannot prove independence. Several scores from one model cannot be passed as
independent runs. One-run canary/generalization auditing needs its own theorem
and is intentionally unsupported by this binomial procedure.

Each of K predeclared tests receives family error gamma/K, divided between its
one-sided p lower and q upper bounds. Binomial tail inversion gives pL and qU;
the event inequality implies epsilon >= max(0, log((pL-delta)/qU)) when defined.
The implementation uses 80-digit Decimal positive sums and 80 bisections, with
outward float rounding. "Exact" describes the statistical binomial construction,
not a machine-checked floating-point enclosure proof. Counts are bounded at
20,000 per side, and each tail error must be at least 1e-12. Independent rational
PMFs test small-sample coverage and edge cases; the Chapter 48.2 golden reproduces
pL=0.082105334..., qU=0.0036820839..., epsilon lower=3.10451194... from the original
1,000/1,000 trials, 100/0 events, gamma=.05 and delta=1e-6.

Any failed/timed-out invited run makes inference inconclusive; it is retained
instead of being silently excluded. Reports name attack, observer, sample counts,
multiplicity, power declaration, confidence and limitations. A separate exact
event-rate test-power calculation is provided and explicitly is not joint DP-audit
power. A lower bound exceeding the claimed epsilon is a contradiction *under the
assumptions*; otherwise the audit is inconclusive. No privacy certification or
privacy-proof badge exists. The exact-binomial method is also documented by
[NIST](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).

## #62: Fixed classifier, held-out units and conditional fairness

A fixed exact linear classifier counts (k0,n0,k1,n1) on positive-label records.
Synthetic unit IDs must be distinct; repeated/clustered units need an alternative
statistical design. Count comparisons use exact rational arithmetic. Under fixed
classifier/group definitions and record add/remove adjacency, one record changes
at most a denominator and a numerator, giving L1 sensitivity at most two.

The HoldoutLedger binds observer, synthetic-record privacy unit, holdout version,
complete record contents and frozen classifier digest. New query IDs spend again;
an identical cached query returns the identical prior release without resampling.
Changing a model/holdout under the same version is rejected. Epsilon is reserved
before release and is not refunded after failure. This is an in-memory teaching
ledger, not durable concurrent observer accounting; #57 still owns that system.

Only synthetic records and a caller-supplied synthetic additive-noise tape are
accepted. This is explicitly **not an implemented DP sampler**. The finite-
arithmetic mechanism in #55 and protected computation remain dependencies.
The analytical certificate function separately assumes the manuscript's ideal
real-valued Laplace law. It consumes already released denominators and noisy gap;
it never emits exact private sample sizes. For b=(2/epsilon)*log(4/beta), each
denominator must exceed 2b. Observable ratio error and sampling radii are
2b/(n_tilde-2b) and sqrt(log(4/alpha)/(2*(n_tilde-b))). Add both groups' terms to
the noisy gap and cap at one. Confidence is at least 1-alpha-beta under the fixed
classifier/IID/noise assumptions. Missing assumptions or small denominators yield
inconclusive results, not repaired denominators. The original Chapter 56.4 inputs
give b=11.982929... and U=.589770924... at 95% conditional confidence.

Missing-attribute fractions lambda_0+lambda_1 and conditional distribution-shift
TV bounds rho_0+rho_1 add conservatively before capping at one. These allowances
must be independently justified/identifiable; no values are inferred from unknown
group attributes. The report distinguishes the noisy measured gap, conditional
population confidence bound, and the absence of a deployment fairness claim.

## #63: Exclusive event ledger and local profiling companion

`profile-ledger-1.0.0` is a reviewed companion for detail that CI-04 v1 cannot
express: prepare, train, witness, prove, transfer, aggregate, verify, setup,
evaluate and release events. Every event has one cost ID, contribution/attempt,
worker, interval, CPU work, bytes, outcome and cold/warm setup mode. Reuse references
point to earlier setup events; costs occur only once. Inclusive parent events
and overlapping intervals on one worker are rejected. Concurrent workers' occupied
time sums to work; earliest start to latest end measures wall time. CPU counters
must be exclusive per worker. Retries are counted per contribution, and failed
attempt costs remain in totals.

Live resource samples are updated jointly by timestamp and summed across workers;
phase peaks are never added. Sampled joint RAM/VRAM/disk peaks are lower bounds
unless all resource changes are observed. Missing memory/VRAM stays unavailable,
not zero. The actual one-worker CPU experiment separately reports OS process-
lifetime high-water RSS, including interpreter/imports. It is not a sampled or
sum-of-phase memory estimate. VRAM is explicitly not-run. Quality time requires
both a verified certificate and an authorized release; otherwise it is right-
censored with its budget. The native kernel has no such certificate and stays
censored. The Chapter 64.2 Amdahl and batch goldens are exact Fraction calculations,
separate from noisy-host measurements.

`native-profile-1.0.0` supplements the primary result contract with honest local
provenance, exclusive event/resource ledgers, warmups and raw timings. CI-04 v1
does not represent local executions or pending publication approval. No invented
GitHub run number or approval marker is used to force this companion into a
public result record. CI-11's common distribution summarizer is reused. Promotion
to primary scientific/public results requires a reviewed schema migration, actual
workflow identifiers where applicable, and publication review.

## #64–#65: Adequacy before comparison, exact CPU optimization

BackendEvidence includes exact relation/numeric semantics, guarantee, observer,
assurance mode, security/setup assumptions and delivered-payload binding. Special
properties, full training, recursion and attestation are different modes.
Only same-assurance, explicitly reviewed, non-placeholder research records reach
CI-11's existing comparison. Synthetic-test records, arithmetic-only kernels and
unsupported/not-run candidates cannot become proof benchmarks. Hardware,
parameters, assets and benchmark policy still have to match. A metadata review ID
is a declaration, not a substitute for reviewing the actual cryptographic adapter.
Results are diagnostic; selection remains unset until measured workload/resource
tradeoffs and an application policy justify it. The missing #33/#44 adapters
prevent a real multi-backend proof bakeoff here.

The exact CPU optimization compares modular matrix multiplication with per-term
reduction against transposed-column integer dot products with one final reduction.
Python integers avoid fixed-width overflow, so both compute the same element of
Z/modulus for every declared input; no primality/security property is needed.
Independent hand vectors, small-ring enumeration, negative values, range/shape
adversaries and randomized public test vectors check agreement. No approximation,
ML numerical relation change, privacy reanalysis shortcut or proof binding change
is claimed. Integrating this kernel into a proof/ML implementation would require
its own binding/conformance work in #26/#34.

The fixed native plan uses 32x32 matrices, modulus 2^61-1, six repetitions per
implementation, one retained warmup each and alternating order. Each repetition
uses a fresh process and includes input preparation, kernel, independent checks,
local buffer copy, fsync and launch/import/IPC cost. This measures a native CPU
pipeline, not full training/proving/aggregation or network transfer. RSS includes
the interpreter; temporary-file bytes and local-copy bytes are labeled. No timing
threshold gates PRs. GPU absence is not-run; CPU tests still exercise the reference
and interface. Any observed slowdown or negligible end-to-end improvement is
retained rather than relabeled a success claim.
