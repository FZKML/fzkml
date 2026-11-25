# Protocol/privacy reference delivery — #51–#55

Branch `codex/history-witness-dp`, stacked on scientific specification PR #69.
The five slots were checked unclaimed, assigned to Guillaume Lauzier and received
branch/scope coordination comments on 24 November 2026. This is original
engineering code and specifications developed with Codex assistance, Apache-2.0;
no manuscript text, external dataset/model, or upstream sampler code is copied.
No dependency, paid service, GPU workload or repository security setting is added.

| Issue | Implemented and executable evidence | Remaining acceptance evidence |
| --- | --- | --- |
| #51 | Complete-state hash/context/parent/order checks, externally pinned genesis, verifier callback, missing-certificate state, two-valid-history/disconnected/withholding examples; atomic and racing trusted-ledger selection tests | Actual #23/#45/#48 authenticated proof/aggregation integration; durable anti-rollback state and availability service; independent consensus/security review |
| #52 | Role/flow inventory including trusted, outsourced, collaborative and attested views; fixed public exporter using CI-10; success/failure canaries through CLI/public reports; explicit uncovered surfaces | Actual #33/#46 worker/network/telemetry audit and malicious/remote computing assumptions instantiated and reviewed |
| #53 | M0 native exact step, equal squared norms 256, clean losses 0 vs 4 from baseline 1; correct poisoned execution distinguished from wrong trace | Real full-training proof/circuit execution on the same inputs; no robustness/Byzantine or source-authenticity claim |
| #54 | Exact fixed-slot/clipping/rounding query, L1 bounds 24/48, all coordinate/residue checks, multiplicity contract, extremizers and private-denominator counterexample | Independent mathematical review and integration with the actual selected research/numeric/release contract; no transfer to the three-client RNE profile |
| #55 | CKS2020 Lemma 29 parameter mapping; original exact rational folded-geometric sampler and analytic PMF; default and reduced finite conformance checks; OS randomness, range/support/modulo/error and accountant interfaces | Independent theorem/implementation/security review and integration; central trusted output-only mechanism, no distributed sampler, persistent budget enforcement or deployment DP claim |

Run the same checks locally and in CI:

```sh
./scripts/validate
./scripts/protocol-reference --check --output protocol-evidence
```

The output directory must be new; this avoids overwriting or following existing
artifacts. `experiments/protocol/observations.json` retains deterministic original
reference results, including counterexamples and explicit real-proof **not-run**
status. The runner compares them and checks the observer inventory and shared
claim schema. No private randomness/noise sample is retained or seeded for public
reproduction. Locally it records observations only. On GitHub, the actual run ID,
source commit, source/parameter/embedded-fixture/dependency digests and runner
revision also populate **the existing CI-04 result schema**, followed by the
existing semantic validator and deterministic report verification. No fake local
workflow ID is invented. CPU job logs retain a bounded reference summary; the
runner's generated report directory is temporary during validation. The committed
observations plus source/tests/specifications are the retained reference artifacts;
this change does not add an automatic public artifact upload path.

`claims/protocol-privacy.json` is a scoped registry using the same claim schema
and validator as the manuscript registry. `ENG20261124` identifies original
engineering definitions mapped to issue chapter topics, not an extracted book
edition. Its five `tested` statuses apply only to these scoped reference claims;
formal-proof and independent-review fields are empty and explicit. The existing
manuscript register, source extraction coverage and claim statuses are unchanged.
It is an additional source set for future registry consolidation, not another
schema or a replacement claim register. `DP-MECHANISM.md` names the exact external
privacy lemma and separates it from the original vector/ring derivation.

Twenty new tests cover disconnected or competing valid histories, withholding,
complete-state/context/order tampering, verifier failures, replay/concurrent
selection, ledger loss/atomicity, omitted external-role assumptions, declared
public surfaces with positive and leaking controls, poisoned-but-correct versus
incorrect execution, negative rounding ties, clipping order and unsupported
adjacency/multiplicity, every rounded coordinate/residue phase, exact finite
sampler/analytic masses, exhaustive inverse-CDF ranks/pairs in a reduced profile,
default modular full support, conservative exact accounting, RNG failure and
schema/report integration. No distribution or unit test is a proof of DP.

No automatic issue-closing keywords are appropriate: these research issues still
need their stated backend/protocol and independent review evidence. The current
M0 trusted ledger is not a consensus implementation, its dataset is synthetic,
and no production privacy/security property is established by these examples.

Final local validation: `./scripts/validate` passed Rust format/Clippy/workspace/doc
checks, Ruff lint/format, strict mypy, governance/citation and scientific metadata
checks, all 66 Python tests and the reference CLI. The unchanged placeholder Rust
crate has no protocol tests; these twenty new tests exercise the Python reference.
The prior explicit DCO authorization in this session is used for this contribution.
