# Session 04 infrastructure handoff

This integration supersedes the unavailable-backend snapshot in CI-DELIVERY.md.
It is stacked on PR #72 and incorporates the CI infrastructure from #68 and
Session 03's authoritative interfaces from #121 and Session 01's private proof
candidate from #75. Core cryptographic and numerical changes are imported from
their owning sessions without Session 04 edits. Dependency PRs remain
separately reviewable; this branch does not merge them on GitHub.

## Correctness and assurance

`./scripts/validate` runs pinned Rust formatting, Clippy and tests, Python lint,
strict typing, governance, serialization/evidence boundary tests, and both
Session 03 registry validators. `./scripts/s04-conformance` compares debug and
release CLI output with Session 02's independent Fraction oracle and golden
vectors. The PR aggregate requires foundation, genuine proof, conformance and
registry jobs to succeed. A skipped or unavailable proof cannot pass it.

`./scripts/research proof` builds and installs the actual native extension and
performs fresh Groth16 setup, proof generation and verification. Mandatory
rejections cover changed output, changed public counts, a different native
verifying key, malformed proof and trailing bytes. The independent oracle must
agree on output 9. Receipts bind source, adapter, contract, circuit, parameters,
native extension and keys. Local executions use null workflow identifiers;
hosted evidence requires its actual positive run ID. Dirty hosted sources fail.
`./scripts/reproduce --full` repeats the proof from a clean checkout; its
`--contract-only` mode reproduces metadata fixtures and makes no proof claim.

The implemented relation is public arithmetic for three clients and one
feature, with round-to-nearest-even semantics. It is different from the book's
M0 relation. These checks establish neither private/protected aggregation nor
cryptographic security, differential privacy or independent review. The
`protocol-invariants` profile deliberately reports unavailable and fails until
the corresponding implementation and reviewed interface exist.

The PR proof job additionally runs `./scripts/s04-private`: Session 01's actual
196,118-constraint private transition setup and two genuine proofs, twelve
statement substitution rejections and one-shot state checks. This candidate
has fresh random commitment blindings and private model/data witnesses. It
does not provide aggregate privacy, differential privacy or durable replay
protection. Its existing full conformance suite runs in main integration.
Private-transition scientific exports remain pending a reviewed evidence
interface; the public-arithmetic publication policy does not cover them.

## Execution tiers

| Tier | Trigger | Work and bounds |
| --- | --- | --- |
| PR CPU | pull request | Formatting, lint, units, schemas, oracle and one genuine proof; 15 minute job limits; no fork uploads |
| Main integration | main push or manual integration | Existing native Python/ML integration; separate unavailable protocol profile; one job at a time |
| Nightly | 03:17 UTC | Seeded 256-case adversarial conformance and existing mutation/Rust tests; one 600 second attempt |
| Weekly | Monday 04:43 UTC | Three proof attempts, each at most 240 seconds; two execution threads |
| Reports | main or manual, protected environment | Candidate generation, policy authorization, exact report regeneration before upload |
| GPU | disabled protected lane | Exits unsuccessfully; no provider, credits or paid workload enabled |

Schedules execute only after workflows exist on the default branch. All
research inputs are fixed public fixtures; profiles cap repetitions at five,
timeouts at 900 seconds, threads at two and input files at one MB. Expensive
research is never run from an untrusted pull request. Actions use full commit
pins, read-only source tokens and checkouts without persisted credentials.

## Honest evidence and publication

Result/bundle 1.1.0 bytes match Session 03's review at
`cb3590648f3a6d38c8092e6f24ee3ad1461daef4`; 1.0.0 compatibility is retained.
Operational journals record each attempted repetition, failure or timeout.
Missing executors produce unavailable records without invented measurements;
missing journals remain inconclusive. Workflow-run reconciliation reads job
metadata only and never executes downloaded artifacts. Timings distinguish
preparation, setup, witness, proving, verification and end-to-end work. The
128-byte proof quantity excludes keys and transport. Peak RSS is not measured.
Weekly attempts retain separate records rather than turning one proof into
three independent samples. Censored or lost work is not a successful result.

All new scientific candidates have `publication_review.approved=false`.
`ci/publication-policy.json` is a **proposal with no human approval**. Therefore
scientific rendering/upload and release export fail closed. Correctness can
succeed while publication remains pending. Initial/final bounded operational
journals are uploaded separately on trusted research runs; full scientific
artifact guards reject unapproved candidates. Uploads are best effort after
runner loss; metadata reconciliation cannot reconstruct missing measurements.

A real reviewer may approve a versioned, fixed public-synthetic producer policy
through protected source review. Approval must identify the actual reviewer,
date, scope, evidence URL and exact policy digest. Any producer/schema/scope
change invalidates it. The protected reports job then issues an automated
receipt binding the approved policy, actual run/source, candidate, claims and
each exported file. This is prior human policy approval, not invented per-run
human scientific review. Private/unknown inputs, manuscript data and unrestricted
attachments are outside this policy. An approved environment alone does not
approve the proposed policy. Session 03's handoff itself grants no approval.

## Activation and remaining specifications

Existing strict governance and DCO branch protections must remain. Add
`required-cpu` only after this workflow exists on main and a trusted main run
confirms the exact context. Adding it before prerequisite PRs land would block
their review. No new required check is activated by this branch, and no merge,
release, GPU job or large experiment is performed.

CI-14 through CI-25 acceptance specifications were not present in the inspected
issues or repository. They remain pending specification; this implementation
does not invent their acceptance criteria or claim those milestones complete.
Session 03's preferred invocation is
`PYTHONPATH=src uv run --locked python specifications/validate.py`; the compatible
`scripts/check_research.py` remains required too.
