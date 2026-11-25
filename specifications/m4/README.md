# M4 scaling contracts, version 1.0.0

These contracts fill Session 03's specification, source-mapping and adversarial
validation slots for #76–#79. They do not complete the backend or empirical
acceptance criteria. `contracts-v1.json` assigns stable engineering requirement
IDs; its empty `claim_ids` deliberately prevents synthetic references from
becoming manuscript scientific claims. The existing 23 claim statuses and
20 inspected/397 pending native equation counts are unchanged.

The connected canonical Google Doc revision matched the MS20261124 snapshot on
2026-11-25. `docs/research/m4-source-review.json` identifies the selected prose
sections inspected. Chapter/exercise IDs are coverage locators. Native equations,
external-paper results and numerical book goldens are not newly verified here.
All fixtures below are issue-defined or original synthetic examples.

| Issue | Delivered in this slot | Still required for issue completion |
| --- | --- | --- |
| #76 | Same witness/statement across RAM, regeneration and temporary-file references; checkpoint identity/position/replay/truncation checks; explicit work/file-byte/allocator diagnostics | Genuine prover adapter, per-role RSS/VRAM/physical I/O, mid-prover termination/recovery and actual setup/prove/verify/ZK-finalization costs |
| #77 | Bounded admission reference and atomic in-memory identity state; concurrent duplicate completion/cancellation tests; resource and identity-history limits | Canonical durable accepted-ledger integration, genuine verifier workers, actual p50/p95/p99/resource load and participation-bias review |
| #78 | Two-layer transparent certificate checker for exact context/roster/weights/sums/availability annotations; adversarial mutations | Existing recursion/folding/aggregation scheme integration, genuine cryptographic checks, authenticated availability/base cases, depth-aware soundness and ZK finalization |
| #79 | Direct/three-relay cohort and observer-policy checks; global/partial-sum counterexample; whole-topology threshold/dropout rules | Protected payload/transport/recipient backend, authenticated accepted state, measured transfer costs and independent topology/privacy review |

## Reproduce the bounded checks

From this branch's repository root, with its locked Python environment:

```sh
PYTHONPATH=src uv run --locked python specifications/validate.py
PYTHONPATH=.:src uv run --locked python -m unittest discover -s tests -p test_m4_contracts.py -v
PYTHONPATH=.:src uv run --locked python -m specifications.m4.run --output /private/tmp/fzkml-m4-reference.json
```

The preferred authoritative validator also checks the M4 schema, source IDs,
revision and required-test links. The runner schema validates its local result,
then checks complete case coverage, same-statement conservation, application I/O
counts, queue bounds/count conservation and the subgroup counterexample. Its
output includes source SHA/dirty state, contract/context/lock digests, source
version, original synthetic data identity, environment, raw per-configuration
observations, reproduction command and missing phases.

The output is a local **synthetic reference** artifact with
`publication_review.approved=false`. It is not a canonical public scientific
report or authorization to publish one. Session 04 owns any reviewed conversion,
publication, archive and CI integration. No workflow is changed here.

## Memory and checkpoint semantics

N=64/256/1024 denotes synthetic eight-byte witness records, not enrollment count,
training samples or a sumcheck/prover complexity parameter. Each mode hashes the
same fixed original generator and statement. Preparation fixes the expected
witness digest and is timed/countable separately. RAM materializes records;
regeneration performs two identical passes; external memory writes and rereads
a temporary file. No strategy is presented as a complete proving algorithm.

`peak_python_allocated_bytes` measures tracemalloc's scoped Python allocator peak;
RSS and VRAM are explicitly unmeasured. File counters measure application bytes,
not physical disk traffic. Temporary file size is not total retained cluster
storage. Timings are one reference trial per configuration; there is no variance
or performance-speedup claim. Shared setup, commitments, host/device copies,
network and finalization require additional measured phases.

A checkpoint binds program, parameters, data/witness identity, statement,
transcript/challenge position, offset and authoritative sequence. Expected
identity/sequence/prefix must come from trusted state, not the checkpoint itself.
A production adapter additionally needs authenticated integrity, confidentiality
where appropriate, atomic durability and rollback handling. An unkeyed checksum
or filename alone does not supply those properties. Regeneration must reuse the
committed inputs and randomness rather than adapt them to later challenges.
The reference tests corrupt/replay/truncate synthetic state; no real prover is
killed or resumed and no production crash guarantee is asserted.

## Queue and accepted-state semantics

Admission bounds proof bytes, waiting count, running workers, total reserved work
and per-round identity history. Cheap shape/authorization checks precede expensive
work. Production cost estimates must come from authorized proof type/dimensions,
not an untrusted claimed cost. The reference authorization flag is synthetic.
A valid-proof throughput experiment requires an actual verifier adapter.

