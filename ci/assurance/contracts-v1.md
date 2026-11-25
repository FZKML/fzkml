# Session 04 assurance interfaces, version 1

Issue ownership: #109 CI-14 and #110 CI-15; evidence/report preparation for
#106–#108. CI-16–CI-20 reference specifications belong to Session 03 and are
not implemented or certified by these gates.

`./scripts/assurance golden --write` deterministically creates CI-14 version
ci14-1.0.0 and its SHA-256 sidecar. `./scripts/assurance golden` requires actual
Rust agreement with the independent Python Fraction/struct oracle: 1040 rounding
cases, seven signed/field encodings, 36 bounded batches, five invalid signed
integers and six invalid frames. It then requires three intentional rounding,
negative-division and byte-order mutations to disagree with native output even
when the native process exits zero. The pinned field is BN254 scalar Fr; these
are original implementation vectors, not numerical transcription of the book.
The 32→34 vector is valid for one step but requires successor-domain admission
before another step under the unchanged weight bound32.

`./scripts/assurance proof` runs a fresh real Groth16 setup/proof and the existing
native verifier. Its controller owns the verifying key. Development, mocked,
substituted key, forged key tag, fake proof, changed output, trailing data,
skipped, unsupported and canceled receipts fail. All negative producer nominal
exits are zero. Selecting an invalid candidate makes the entire command fail;
a zero exit, producer verdict or missing proof cannot satisfy CI-15.
No core cryptographic implementation was edited. This gate covers the public
fzknum arithmetic relation; the existing private-transition check remains a
separate mandatory job step.

`./scripts/assurance benchmark --repetitions 1` measures bounded same-host CPU
processes and their actual per-child wall/CPU/RSS/stdio/queue observations.
The two-process budget and maximum two repetitions are fixed. Emulated delay
and simulator output are separate from physical devices. The disjoint public
toy holdout uses RNE encoded predictions: baseline MSE9/64, transitioned MSE25/256,
target1/9. This is not population utility. Timeouts retain all selected clients
and source coverage; a reduced cohort has no certified quality result. The
unproved protected arm is unavailable, the central arm is not local-only
training, and no matched four-arm/DP comparison or physical field study exists.
Network, energy and monetary cost are uninstrumented, not zero. Manual main-only
GitHub-hosted CPU execution is available; nothing automatically dispatches it.

`./scripts/assurance report` creates a historical book revision proposal and
review packet. `--check` verifies canonical bytes. The proposal retains all
80 chapters, 48 exercises, 23 authoritative claim statuses, unrun replication
cards and counterevidence. Existing CI-05 validation and CI-06 rendering remain
authoritative; standard result/bundle 1.1 schemas are unchanged. Companion
schemas are closed and separately versioned, not replacement scientific results.
Raw genuine-proof result1.1 candidates have approved=false and empty claim_ids;
they cannot enter scientific publication. No canonical manuscript is edited.

The review packet fixes actual protocol code/configuration/contracts/tests to
commit b602197104d810bc1a41a2ea24085b25484272b7. Reviewer TBD, not appointed;
owner Codex Session04; prepared for maintainer review; distribution unauthorized.
No firm or person is contacted. Required future appointment includes relevant
ZK, finite-field/fixed-point and Rust expertise, conflict disclosure and written
severity-rated findings with remediation verification. No reviewed release label
exists. `review-check --require-reviewed` deliberately fails while review is
pending. Scope drift invalidates this packet; CI cannot grant independent review.

All source/lock/tool/hardware/failure/limitation metadata is retained in bounded
local companion manifests under ignored reports/assurance. Scientific publication
policy remains proposed with null human approval; these producers are not
approved by that proposal. No secrets, witnesses, setup trapdoors or private
manuscript exports are retained. The review packet and proposal contain public
source metadata only, not unapproved empirical output. No merge or paid/GPU job
is authorized by this implementation.
