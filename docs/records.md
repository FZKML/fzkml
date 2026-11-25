# Public record contract 1.0.0

`schemas/result-1.0.0.json` is the one result schema. The bundle schema references
that definition; the validator resolves only local, registered schemas and never
downloads references. Unknown fields and schema versions fail closed. Schema
validation is necessary but must be followed by the semantic validator in
`src/fzkml_ci/validate.py`. New incompatible fields require a new schema version
and reviewed migration rather than changing the meaning of an existing field.
These contracts are initial inputs to FZK-R003 (#14), pending that specification's
review; they do not substitute for the scientific measurement specification.

Every result declares statement/relation identity, numerical semantics, backend,
security mode, parameter/key/program/circuit digests, licensed model/data IDs,
source commit, workflow identity, dependency digest, toolchain and hardware.
Only synthetic/public asset identifiers are accepted. Exact asset versions and
publication permission are mandatory. The security mode is a declaration, not
certification of that mode. Public experiment seeds are distinct from protocol
and DP randomness: the latter is explicitly omitted. Never serialize witnesses,
secret shares, raw records, private randomness or participant identifiers.

Statuses are `not-run`, `unsupported`, `failed`, `inconclusive`, `successful`.
The first two cannot contain measurements. Executed records require repetitions
and non-placeholder source/dependency/workflow provenance. Timeouts must be
failed repetitions. A quality failure cannot be a successful repetition. Overall
success requires an included successful repetition; an overall failure contains
only failed repetitions. Inconclusive records may mix outcomes; all remain visible.
Failed retries can coexist with eventual success and must stay in the raw record.

Each repetition has a unique ID, attempt number, outcome, timeout/exclusion reason,
quality outcome and measurements by phase (`setup`, `prove`, `verify`, `train`,
`evaluate`, `communicate`). Time uses seconds, memory and communication bytes,
quality a ratio in [0,1]. A raw phase/quantity appears once per repetition. Retain
setup and failed-attempt costs in their own repetitions instead of relabelling
them as successful proof costs. Exclusions remain visible, with a reason; do not
drop them from the raw bundle. Each summary declares mean/median/min/max/sum,
retained repetition IDs and phase/quantity/unit. The validator recomputes it and
rejects dangling references, excluded inputs and duplicate metrics. A repetition
is referenced once per metric, preventing retry duplication within an aggregate.
Interpretation of which phases belong to a cost total remains the reviewed
experiment's responsibility. No universal total or ranking is inferred.

Every public record includes limitations and an explicit publication review ID.
Optional privacy accounting declares mechanism, privacy unit, epsilon and delta;
this records metadata and does not prove a differential-privacy guarantee.

Claim IDs use `FZK-<EDITION>-C<CHAPTER>-<TOPIC>-<NNN>`, for example
`FZK-V01-C35-RELATION-001`. Chapter and edition must match source metadata.
Claims explicitly declare observer, privacy unit and numerical semantics as required
by the shared FZK-R001 extraction contract. Claims distinguish definitions,
assumptions/theorems, cryptographic security,
implementation relations, empirical hypotheses, reference results and adoption
outcomes. Each requires scope, assumptions, owner, source version, responsible
issue, evidence class and limitations. Section/equation fields may use an explicit
`none` identifier when not applicable.

The authoritative claim statuses are `planned`, `specified`, `implemented`,
`tested`, `replicated`, `reviewed`, `refuted`, `inconclusive`, `unsupported`,
`deferred`. Status is authored; CI never promotes it based on a passing test.
Formal-proof and independent-review scopes and artifacts are separate attributes.
A unit test cannot serve as a formal-proof artifact and `formally-proved` is not
a claim status. An artifact's declared kind still requires human review; this
tool cannot certify that a file is a sound formal proof or an independent review.

Evidence paths must resolve inside the repository and exist. Python unit-test
references use `tests/test_file.py::test_function`; CI checks the function exists.
Run claim IDs and claim evidence IDs must resolve. Coverage lists all ten statuses,
unmapped claims and extraction pending R001; deferred/unmapped does not mean passed.
`claims/registry.json` is the default public-report registry. #12's source
locations, companion scientific context and chapter/exercise coverage are in
`docs/research/`; extraction remains partial and native equations await source
review. `examples/claims.json` remains an empty infrastructure test fixture.
Synthetic schema tests are not imported book claims.

Reports preserve exact inputs, claim scopes, all repetition failures/exclusions,
limitations, source and run links. Inputs regenerate identical output bytes,
without timestamps or network access. Comparison groups include statement,
relation, numerical semantics, backend/security, assets/digests and hardware;
each metric has its own raw-repetition plot. There is no cross-group leaderboard.
