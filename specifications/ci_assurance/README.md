# CI assurance reference contracts 1.0.0

This original engineering package specifies CI-16–CI-20 for issues #111–#115.
It is separate from the manuscript claim registry, the shared result/bundle
schemas and Session 04's production pipeline. No scientific claim is promoted.
All values and traces are public synthetic fixtures. No manuscript text or new
book-derived numerical example is included.

Run from the repository root with the pinned environment:

```sh
PYTHONPATH=.:src uv run --locked python -m specifications.ci_assurance.run --output /private/tmp/ci-assurance.json
PYTHONPATH=.:src uv run --locked python -m unittest tests.test_ci_assurance -v
PYTHONPATH=src uv run --locked python specifications/validate.py
```

The existing `.github/workflows/cpu.yml` has contents:read permission, disabled
checkout credentials and a 20-minute bound. Its `scripts/validate` unittest
discovery runs this suite, including the real CLI baseline and deliberately
mutated CLI calls. No workflow is added or edited. The reference runner is
bounded independently: 64 events per trace, 4096 model states, 12 transition
depth, 256 authority events, four concurrency workers, 4 MiB total public-view
bytes, 64 scan entries, two new DP releases and 16 matrix jobs. Exceeding a bound
fails or returns inconclusive, never successful. The CLI test timeout is 15s.

| Contract | Specification and executable acceptance | Negative fixtures | Remaining integration |
| --- | --- | --- | --- |
| CI-16 / #111 | Canonical accepted cohort, reserve before potential disclosure, at most one cached release; duplicate, timeout, dropped-share, reorder and restart traces | Premature/repeated release, rolled-back snapshot, changed positive fixture | #46/#48/#49 actual aggregation, admission and recovery |
| CI-17 / #112 | Exhaust finite two-client/two-share graph; compare a separate lock-based reference against its linearized model history | Conflicting heads and nullifiers, deliberate duplicate-release mutant, exhausted exploration budget | #47/#48/#51 native service, authenticated storage and consensus refinement |
| CI-18 / #113 | Inventory logs, public inputs, metrics, uploads and recovery views; scan bounded declared files | Raw/hex/base64/percent canaries in each channel, omitted/unlisted exports, symlink/traversal/size | #18/#52/#57 actual public/proof/export paths and complete observer analysis |
| CI-19 / #114 | Hash-bound conditional finite cyclic geometric proposition, exact ticket law, supported clipped-query adjacency and ratio composition | Wrong sampler/ring/scale/clipping/cohort/scope, unsupported amplification, noise reuse and unaccounted repeats | #54/#55/#57 actual entropy/sampler, mechanism and full-transcript analysis |
| CI-20 / #115 | Digest-bound offline matrix, explicit CPU/GPU/RAM/disk/time quotas, pre-expansion product check | Wildcards, mutable/mismatched inputs, unauthorized digest/context, runaway product, missing quota, live dispatch | #38/#15/#40 real reviewed experiments, resource policy and isolated execution |

Dependencies are reviewed here as **interfaces and outstanding obligations**,
not adopted as completed native implementations. Their relevant prior local
specification bytes are pinned in `contracts-v1.json`. Issue numbers are GitHub
references, not claims of test coverage for peer-owned implementations.

The pure state model and mutable authority share the State representation,
invariant predicates and deterministic synthetic release digest; their transition
logic is separate. This is a refinement regression for one trusted lock-based
authority, not an independent implementation of distributed consensus. All 34
reachable states and 374 action edges under the fixed 11-action alphabet satisfy
the checked predicates. This finite closure says nothing about more clients,
network partitions, malicious authorities, arbitrary payloads or production code.
The duplicate-release mutation gives an eight-event counterexample. A lower
exploration budget yields inconclusive. Liveness is not asserted.

An accepted cohort is frozen only after both distinct admissions. Out-of-order
operations that lack prerequisites are ignored. Valid complete reordered traces
freeze the same bindings; conflicting payloads use the first linearized binding,
so different schedules can legitimately select different payloads. A wrong head
cannot change the single-authority state. Restart restores a serialized state
only under the **external** assumption of authenticated latest atomic storage
and a trusted anti-rollback version floor. No actual durable database, Byzantine
consensus, signature verification or protected share network is implemented here.

Reservation is conservative: it precedes possible share exposure. Timeout before
reservation is `aborted-before-disclosure`; timeout after it is
`aborted-possible-disclosure`, retaining cost even if no actual information leak
was measured. A successful release is cached and retransmission adds neither a
release nor a cost. The synthetic release is a SHA-256 identifier for state, not
a protected aggregate, real proof or cryptographic privacy guarantee.

The scanner sees **only its generated public-view directory**. It requires the
five channel classes and scans every declared file, including recovery data.
Known raw, lower/upper hex, base64 and standard percent encodings are detected.
Its error output omits offending bytes, paths and exception details. It cannot
detect arbitrary re-encodings, correlations, low-entropy inference or unknown
exports outside that inventory. Canary rejection is a regression result, not a
proof of confidentiality. Its explicit public canary must never be replaced by
real private material.

`dp-geometric-v1.md` states the exact query, observer, finite law, adjacency,
ideal-uniform ticket assumption and composition. The checker enumerates all
residue/shift ratios and checks exact integer ticket multiplicities. It does not
sample entropy, prove a deployed sampler, validate arbitrary trainer sensitivity
or infer privacy from a byte scanner. Release-ID/noise-instance metadata requires
external binding to actual identical cached bytes. Full-view DP, theorem review,
formal proof and independent review remain open.

The reviewed-matrix interface takes an externally supplied trusted digest set.
`matrix-review-v1.json` injects a **synthetic test-only trust anchor** solely to
exercise acceptance and rejection. It contains no human approval or live approved
digests. All live dispatch requests are unsupported. Matrix changes require
separate review, refreshed software/dataset digests and a new authenticated trust
anchor; a contributor editing this test fixture cannot authorize real hardware.
The baseline expands four jobs, eight attempts, 480 worst-case serial/CPU seconds,
zero GPU seconds, 4096 MiB concurrent RAM, 2048 MiB concurrent disk and 8192 MiB
cumulative disk allowance. These are planned ceilings, not measured consumption.
No shell command is accepted. All six own Python source files are pinned through
`software-v1.json`; the dataset and software descriptors are themselves hashed.

`report-schema-v1.json` is a closed, separate engineering report, not a shared
scientific result or bundle. Successful records carry contract/issue/fixture IDs,
source commit/dirty flag/file hashes, observations and explicit limits. A failed
CLI call overwrites the requested output with a closed failure record and exits
1, so stale success cannot survive a failure. Inconclusive/unsupported/canceled
records cannot pass `check_report`; skipped is not a successful outcome. Direct
reference processes have no hosted receipt IDs; hosted workflow logs are linked
separately and must name their actual source. All publication records are
`approved=false`, with no scientific claim IDs. These records do not authorize
public scientific exports or adopt evidence into the manuscript registry.
