# Session 02: retained local data/reference evidence

Calculation source: `424dff510f42024cda4a6e134f66c4e4e1156170`, clean at run start.
Raw `run.json` SHA-256: `5256340727b565126faa3c132daac568335064e5dd5f6cd36d1a5495a5757132`.
The user personally certified and authorized DCO sign-off for this PR and
regenerated evidence on2026-11-25. This is not independent scientific/security
review or publication approval.

The completed run retains all27 profiles:3 repetitions × N={64,256,1024} ×
Q={1,4,8}, with full-data, exact-summary and approximate-summary comparisons.
No profile was excluded. Exact loss/gradient errors are zero. The largest observed
approximate absolute loss error is51597/524288; all loss/gradient errors satisfy
the recorded deterministic bounds. The generator has33 unique pairs at most;
large N stresses repeated input volume, not additional people/information.

For Q=8 the raw full-row and summary setup+query times in seconds are:

| N | Full row loop, three repetitions | Exact summary, three repetitions | Approximate summary, three repetitions |
| --- | --- | --- | --- |
| 64 | 0.006153,0.006458,0.005742 | 0.001610,0.001633,0.001955 | 0.002120,0.001653,0.001889 |
| 256 | 0.023700,0.026394,0.023854 | 0.004564,0.004563,0.004522 | 0.004978,0.005704,0.004723 |
| 1024 | 0.096755,0.096993,0.090775 | 0.013018,0.013401,0.013057 | 0.016420,0.015918,0.020620 |

These are diagnostic trusted arithmetic paths on a shared Apple M3 Pro,
Darwin arm64,12 logical CPUs, Python3.11.14/SQLite as recorded; GPU unused.
Summary online time includes comparison/error-bound checks against a separately
generated reference. The full validated-comparison total adds that reference
cost. Common fixture generation/serialization is separately recorded once and
reused by three profiles. Application bytes are requested reads, not physical
storage traffic. All seven statistics, cache bytes, costs and actual Q-1 reuse
opportunities are retained. No uncertainty interval or statistically significant
speedup is claimed from three timings. Proof amortization is not-run/null:
the inspected fixed two-record integer ridge proof does not match this pipeline.

Four cumulative-window releases retain30,60,90,70mm and four unprotected observer
entries; restart/redelivery changes neither the accepted head nor disclosure
count. Actual child exits91/92/94/93 exercise precommit rollback, committed-event
recovery, snapshot rollback and observer-journal/SQL outbox recovery. This is not
a power-loss, Byzantine store, authenticated source or private publisher test.
The one-/two-alias negative is3/2 vs3/4 after a fixed canonical-entity map.
The join is trusted plaintext, not PSI or DP. A guessed small-domain hash and a
single-record statistic reveal their values. A forged cache statistic with a
recomputed checksum is accepted and gives the wrong derivation, demonstrating
the trusted builder/storage boundary rather than a correctness proof.

The full3-step untrained denoiser worsens zero-target MSE from5/8 to
75463969/36864000. The six-event simulated control return is-5. All states,
rewards and deterministic tapes are visible. No model training, real inference
proof, environment authenticity, adaptive-transcript privacy or family safety
claim is established. The bounded follow-up design is not-run.

Local validation passed20 new tests; the existing combined language lane ran66
with65 passes and1 existing optional external-runtime skip. Debug/release numeric
conformance accepted261/rejected11 plus1040 rounding cases, and all3 controlled
mutants were detected. Before the base integration, standard validation passed4 Rust,17 governance and16
pipeline tests. The updated base adds additional Rust/research checks; fresh
integration receipts are reported in the PR, separately from this local experiment. Ruff/format/strict mypy and synthetic regeneration checks passed.
The evidence checker verifies all27 profiles and rejects eight assurance,
missing/duplicate case, reuse, timing, arithmetic, crash and trajectory mutations.

The initial restricted-sandbox combined run blocked the pre-existing localhost
relay test; the authorized localhost run passed. A development CPU-model probe
also failed under the sandbox before a report was created; the final probe has
an explicit unavailable fallback and this retained run observed the CPU model.
Dirty preflight runs are not retained as clean-source conformance evidence.
Hosted CI receipts, once completed, are separate from this local experiment.

Reproduce using `experiments/s02-data/README.md`. The book fixture contains only
source-inspected mathematical facts/equations and locators from51.3,76.2,78.9;
current authoritative edition migration/review remains pending. No native EQ
catalog or scientific claim status is promoted by these results.

This final run refreshes source/lock pins after base integration and authorized
DCO history rewriting. Earlier unsigned candidates and their raw digests are
historical, superseded measurements. No source-derived or scientific claim is
promoted by contribution certification.
