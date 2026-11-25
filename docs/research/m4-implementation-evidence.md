# M4 Session 03 evidence and handoff

Branch: `codex/s03/m4-scaling-contracts`, stacked on PR #121. Claimed specification,
source-mapping and adversarial-conformance slots: #76, #77, #78 and #79. Full
backend/performance acceptance remains open; see the per-issue matrix in
`specifications/m4/README.md` and machine-readable `contracts-v1.json`.

The canonical Google Doc revision readback on 2026-11-25 matched MS20261124.
Selected prose sections 46.4, 65.2, 65.5, 66.3, 68.4 and 71.2–71.4/73.3 were
inspected from the matching authorized paragraph snapshot. Exact source IDs and
ranges are recorded in `m4-source-review.json`. No manuscript body, export, image
or equation XML is distributed. No new native-equation/source-numerical claim or
external-paper theorem is verified. The source graph and 23 scientific claim
statuses remain unchanged; engineering requirement IDs and empty claim links
prevent synthetic reference checks from promoting book claims.

The executable reference covers nine memory configurations, replay/context/
truncation rejections, 8/32/128 synthetic queue loads, concurrent completion and
cancellation, two-layer certificate mutations, direct/relay logical cohort
preservation and subgroup disclosure. Measurements explicitly distinguish Python
allocator peak from unmeasured RSS/VRAM, application file bytes from physical I/O,
and reference timing from unexecuted genuine proving/finalization. Local output
is schema checked and unapproved for scientific publication.

Session 01 should consume exact state/key/roster/conservation/availability and
checkpoint/queue admission contracts through its own real verifier/ledger and
proof backend. Session 02 may consume the original synthetic definitions and
source locators for independent experiments; no numerical implementation or
experiment is overwritten here. Session 04 may consume the authoritative
validator, named tests and raw-reference schema; canonical reports/publication
remain its ownership. No CI workflow/shared schema is changed by this branch.

Ruff, strict mypy, named unit tests and both source/claim checks are the validation
plan. The complete locked repository suite, source archive and local runner are
checked before publishing the draft. Actual final commands/results are attached
to the PR; they establish only their declared conformance scope. Independent
scientific/security review, genuine backend evidence and publication authorization
are not inferred from green checks.

A follow-up Docs metadata read on 2026-11-25 returned a different revision token.
The earlier read and selected cached prose remain an explicitly historical
MS20261124 inspection; current-edition mapping/content equivalence and migration
are pending-source-review. No source graph, equation count or claim status is
relabelled from that token alone. The M4 engineering fixtures are original
synthetic definitions, so their checks do not depend on a new book golden.

Actual local validation: the locked `./scripts/validate` passed all 119 Python
tests, Rust formatting/Clippy/scaffold checks, governance/license/provenance and
citation checks, research metadata, fixture reproducibility and workflow policy.
Additional Ruff formatting/lint and strict mypy passed for `specifications/`,
`test_m4_contracts.py` and `test_specification_registry.py`. The local runner
completed nine memory configurations, three queue loads and all specified
structural/adversarial checks; it retained unapproved synthetic-reference scope.
Initial development lint/type findings were corrected before these checks.
