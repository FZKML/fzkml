# M0 scientific implementation evidence

This branch is stacked on CI foundation #67 (which is stacked on governance
foundation #66). It supplies reviewable specifications, source metadata and
fixture tooling for #12, #13, #14, #19, #20, #21, #22 and #23. It does not close
these issues automatically or claim the required independent reviews occurred.

| Issue | Delivered | Remaining evidence or review |
| --- | --- | --- |
| #12 | Observed manuscript revision, 80 chapter/48 exercise work mappings, source anchors, 16 scoped prose claims, explicit evidence coverage | 417 native equations need authorized source review; remaining extraction is pending; first-release set and mathematical/security summaries need review |
| #13 | Fixed four-client synthetic deployment, separate observer views, one-step relation, roster/weights, abort/release/recovery behavior and capability table | Independent protocol review, arithmetic contract, implementations and adversarial vectors |
| #14 | Scientific run-identity/cost requirements and six fictional reporting cases | CI-04 interface review/extensions for event costs, missing phases, MSE, local/GPU provenance and uncertainty |
| #19 | Matched honest-trace vs deployment comparison; seed/budget/quality policy; separate sample/diversity/label factors | Protected/proof arms, new batch relation for sample-count effects, actual experiments and any adoption study |
| #20 | Original deterministic synthetic dataset, manifest, entity/time/duplicate metadata, split helper and negative tests | Independent provenance-policy review and any later public benchmark adoption |
| #21 | Complete 12-family by 6-mode status matrix and initialization/full-state/delta requirements | Backend implementations and relation-specific review; no assurance mode is implemented |
| #22 | Four primary-source cards, explicit reproduction/replication/adaptation distinction, separate population counts and missing-resource records | No source experiment reproduced; code/data licenses and runnable artifacts remain unadopted |
| #23 | Scoped standalone games/conditional argument and 14 open obligation records with responsible issues/review domains | Concrete backend, commitment/setup, composed extraction, security/numeric/privacy review and all later protected composition |

## Actual local validation, 2026-11-24

The manuscript revision was read before and after inspection and was unchanged.
The text-only digest and omitted equation count are in `manuscript.json`.
The private manuscript body and source cache are absent from this branch.

- The complete `./scripts/validate` command passed with the existing locked
  Python 3.11.14/Rust 1.85.1/uv 0.9.11 toolchains: Rust formatting, Clippy and
  scaffold tests; Python Ruff formatting/lint, strict types for CI sources;
  governance/license/asset/citation checks; the shared claim schema and semantic
  validator; all 46 Python tests; workflow policy and unchanged lock files.
- Additional Ruff checks/format checks passed for the new scientific scripts and
  tests. Existing strict typing applies to the CI package; no strict typing
  claim is made for the new standard-library research scripts.
- Public report generation with the canonical 16-claim registry and exact report
  regeneration verification passed. All five scaffold scientific runs remain
  not-run. No fictional successful reporting case is included as an actual run.
- The source builder passed and its reproducibility/contents tests passed.
  The manuscript body, native equation payloads and external datasets/models
  are not source-archive inputs. One initial local report invocation failed
  because its output parent directory did not exist; creating that parent and
  rerunning generation/verification succeeded. No scientific run failed or
  succeeded as a consequence of these infrastructure checks.

The macOS sandbox caused the installed uv tool to panic while reading system
configuration. The full offline validation succeeded outside that sandbox using
already installed toolchains. This is an environment limitation, not scientific
evidence. Hosted Linux checks and DCO certification are separate from these local
checks and must be inspected on the actual PR head.

Required independent review follows `GOVERNANCE.md`: security-sensitive changes
need a qualified reviewer independent of the author. Until that review exists,
this remains a draft specification and must not be merged as an approved
cryptographic or privacy guarantee.
