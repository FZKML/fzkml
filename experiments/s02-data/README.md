# Session 02: bounded data lineage and model-family references

This is the Python reference slice for #96–#100 (planning IDs FZK-R058–R062).
It provides executable ideal functionalities, exact rational comparisons and
original synthetic experiments. It does not implement cryptographic PSI,
production streaming consensus, a DP release mechanism or a new model-family
proof. These missing components remain explicit integration/research work.
No Rust, peer specifications, shared result/bundle schema or workflow is changed.

| Issue | Implemented reference and negatives | Remaining boundary |
| --- | --- | --- |
| #96 | Complete three-call 2×2 denoising trace; exact vs scale16 nearest-even arithmetic; six-event simulated control; wrong reward units, invented events, truncated paths and copied training sample negatives | No training, inference proof, real environment authenticity, adaptive transcript DP or family/safety conclusion |
| #97 | Three-organization source inventory; canonical immutable partitions; schema, units, entity/time split and versioned preprocessing DAG; content-addressed snapshot | Trusted builder/source declarations; selected membership does not establish real population completeness, rights or truth |
| #98 | Trusted plaintext three-way join; duplicate multiplicity; fixed entity mapping/cohort, local contribution cap, clipping and authorized aggregate view; missing-correspondence counterexample | Ideal functionality only; role strings are caller declarations, no PKI or private PSI. Diagnostics are operator-only synthetic data |
| #99 | Versioned event ingestion, late/corrected/tombstone records, cumulative event-time windows, parent-bound snapshots, four exact releases, durable observer outbox and process-crash recovery | Trusted local SQLite/journal and operator correction authority; no Byzantine storage, real publisher or power-loss guarantee |
| #100 | Full rows vs seven exact sufficient-statistic scalars vs bounded approximation; context-bound cache; cold/setup/query costs, bytes and actual reuse | Trusted statistics builder/storage; no matching summary/witness proof circuit, so proof amortization is not-run |

## Reproduce

Use the repository's locked Python3.11.14 environment and standard dependencies:

```sh
uv sync --locked --group ml
./scripts/validate-s02-data
PYTHONPATH=.:src uv run --locked python scripts/run_s02_data.py .tools/fresh-data-run
PYTHONPATH=.:src uv run --locked python scripts/check_s02_data_evidence.py .tools/fresh-data-run --mutations
```

The retained-evidence checker requires a clean calculation source committed as an
ancestor of HEAD. A development run can execute on dirty source but cannot pass
that evidence gate. Output directories must be fresh. Running/completed/failed
status is retained incrementally; failures are not silently excluded. The
`--require-real-proof` option fails because a matching backend is unavailable.
The existing language unittest loader includes the20 new cases; the dedicated
command additionally checks formatting, strict types, deterministic vector
regeneration and, when present, the retained evidence and eight mutations.
Existing CPU/governance checks alone are not evidence for these20 cases.

The bounded matrix is3 independent timing repetitions × N={64,256,1024} ×
Q={1,4,8}:27 profiles with exact and approximate modes in every profile.
There is no randomized subject sample or inferential confidence interval.
The generator has at most33 distinct (x,y) pairs; larger N repeats rows to stress
input volume. These repetitions are not additional people or information.
Generation/serialization is recorded once per repetition/N and reused by three
Q profiles. There is no undeclared model-weight or cryptographic preprocessing.

## Numerical contracts

For frozen features z=(1,gx), |x|,|y|≤2, 0<g≤2, and |theta_j|≤2, the reference
computes the **mean** objective J=(sum(z theta-y)^2)/(2n)+lambda||theta||²/2.
It stores n, S00, S01, S11, T0, T1 and q, where S=sum zᵀz, T=sum zᵀy and
q=sum y². Thus gradient=(S theta-T)/n+lambda theta. The redundant S00=n is
explicit. q is necessary for the absolute loss. Sum and mean regularization
are different: their normal matrices are S+lambda I and S+n lambda I.
An independent direct row loop checks every exact objective and gradient using
`fractions.Fraction`; no Rust or proof executable supplies these results.

The approximate mode rounds feature1 and y to the nearest multiple of1/2 with
ties to even. Let B=2g, R=|theta0|+|theta1|B+2 and
Delta=(|theta1|+1)/4. Since each rounded value changes by at most1/4,
|J'-J|≤R Delta+Delta²/2, |g0'-g0|≤Delta, and
|g1'-g1|≤Delta B+(R+Delta)/4. The ridge term is unchanged. These are deterministic
bounds for this bounded quadratic, not general model quality or privacy bounds.
The raw report retains every observed error alongside its bound.

Summary keys bind the source snapshot, frozen feature descriptor, numeric
relation, schema, preprocessing and policy. Head-dependent mathematical witness
keys also bind theta, but are explicitly **not proofs**. A cache checksum detects
ordinary drift only: changing a statistic and recomputing the checksum is accepted
by this trusted-store reference and yields an incorrect derivation. The report
retains that negative. Even a legitimate one-record T0 exposes its label.

