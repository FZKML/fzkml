# Session interfaces, S03 version 1.0.0

These are reviewable contracts, not instructions to overwrite another session's
implementation. The source map and evidence overlay are authoritative for
scientific traceability. Downstream sessions add evidence against exact versions;
S03 reviews registry changes. CI cannot approve a scientific claim automatically.

## Session 01: exact relation and proof boundary

Consume `relations/fzknum-1.0.0.json` for the existing implementation. Its domain
is three clients, one scalar feature and one selected record per client, scale
16, learning rate 1/4, signed exact arithmetic and nearest ties-to-even at every
specified division. The released value is the rounded count-weighted average of
full local states. A modular inverse, a real-number approximation or a rounded
delta average is a different relation. The JSON lists every intermediate bound
and an original counterexample for Session 02's independent confirmation.

A proof statement must bind protocol/relation/parameter/key versions, trusted
expected context, parent and complete model/optimizer state, ordered accepted
roster/weights/denominator, authenticated input commitments and output. Secret
witnesses contain the exact records/model openings/randomness that the chosen
profile actually uses. Field range constraints must prevent wraparound in all
integer quotients/remainders/intermediates. Public input encodings must be
canonical and checked against independently trusted expected context.

The manuscript/M0 relation (`m0-two-feature-v0.1`) is a separate target. Do not
link the scalar proof to `FZK-MS20261124-C40-REL-001` as implemented/tested book
conformance. The transparent, joint-private and protected-aggregation profiles
also differ in witness custody and authorized disclosure. A joint prover learns
all witnesses; individual local proofs do not establish aggregation conservation,
durable release uniqueness, admission truth, useful learning or DP. See the
protocol's explicit review obligations and observer views.

## Session 02: inspected inputs and numerical evidence

Use `claims/source-map-v1.json` IDs and include `source_version`, exact `source_refs`,
source inspection record, profile/relation ID and expected-trace digest in vector
metadata. Stable IDs are edition scoped; native UTF-16 aliases are locators for
the observed revision, not permanent offsets for a later edited manuscript.

The Chapter 40 source-inspected worked-step parameters are in
`source-inputs-v1.json`. Their expected trace is source transcription checked
against inspected markup/prose, not an independent oracle result. Keep all
rounding stages and the learning rate explicit. Place independent calculations
and adversarial/generated fixtures in separately labeled records; do not call
invented values book examples. The RNE full-state/delta counterexample is an
original derivation awaiting independent oracle adoption.

Existing source-inspected analytic parameters and their limits are in
`docs/research/transcript-source-review.json`: Chapters 47, 53, 67 and 75. No
new verified inputs for issues #61/#62/#63 are supplied by this S03 change.
Chapter/section indexing alone is insufficient; inspect the relevant native
math before declaring a source-dependent expected value verified. Do not promote
unit/reference tests to empirical replication, finite-sampler DP, adaptive
learning results, formal proofs or independent review.

## Session 04: CI and reporting

Preferred standalone command from the repository root:

```sh
PYTHONPATH=src uv run --locked python specifications/validate.py
```

The command is offline, read-only and exits nonzero for invalid source/evidence
metadata. Keep the earlier `scripts/check_research.py` as a compatible broader
research check. New negative tests are auto-discovered by the existing unittest
suite; explicit invocation is documented in `README.md` in this directory.
Run Ruff and strict mypy on `specifications/` and
`tests/test_specification_registry.py` in an S04-owned integration if desired.
No workflow or CI implementation is changed by S03.

Keep `schemas/claims-1.0.0.json` authoritative; `claims/schema-v1.json` is only a
local alias. The traceability and source-map schemas are supplemental closed
contracts. Ten authored statuses remain compatible with CI-05. Formal and
independent-review evidence are separate fields, not invented status strings.
Use `reporting-requirements-v1.json` for category/measurement/publication rules.
A validated external receipt remains declared metadata until the approved
checker/reviewer and exact artifacts are independently verified. Do not run
arbitrary checker commands supplied by a claim record. `claim_binding()` in the
validator defines the canonical JSON digest binding source, assertion, scope,
assumptions, relation and specification to a formal/review receipt.

Result/bundle 1.0.0 remain supported. The result/bundle 1.1.0 proposal in PR #74
adds truthful local execution nulls, phase names and unapproved publication
records. S03's review supports those semantics under the listed requirements;
S04 owns integration and must exercise its canonical schemas/renderer/policy.
An unapproved result may be archived privately/local for audit but must not be
published. A schema-valid boolean is insufficient publication review. Do not
rewrite a local run as a hosted workflow or erase failed/not-run outcomes.
For allowlisted public-synthetic CI producers, a real prior human approval may
cover a versioned policy rather than every random seed. Per-run automated
receipts must bind actual outputs and successful enforcement to the approved
policy, producer, schemas and protected environment. Clearly distinguish the
human policy approver from the automated verifier. Until the actual policy is
reviewed and authorized, records remain unapproved; this proposed interface
does not grant approval. Other inputs/producers/scopes need their own review.

No published CI-14–CI-25 specification was found in the audited issues/files on
2026-11-24. Treat those identifiers as pending specification rather than inventing
acceptance requirements or claiming their completion. Existing CI ownership for
#15/#16 remains with the CI session; S03 supplies the source/evidence interface.
