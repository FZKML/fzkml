# S03 source and evidence audit

Edition MS20261124 is a local registry label, not an author-declared publication
edition. The connected Google Doc revision readback matched the revision observed
before the authorized DOCX inspection. `s03-source-inspection.json` records its
exact identity, private export digest and qualification: there is no server-signed
atomic export attestation. No export, manuscript body, images or equation XML is
included in this contribution.

The stable graph indexes 80 chapters, 48 exercises, 378 section/chapter-heading
anchors and 417 native equation locations (923 nodes). Index coverage is distinct
from extraction. Twenty native math elements have inspected markup, including
six Chapter 40 elements newly inspected for the worked update; 397 remain
`pending-source-review`. There is no claim that all book prose or mathematics
was inspected. New source revisions require a reviewed edition/migration record;
UTF-16 offsets are valid only for the identified revision.

The existing 23 scoped claim IDs retain their statuses: eight planned, ten
specified and five tested analytic/synthetic references. The five named tests
were observed in the successful hosted CPU run 45304417381 at
`be22d33427c8e4ff4abaec41467447482668e633`; the overlay pins test/module contents,
execution and source commit. No empirical replication, formal kernel artifact,
independent scientific review or integrated security/DP guarantee is added.

The exact implemented scalar relation differs from the manuscript/M0 two-feature
worked step. `specifications/relations/fzknum-1.0.0.json` records the current
three-client scalar nearest-ties-even full-state computation, its bounds and
pinned implementation contract. Candidate joint-private and protected-aggregation
profiles are references to immutable peer commits, not implementations adopted
or independently reviewed by S03. The source-input transcription is explicitly
pending an independent numerical calculation. The full-state/delta rounding
counterexample is an original derivation, separately labeled for Session 02.

The supplemental schemas, offline validator and mutation tests detect broken
source/test/evidence references, unreviewed edition drift, content hash changes,
relation mismatch, unsafe paths, unknown schema fetches and unsupported status
promotions. Structural checks cannot establish the honesty of an externally
supplied checker receipt or reviewer. Formal claims require the precise theorem,
axioms/kernel/version, exact claim-context digest and checked artifact/receipt;
independent reviews require an identified independent reviewer and a bound
source/scope receipt. Session 04 must verify approved checkers and execution
provenance before relying on declarations. No arbitrary record-supplied command
is executed by this validator.

Original S03 code, specifications, metadata and documentation are inventoried in
`compliance/files.json`; no dependency or restricted asset is added. Other
sessions' numerical implementations, experiments, shared schemas and CI
workflows are unchanged. The PR remains a draft pending the required independent
domain review; it must not be merged as scientific or security approval.

## Actual local validation on 2026-11-24

The locked offline `./scripts/validate` passed: Rust format/Clippy/scaffold tests,
Python lint/format/strict CI types, governance/provenance/license and citation
checks, research/schema checks, fixture reproducibility, all 101 Python tests,
workflow policy and unchanged lock files. The new registry has 29 mutation tests.
Additional Ruff lint/format and strict mypy checks passed on `specifications/`
and `tests/test_specification_registry.py`. The existing research test also
passed lint/format after its fixture-copy adjustment.

The first full run exposed that the older metadata test copied a fixed set of
directories and omitted newly inventoried contracts. Its public test fixture now
includes the evidence manifest's referenced files; the targeted test and full
suite then passed. This was a test-input packaging failure, not a scientific
experiment outcome. The installed uv tool uses the previously established
outside-sandbox workaround for macOS system-configuration access; the validation
itself used locked, already installed toolchains without fetching dependencies.

Report generation and exact report verification with the canonical 23 claims
passed; all five scaffold scientific runs remain not-run. Source archive
construction and its reproducible-content tests passed. No manuscript bytes,
private input caches or foreign worktrees are inventoried archive contents.
Hosted checks must still be inspected on the actual pushed PR head; local checks
do not constitute independent scientific/domain review.