The implementation adapter must atomically bind `(context, admission-unit,
nullifier)` to the exact payload digest and final verification receipt in the
canonical durable ledger. Retransmission returns the same result; conflicting
bytes reject. The reference key represents this composite identity; it is not
an authentication or global-uniqueness implementation. Verification happens
outside the ledger transaction, then commits using the exact active token,
context and state version. A late completion cannot revive cancelled work.

Cancellation of running noninterruptible verification retains its reservation
until the worker actually exits. A cancellation request is not CPU termination.
Commit-before-cancel retains the already committed receipt; cancel-before-commit
prevents admission. Tombstones persist within a bounded identity space; arbitrary
identifier floods cannot grow the reference history indefinitely. A production
round needs a bounded authorized population, retention/retry policy, crash-safe
transactions and authenticated latest state; no in-memory lock establishes these.

The 8/32/128 load references use synthetic valid/invalid labels and a deterministic
scheduler, with explicit backpressure. They do not measure genuine-proof
throughput, parallel worker utilization or latency percentiles. Concurrent tests
exercise the reference state linearization, not a deployed multi-host ledger.
Queue policies must not silently substitute a smaller cohort or claim unbiased
participation/DP amplification after load-dependent exclusions.

## Certificate semantics and proof boundary

The transparent two-layer reference tree binds expected session/round, complete
parent/model/optimizer state, relation/parameters/key, payload type, accepted root,
ordered authorized roster/weights and release identity. Every leaf occurs once;
every internal node conserves weighted numerator and denominator. Expected
context and roster come from trusted external state. The fixture availability
boolean is an annotation, not an authenticated availability certificate.

A genuine adapter must verify every required leaf and recursive/aggregation
proof against expected keys, bind protected payloads to those statements, validate
availability/receipts and constrain the authenticated base case and complete state
edges. Aggregating siblings sharing a parent and composing sequential history are
different operations; sequential output/input state, counters and policy must
connect explicitly. A short certificate alone supplies none of these constraints.

Choose and pin one existing scheme/backend in the implementation slot, including
source/version, parameters/setup, transcript/challenge model, maximum or justified
polynomial depth and extraction/composition assumptions. Distinguish raw folding
or aggregation objects, terminal opening/binding checks, compression and final ZK
transformation. Report every step's work, retained witness/commitment storage and
finalization cost. The reference checker returns `proof_backend=not-integrated`
and `zero_knowledge=not-established`; its schema rejects promotion to genuine
proof evidence. No recursion backend is selected or integrated by this slot.

## Transport and global privacy cohort

The logical accepted cohort is twelve clients whether routed directly or through
three relays. The topology fixture conserves each identity once and the same
weights/total. A partition/dropout aborts the fixed-cohort operation; changing the
cohort or renormalizing needs a new authorized context, not a transport retry.
Inventory coordinator, every relay/worker/recipient and their permitted views,
including reconstruction, rejected requests, timing and recovery observations.

For global-only policy, relays may handle declared routing metadata and opaque
protected payloads. A string labeled opaque does not establish cryptographic
confidentiality. Clear individual/subgroup sums require a different authorized
release policy and privacy argument. The original fixture gives two input sets
with the same global sum78 but different relay subgroup sums: observing those
partials reveals information beyond that global output. It is a deterministic
extra-leakage counterexample, not a DP neighboring-dataset theorem.

The illustrative recipient threshold is two of three with at most one corrupt
recipient across the entire topology. Threshold counts refer to actual distinct
security principals; multiplying committees does not reset the global coalition
budget. Enumerate shares/keys held across roles, permitted corrupt sets, dropout
patterns, reconstruction authorities and retained/released material. A role must
not collect a reconstruction threshold for an unauthorized intermediate value.
Even a valid unknown-contributor count is insufficient if other information or
repeated subset queries reveal values. The protected backend, complete observer
argument, conditional entropy/accounting and independent review remain required.

These original design choices and alternatives are proposed for independent
protocol/cryptographic/privacy and provenance review under GOVERNANCE.md. Keep
all four issues open until their implementation, actual measurements and review
gates are met. Do not merge this draft as an approved performance/security result.

A follow-up Docs metadata read on 2026-11-25 returned a different revision token.
The earlier read and selected cached prose remain an explicitly historical
MS20261124 inspection; current-edition mapping/content equivalence and migration
are pending-source-review. No source graph, equation count or claim status is
relabelled from that token alone. The M4 engineering fixtures are original
synthetic definitions, so their checks do not depend on a new book golden.
