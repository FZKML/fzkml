# Session 02: retained local data/reference evidence

Calculation source: `0705c92352b98ce056b2b2df8d7bc3c096dd7928`, clean at run start.
Raw `run.json` SHA-256: `9e6e5f460a06df745742a01dd46b44e4ec6b4bacfaf04457c6f7224f632ed551`.
Contribution certification for #96–#100 is pending the user's review of this draft;
this is not independent scientific/security review or publication approval.

The completed run retains all27 profiles:3 repetitions × N={64,256,1024} ×
Q={1,4,8}, with full-data, exact-summary and approximate-summary comparisons.
No profile was excluded. Exact loss/gradient errors are zero. The largest observed
approximate absolute loss error is51597/524288; all loss/gradient errors satisfy
the recorded deterministic bounds. The generator has33 unique pairs at most;
large N stresses repeated input volume, not additional people/information.

For Q=8 the raw full-row and summary setup+query times in seconds are:

| N | Full row loop, three repetitions | Exact summary, three repetitions | Approximate summary, three repetitions |
| --- | --- | --- | --- |
| 64 | .005499,.005479,.005473 | .001437,.001446,.001453 | .001570,.001636,.001540 |
| 256 | .022050,.021721,.021677 | .003707,.003614,.003491 | .004093,.004017,.004205 |
| 1024 | .088979,.086660,.085114 | .012096,.011857,.012055 | .014482,.014053,.016797 |

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
mutants were detected. Standard validation passed4 Rust,17 governance and16
pipeline tests. Ruff/format/strict mypy and synthetic regeneration checks passed.
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
