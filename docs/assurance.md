# Security and scientific assurance statement

Version: S03 assurance 1.0.0. Scope: `specifications/protocol-v1.json`, its named
relation profiles and the exact source/evidence records in `claims/`. The
statement is a proposed policy/specification, not an external audit or approval.

The [protocol threat contract](../specifications/protocol-v1.md) lists roles,
static coalition assumptions, permitted views, trusted setup/key/state services,
abort/recovery behavior and unsupported conditions. Candidate implementation
profiles are separately versioned: transparent numeric conformance, a joint
private-witness transition and protected aggregation have different disclosure
boundaries. A result from one does not establish another profile's guarantee.

| Assertion | Registry/evidence scope | Limitation |
| --- | --- | --- |
| Local transition target | `FZK-MS20261124-C07-REL-001`, `C40-REL-001` under the same ID prefix | Manuscript/M0 two-feature target; implementation evidence must name the distinct actual scalar relation |
| Commitments/standalone proof security | `FZK-MS20261124-C04-SEC-001`, `C05-SEC-001` | Conditional requirements; setup, entropy, hiding/extraction and implementation review remain open |
| Payload/composition binding | `FZK-MS20261124-C14-SEC-001` | No full-system simulation or universal composition proof |
| State agreement/history | `FZK-MS20261124-C73-MATH-001` | Valid certificates do not by themselves prevent forks or establish freshness |
| Transcript accounting reference | `FZK-MS20261124-C47-LEDGER-001` | Tested synthetic declared-cost ledger; no deployed DP service |
| Gaussian geometry | `FZK-MS20261124-C75-GEOMETRY-001`, `C75-REFERENCE-001` | Exact analytic/reference scope; no discrete sampler or adaptive-training theorem |
| Learning/access benefit | `FZK-MS20261124-C77-HYP-001`, `C80-HYP-001`, `C80-ADOPT-001` | Planned hypotheses; no learning/adoption/clinical outcome is established |

The full IDs, assumptions, observer, privacy unit, source version, numerical
semantics, limitations and validation references are machine-readable in the
registry and traceability overlay. The validator distinguishes authored status,
test execution, empirical replication, formal-checker evidence and independent
review. Mathematical derivation/source inspection is not an independently checked
formal proof. An unsuccessful attack does not certify DP. Green CI establishes
only its named conformance checks and cannot confer cryptographic security,
production readiness, useful learning or truthful data.

Review history: source inspections on 2026-11-24 are recorded with document
revision, export digest, locators and limitations in `docs/research/`. Existing
hosted test observations are pinned to their run and source commit. There is no
formal proof/kernel artifact, independent protocol/privacy review or external
audit in the current catalog. Such records must include exact date, version,
scope, reviewer/checker, immutable artifacts and remaining assumptions before
their evidence category can be reported. Required independent review is governed
by `GOVERNANCE.md`; no merge or audit approval follows from this statement.
