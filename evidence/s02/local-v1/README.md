# Session02 local mathematical evidence

Immutable source: `d5e28970a36b43ccc1a6f72b18fef41e9914c7d7`, clean at calculation time.
Reproduce with `./scripts/validate-s02` and
`PYTHONPATH=.:src .venv/bin/python scripts/run_s02_experiments.py .tools/s02`.
The adjacent [raw companion](math-run.json) validates against
`schemas/s02-math-run-1.0.0.json` and records fixture/lock/source digests,
assumptions, one retained deterministic calculation repetition and limitations.
It is not a CI-04 public report, independent approval or privacy-proof artifact.

Observed mathematical outcomes:

- Full-state RNE versus rounded-delta counterexample:2 versus1.
- Exact finite-law checks agree with the independent polynomial convolution;
  a support-mismatched truncated shift retains nonzero divergence.
- The book's hypothetical audit and fairness calculations reproduce their
  stated rounded values; no real model-training trials are claimed.
- The small-denominator certificate remains **inconclusive**, without repairing
  the denominator or claiming deployment fairness.
- A valid update from initial weight32 reaches34. The v2 parent format can
  encode34, but unchanged numeric-v1 rejects34 as a next initial weight;
  arbitrary indefinite chaining is unsupported.
- Original quadratic precision trajectories are recorded below. The unsafe
  learning-rate3 case is `rejected-state-domain` after
  2 accepted steps. The uniform-error
  margin condition distinguishes certified from only observed unchanged classes.

| Scale | Final weight | Objective gap | Stationarity residual |
| --- | --- | --- | --- |
| 1 | 0 | 1/18 | 1/3 |
| 2 | 0 | 1/18 | 1/3 |
| 4 | 1/4 | 1/288 | 1/12 |
| 8 | 1/4 | 1/288 | 1/12 |
| 16 | 5/16 | 1/4608 | 1/48 |
| 32 | 5/16 | 1/4608 | 1/48 |

All values above are exact rational reference calculations on original synthetic
inputs or explicitly labeled hypothetical book examples. They are not learning
quality, performance or production privacy measurements. Circuit cost, general
optimizer convergence and attention refinements remain not measured. A stored-
weight i32 margin does not prove a circuit's residual/no-wrap condition.

Validation performed:21 S02 mathematical tests passed;129 valid canonical cases,
14 malformed cases and129 wrong-output constraints checked through the external
Rust release CLI. The prior numeric-v1 asset bytes/hash are unchanged, and the
existing debug/release conformance and three controlled mutations passed. The
combined Python language suite has29 passing tests, including actual public
research-proof/binding tests and the independent S02 cases. Ruff/strict typing,
17 governance tests,16 pipeline tests and existing source/citation checks passed.
The wheel build, notice verification and isolated import smoke test passed.
These observations do not certify v2 Groth16 security or a general DP theorem.
The v2 envelope layout fixture deliberately contains an invalid zero proof.

Raw artifact SHA-256: `3142e7b12d986bbcf1c248e9f19f54c4d763a68ef92d0a69f47614871ca134ca`.
