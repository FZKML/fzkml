# CI evidence gates v1

These gates cover issues #116 through #120 on original synthetic inputs.
The checked-in fixture fixes the schedule, the stream snapshot, the notable
release mutations and the outcome seeds. The machine record schema is
`evidence-run-v1.schema.json`. Raw timings from the benchmark fixture are
synthetic. The model pilot's subprocess wall times are measured.

## Run and verify

From the repository root with the locked toolchain installed:

```sh
./scripts/ci-evidence --output /tmp/fzkml-ci-evidence
```

Choose a new destination. It contains `evidence.json` and `portal.html`.
The script validates the authoritative claim registry, runs six focused tests,
builds the existing native CLI and verifies three new CPU Groth16 proof runs.
It then deliberately injects an unequal relation into a positive comparison.
The mutant must exit 1 at the named gate before any proof or report generation.

The existing CPU workflow runs the same command with a 15 minute job limit
and read-only repository permissions. It writes a bounded job summary.
The preview is a local file; the protected publication workflow and its
reviewed allowlist govern public deployment. No registry statuses or identities
are written by this command.

## #116 · Benchmark validity

One warm-up and three measured attempts must appear in the same order for each
arm. The schedule is fixed before observing the result. Each attempt must have
its own ID, completion state, time and quality status. Exactly the declared
warm-ups may be excluded. A missing attempt or timeout produces an
`inconclusive` result without a ranking. A differing statement, numeric
scope, hardware or setup policy is `unmatched`. A complete comparison reports
raw seconds and sample variance through the existing CI-04 comparator.

This exercises CI-11 and FZK-R035. It supports a bounded diagnostic
comparison. It does not measure hardware performance or calibrate a CI
regression threshold.

## #117 · Snapshot and stream lineage

The initial canonical JSON row list must match the expected SHA-256. Exact
normalization accepts `Wh` and `kWh` with fixed integer bounds and requires
the declared unit for future corrections on each row. Corrections for the
fixed watermark use the half-open event-time interval
`[watermark - horizon, watermark)`. Each accepted event has a new ID and the
next row revision at the original event time. In this fixture the second
correction replaces the value with zero.

A release identifies its state digest, predecessor receipt and ordered
release ID. Replaying an event, changing the unit or source, releasing the same
state twice, or using a stale parent fails before mutation. This exercises
the FZK-R059 and FZK-R061 dependencies in one in-memory process. Crash
recovery, storage, partition manifests, true deletions, and concurrent writer
or release behavior need additional evidence.

## #118 · Provenance and leakage

The synthetic candidate includes one dataset and one checkpoint and has an
explicit synthetic approval flag. Both assets must match their approved inventory license, SHA-256, and explicit
redistribution decision. Training and evaluation entity IDs are distinct.
The release check consumes only bounded public text and rejects a literal
synthetic canary case-insensitively. The machine record keeps the rejection
code instead of reproducing the leaked payload.

The fixture exercises the GOV-08 and CI-10 requirements and the FZK-R053
retrieval/canary boundary. A literal-string gate says nothing about
semantic leakage, transformed canaries, model extraction or privacy.

## #119 · Outcome comparisons

Seeds 17, 23 and 41 produce fixed original three-client training examples
under fzknum-1.0.0. The local-only baseline is the first client's native
update. Ordinary federated evaluates the full-state weighted aggregate.
The transparent proof-backed arm proves the same canonical input on CPU,
with the existing `fzkml-contract smoke` command. Native output must agree
with the independent exact rational calculation. All supported arms use
the same four entity-disjoint evaluation records, same RNE prediction and
same absolute-error denominator. Raw errors and counts are retained for
groups A and B. Timings include process launch; the proof time also includes
fresh setup. The release pilot has no accelerated hardware dependencies.

A controlled label mutation changes the model outcome. A modeled timeout
drops one predeclared seed and changes the group B survivor-only error.
The reported result is inconclusive whether the timeout is kept or hidden.
An unavailable, skipped or canceled execution cannot satisfy the gate.

The protected FL and protected-plus-proof arms remain unsupported on this
matched full-state fixture. A separate proof for a different relation cannot
fill those rows. The pilot exercises FZK-R004, FZK-R065 and CI-04 without
claiming an executed four-arm deployment or a factorial study.

## #120 · Claim coverage preview

The static page projects the authoritative registry, trace attestations and
source map. It shows original claim ID, evidence class, status, manuscript
source IDs, source extraction state, tested commit and reviewer evidence when
present, and limitations. It shows unavailable or mismatched references as
such and retains failed executions visible in the source records.

A unit test cannot promote a security claim or theorem without a bound formal
artifact. Authored independent review is a separate evidence channel. The
page is a scoped review preview of CI-05, CI-06 and FZK-R070. It does not
publish manuscript contents or feed results back to the manuscript.
