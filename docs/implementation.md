# Implementation evidence and limits

This change coordinates CI-01 (#10), CI-13 (#11), CI-04 (#15), CI-05 (#16),
CI-06 (#17) and CI-10 (#18). It provides engineering infrastructure and negative
test fixtures; it does not establish scientific or cryptographic claims.

| Issue | Implemented evidence | Remaining dependency/verification |
| --- | --- | --- |
| #10 | Rust workspace/lock/toolchain, Python metadata/lock/hash-pinned bootstrap, one CPU command, format/lint/type checks, runner revision summary | Clean hosted Linux CPU run passed; LANG-01 selects scientific proof backend |
| #11 | Read-only ephemeral fork CI, pinned action allowlist, timeout/matrix/privilege checks, CODEOWNERS, isolated trusted report path | CPU required-check addition after workflow lands; independent reviewer scope remains explicit |
| #15 | One versioned result schema, semantic validator, retained repetitions/aggregations, five statuses, synthetic v0.1 placeholders | Scientific contract review by FZK-R003 (#14) |
| #16 | Versioned claim schema, reference/source checks, explicit coverage, separate formal/review evidence | Manuscript extraction and topic map by FZK-R001 (#12) |
| #17 | Deterministic Markdown/HTML/SVG/JSON, job summaries, commit-versioned trusted artifact workflow | Actual tiny proof/conformance/negative/cost measurements; longer-lived release publication |
| #18 | Closed public fields/paths, byte/depth/count bounds, licenses, randomness separation, secret markers, exact-regeneration upload gate | Secret scanning/push protection verified enabled; ongoing human narrative review |

`tests/test_pipeline.py` exercises malformed metadata, unknown versions and units,
inconsistent statuses/timeout/quality, nonfinite values, duplicate IDs/JSON keys,
missing raw repetitions, wrong aggregate values, excluded samples, forbidden
fields, credential-like fixtures, data complexity limits, missing license metadata,
dangling test/claim references, formal-evidence separation, deterministic reports,
escaping, comparison group separation, tampering, links, oversize files, bounded
CLI errors, and workflow policy mutations. Test inputs are generated synthetic
objects and are not benchmark observations.

No automatic issue-closing keywords are appropriate until remaining acceptance
criteria have evidence. In particular an empty claim registry cannot stand in
for the book; a not-run result cannot stand in for a tiny proof; a policy document
cannot stand in for verified repository configuration.

## Repository settings verified 2026-11-24

GitHub REST responses were read back after configuration:

- Secret scanning and push protection: enabled. Non-provider patterns and validity
  checks remain disabled; no claim of universal secret detection is made.
- Actions default token: read-only; workflow approval of PRs: disabled.
- Fork contribution approval policy: first-time contributors.
- `public-reports`: required reviewer `guillaumelauzier`; custom deployment branch
  policy permits branch `main` only; administrator bypass disabled. Self-review
  remains allowed for this single-owner publication gate. This is not independent
  two-person approval; source review is governed separately by branch protection.
- Existing `main` protection: administrators included; strict required checks
  `governance` and `dco`; one approval, CODEOWNERS review, stale approval dismissal
  and last-push approval required. The new `validate` check should be added only
  once the CPU workflow is available to all PRs, to avoid blocking prerequisite #66.

This PR is stacked on governance foundation #66 and extends its explicit file and
package inventories. It preserves its required governance/DCO check names, aligns
its runners/tooling with the locked CPU setup, and removes broad untrusted uploads.
`compliance/ci-dependencies.json` checks all uv package artifacts and license texts;
third-party Rust additions remain rejected until explicitly inventoried.

Local validation: Rust 1.85.1 formatting, Clippy and workspace/doc tests; Python
3.11.14 Ruff lint/format, strict mypy; governance/citation checks; 32 Python tests.
The Rust crate is a documented boundary with zero protocol tests because there is
no protocol implementation. The initial clean Ubuntu 24.04 run passed: https://github.com/FZKML/fzkml/actions/runs/45299245713. Latest commit checks remain linked from PR #67.