The ideal join uses K=2 slots per canonical entity, clip C=3cm and fixed public
W=8. Sorting/capping is entity-local, so changing one entity cannot displace
another. Add/remove-entity sensitivity of sum/W is KC/W=3/4cm; replacement is
2KC/W=3/2cm. The bound assumes the public roster, denominator and canonical
privacy-unit mapping are fixed and other entities do not change. Both bounds
are attained in tests. Aliases counted separately give3/2 in the retained
negative; a fixed two-alias/one-entity map restores3/4. This does not solve
personhood. A private changing denominator is a different function. Neither
sensitivity nor empirical testing proves an implemented mechanism is DP; see
[NIST SP800-226](https://doi.org/10.6028/NIST.SP.800-226).

## Observers, snapshots and streaming

Source/schema/transform/policy changes alter snapshot identity. Unit conversion
is exact cm→mm. The selected source inventory, exclusions, train/holdout policy
and preprocessing parent DAG are hashed. Verification without a separately
trusted inventory is selected membership only. Even supplying the complete
synthetic fixture inventory establishes completeness only relative to that
inventory. Hashes authenticate neither source truth, copyright authority nor
real timestamps; an unsalted small-domain hash permits the retained dictionary
attack. Metadata and authorized aggregate outputs can themselves leak.

Events have stable IDs, sequential versions and previous-event hashes. A retry
of identical transport has one accepted effect; changed content under the same
version fails. Closed-window revisions need an explicit trusted operator action;
tombstones bind the current row and are terminal in this reference. Each round
binds old/new source state, watermark, roster, policy and snapshot parent. Four
releases sum to30,60,90,70mm; corrections/deletion never erase earlier observer
releases. The cumulative window is [0,watermark], not an expiring sliding window.

A reserved cached release is journaled in the unchanged ReferenceAccountant
before SQLite marks it accounted. Recovery redelivers the same payload and
idempotent observation; it does not sample a fresh output or refund an old one.
Every exact release is explicitly unprotected. The local four-slot quota is not
a privacy budget; zero numeric epsilon fields do not assert zero privacy loss.
The observer has all four releases. No external publisher is integrated.

Actual child processes terminate before ingestion COMMIT, after COMMIT, before
snapshot COMMIT, and after the observer-journal write but before SQL accounting.
The expected zero/one effects and unchanged observer history are checked after
reopening. Concurrent identical-ingestion retries are also exercised. These
are local process failures, not power loss or adversarial whole-store rollback.
SQLite durability relies on its filesystem/storage assumptions, as documented
in [WAL](https://sqlite.org/wal.html) and
[synchronous](https://sqlite.org/pragma.html#pragma_synchronous).

## Tiny generative and control paths

The denoiser follows the eta=0 DDIM update with rational signal/noise pairs whose
squares sum to1, an untrained epsilon(x)=x/4 and a fixed public initial array.
The mathematical update follows the authors' [generalized sampling definition](https://github.com/ermongroup/ddim/blob/main/functions/denoising.py);
no external implementation, learned weights or dataset is incorporated. The
initial tape is deterministic, not a Gaussian sample or privacy noise. All three
calls (12 scalar pixel updates), exact and scale16 results are retained. An
independent gain product8687/4800 checks the trace. Against the declared zero
target, MSE rises from5/8 to75463969/36864000: this untrained toy worsens the metric.
The control simulator starts at3, moves toward0 and uses reward=-(next_state)^2
in negative-squared-grid-position units; its six-event return is-5. All states,
actions and rewards are visible. A simulated transition is not evidence that a
real-world event happened. The exact training-copy negative only detects its
declared exact case, not general memorization resistance. The versioned config
specifies a bounded follow-up design before any expansion; it has not run.

## Timings and proof boundary

Full-data timing includes JSON reads/parsing and all direct Fraction queries.
Each summary mode records input read/build/cache write, Q cache reads/evaluations,
comparison checks, first-query estimate, cold total and amortized cost. Online
comparison timing includes error-bound checks against already generated direct
references. Their measured generation cost is also retained, and the full
validated-comparison total includes it. Raw application bytes count requested
file reads, not physical disk traffic; page cache and host load are uncontrolled.
The arithmetic-path break-even floor(setup/(full/query-cached/query))+1 is
reported only when the denominator is positive. It is a diagnostic estimate,
not a protected, trust-equivalent or statistically significant speedup. Actual
reuse opportunities are Q-1; a larger extrapolated break-even is not measured.

The inspected [existing model contract](https://github.com/FZKML/fzkml/blob/b602197104d810bc1a41a2ea24085b25484272b7/specs/models/model-capacity-v1.json)
proves a fixed two-record integer identity-feature, sum-objective ridge relation.
It does not prove this variable-size rational mean objective, source→summary
pipeline or cached witness. Consequently all proof costs/break-even fields are
null/not-run. Prior scalar or fixed-shape proof timings are not transferred.

## Manuscript provenance and review

`tests/vectors/book/data-lineage-v1.json` contains only inspected mathematical
facts from51.3/Figure51.1 (2×3 duplicate multiplicity),78.9 (equal/opposite binary
joint laws with identical marginals), and equations from76.2 (sum/mean ridge and
statistics). It pins the observed native revision, export SHA, heading IDs and
UTF-16 ranges from the canonical Google Doc. The observed edition label is
MS20261125; no author-declared edition or atomic export/native snapshot is claimed.
Historical/current authoritative edition migration remains pending; no old EQ IDs
or Session03 claim statuses are reassigned. No manuscript prose/image/export is
redistributed. New benchmark values are original synthetic, not book examples.
All uninspected model-specific manuscript values remain pending-source-review.
Contributor DCO, independent scientific/security review and publication approval
are separate decisions; this local companion grants none of them automatically.
