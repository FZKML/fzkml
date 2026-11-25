# Transcript/privacy reference evidence

This change addresses #56–#59 on `codex/transcript-privacy-research`, stacked on
the scientific registry PR #69. The existing #60 claim on
`codex/privacy-performance-research` is preserved in [PR #71](https://github.com/FZKML/fzkml/pull/71). No issue is automatically
closed and no independent security review is asserted.

| Issue | Implemented and checked | Remaining scope |
| --- | --- | --- |
| #56 | Conditional-entropy gates, declared release/entropy-instance binding, exact independent residual covariance under coalition/dropout, half-normal retry calculation and XOR counterexample | Real private entropy service, hidden-noise/inclusion proof, durable cross-service binding and independent protocol review |
| #57 | Four-way observation classification, fixed-cohort basic declared composition, epsilon/delta exhaustion gates, separate computational advantage, idempotent retry, locked/fsynced journal, recovery and trusted-root rollback checks | Verified finite mechanism, authenticated protocol/roster, actual protected publisher, trusted latest-root custody and complete-view simulation |
| #58 | Exact rational PSD/support/conditional-covariance routines, complete finite pattern checks, scalar 43/10 and vector 24/5 source example | Independent mathematical review; continuous-set/adaptive theorem where applicable; theorem-matched discrete/finite sampler before applying DP |
| #59 | Exact final-inclusion means/variances, source two-client bias example, equal-marginal dependent laws and per-resource population stages | Real completion laws, stochastic/adaptive update assumptions, actual deployment experiments; no amplification theorem implemented |
| #60 | Existing implementation inspected; its three compression tests rerun successfully on commit `f1945a33d36f826af2509d8f475e157319a9ceba` | Ownership and review remain with its existing branch; these tests do not prove a complete transcript privacy guarantee |

Source inspection recorded the canonical Google Doc revision before an
authorized DOCX export outside Git. A post-export revision read failed with a
connector transport error, so no atomic revision/export snapshot is claimed.
The inspected equation IDs and export SHA-256
are in `transcript-source-review.json`. Fourteen source equations have inspected
markup, including the exact precision matrix, conditional covariance and
inclusion variance. The remaining 403 equations stay pending-source-review.
Source inspection is distinct from independent scientific review.

Actual local checks on 2026-11-24:

- Full locked `./scripts/validate`: passed with Python 3.11.14, Rust 1.85.1,
  uv 0.9.11. Rust scaffold format/Clippy/tests; Python lint/format/strict typing;
  governance/asset/citation and shared claim checks; all 72 Python tests;
  analytic fixture regeneration, workflow policy and unchanged dependency locks.
- Canonical public report generation and exact report verification: passed.
  The registry now has 23 records: eight planned, ten specified and five tested
  reference implementations. Zero empirical, independent-review or formal-proof
  evidence is asserted. All five scaffold scientific runs remain not-run.
- Source build and reproducibility/contents tests: passed. No manuscript body,
  export, equation XML, images, external code, data or model is included.
- In the existing #60 checkout, only
  `test_privacy_performance.CompressionTests` was rerun: three tests passed.
  This covers the kernel/dense-bound rejection, error-feedback clipping example,
  and state/version/randomness binding. That result is a separate local
  conformance check, not an independent security approval.

Exact rational geometry has no numerical eigenvalue tolerance. Only the named
erf approximation uses floating arithmetic, with a stated absolute tolerance.
The ledger's mechanism and entropy references are synthetic dependency contracts;
their existence does not establish any external theorem or honest randomness.
Unix local locking/durability and external latest-state custody are assumptions,
not a consensus or Byzantine-storage implementation. Required independent review
under GOVERNANCE.md remains pending before merging security-sensitive behavior.
The NIGHTLY_CPU lane depends on the separate CI research workflow foundation;
no hosted nightly, GPU, field-study or protected-protocol run is claimed here.
