# CI-16–CI-20 implementation evidence scope

Session 03 supplies original, public synthetic specifications and executable
reference checks for #111–#115 in `specifications/ci_assurance/`. The dedicated
branch is `codex/s03/ci-assurance-contracts`, based on the #128 specification
snapshot. The CLI, schemas, fixture IDs, named positive/negative tests, dependency
interfaces and remaining integration obligations are defined in that directory.

The implementation separately exercises a pure finite model and a mutable
single-lock authority, synthetic fault replay, five-channel known-canary scans,
exact finite-ring parameter/accountant conformance and an offline quota planner.
The initial bounded closure is 34 states / 374 edges. Deliberately permitting a
second release yields an eight-event counterexample. Exhaustion yields
inconclusive. Known-canary mutation and duplicate-release mutation must make the
same baseline CLI fail with exit 1; diagnostics omit fixture/private bytes.

All numerical values are original synthetic engineering inputs. The manuscript
was not needed or newly inspected for this contribution. Existing edition/source
mappings, scientific statuses and evidence-adoption decisions remain unchanged.
The finite-ring conditional proposition cites external DP foundations but is an
original reference derivation, pending mathematical review. No external DP
implementation or manuscript theorem is claimed as verified.

Local validation on 2026-11-25 passed the complete locked `scripts/validate`
command: 155 Python tests plus the existing Rust, governance, fixture and workflow
checks. This includes 14 CI-assurance tests and three added registry mutation
tests. Additional scoped Ruff/format/mypy checks passed for the new package and
its validator/tests. The authoritative `specifications/validate.py`, source archive
build and canonical report/verify-report commands also passed; the canonical
scaffold report retains its five not-run proof scenarios, not successful proofs.

Local commands and their bounded existing CPU workflow are documented in the
package README. A final PR evidence comment records the clean calculation commit,
raw local report SHA-256, actual commands and hosted source/run/job links after
execution. Those receipts establish their scoped test executions only. They do
not supply native protected protocol refinement, production consensus, full-view
DP, live matrix review, formal proof or independent review. The planner never
dispatches. Publication approval remains false.

Licensing/provenance: original software and engineering documentation developed
with Codex assistance under the existing applicable Apache-2.0 path scope. No
private manuscript bytes, external code, model or restricted dataset are added.
The canonical manuscript's publication rights remain separate.
