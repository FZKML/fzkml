# CI-02/03/07/08/09/11/12 delivery evidence

Branch `codex/ci-research-release`, stacked on CI foundation PR #67. These are
engineering controls and synthetic validator tests, not scientific observations.
All seven issues were assigned and received scope/branch claims on 24 November
2026. They remain open until the missing acceptance evidence below exists.

| Issue | Implemented | Still required |
| --- | --- | --- |
| #37 | 15-minute CPU validation/proof jobs; same local proof command; always-running required aggregator; reject mock/missing/skipped proof records | Real adapter and negative/conformance cases from #29/#33/#35/#36; measured tiny CPU budget and hosted successful proof; promote required status after readiness review |
| #38 | Fixed main-only allowlist, two concurrent profiles, per-repetition journal/fsync, initial artifact, failed/timed-out records, bounded reproducer, metadata-only reconciliation | Research fuzz corpora/integration scenarios and real benchmark repetitions; hosted schedule/cancellation/runner-loss evidence after merge to default branch |
| #39 | Dependabot Cargo/pip/Actions config, CodeQL Python/Rust/Actions matrix, full commit pins, transitive lock-derived SPDX and explicit unresolved license findings | Actual dependency-update PR and human protocol/numerics review; first hosted CodeQL scan; continued compatibility/license review |
| #40 | Manual no-input workflow, protected environment, explicit failure; no GPU provider, credentials or capacity | Future reviewed ephemeral provider/cleanup/metadata implementation and specific maintainer budget authorization before enabling paid execution |
| #41 | Protected-tag/main-ancestry release workflow, bounded closed digest inventory, library+manifest attestations, verifier constraining repository/workflow/SHA/ref/runner | Real proof results, reviewed protected release tag, approval and publication, independent successful external verification |
| #42 | Shared CI-04 schema extensions, matched workload/security/numerics/model/data/hardware checks, declared phases/resources/cache/amortization, raw variance/failure counts, diagnostic-only policy | Research FZK-R035/R036 experiments and any independently reviewed noise calibration before strict gates |
| #43 | Isolated clean checkout/new environments/hash locks, contract reproduction command, full-mode unavailable failure, tagged inventory/retention/verification policy | Actual reference proof reproduction and tagged evidence inventory once backend and inputs exist; external mirror/retrieval verification |

Local validation before publication: `./scripts/validate` passes Rust formatting,
Clippy and workspace/doc checks, Ruff lint/format, strict mypy, governance/license
and citation validation, workflow policy and 48 Python tests (16 added here).
The Rust placeholder library has no protocol implementation/tests. New synthetic
tests cover missing/mocked proof evidence, skipped/timeout records, real subprocess
timeouts, partial journal survival, bounded reproducers, missing-job reconciliation,
binary/manifest tampering, identity-constrained verifier invocation/failure,
unsafe workflow mutation, transitive inventory, unmatched benchmark/cached work
and missing setup measurements. The mocked attestation invocation test is not an
actual signature verification and is not presented as one.

Repository administration read back on 24 November 2026:

- Public repository; Dependabot alerts endpoint returned HTTP 204 (enabled).
- Dependabot security updates explicitly enabled, then GET returned `enabled: true`.
- Secret scanning and push protection read back enabled (coordinated foundation
  setting; no paid AI feature was enabled).
- `gpu-research`: reviewer Guillaume Lauzier, self-review prevented, administrator
  bypass disabled, deployment branch `main` only. Environment approval authorizes
  no provider spend; workflow cannot provision anything.
- `release-evidence`: same approval restrictions, deployment tags `v*` only.
  Workflow additionally requires a protected tag and default-branch ancestry.
  No new protected tag/release was created. With one reviewer, that reviewer's own
  initiated deployments remain blocked; this is deliberate, not two-person review.

The repository's branch rules must be reviewed once these check names are present.
This change does not merge code, approve its own controls, create a paid runner,
claim completed scientific dependencies, or publish a synthetic fixture as a release.
Workflow digest changes in `ci/workflow-digests.json` must accompany reviewed
workflow changes, including Dependabot action updates; CODEOWNERS applies to both.

Official support references: [CodeQL languages](https://docs.github.com/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql)
and [attestation verifier policy flags](https://cli.github.com/manual/gh_attestation_verify).
Annotated CodeQL v4 and attest-build-provenance v3 tags were dereferenced to
commit objects and checked via GitHub's commit API; no tag-object IDs are used as
action pins. Foundation checkout/setup/upload pins are reused.

PR #68: https://github.com/FZKML/fzkml/pull/68. The initial hosted Ubuntu run
passed validation, governance and DCO; the proof and required aggregator failed
explicitly on the unavailable adapter, as intended:
https://github.com/FZKML/fzkml/actions/runs/45300501696.
Fresh local checkout/new-environment contract reproduction passed, as did three
actual contract-profile repetitions. Hosted validation now invokes that same
clean-environment reproduction command. The default-branch dependency-graph SBOM
endpoint returned 404 while main still contains no dependency manifests; the
lock-derived local inventory contains 16 packages with reviewed license metadata.
This is not a compatibility/rights audit or a completed hosted update-PR review.
