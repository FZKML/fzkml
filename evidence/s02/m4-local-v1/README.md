# Session02 M4 retained local evidence

Calculation source: `568a81eb0fddb6a5ba89f08b0932b814a30b2a9b`; clean at run start.
Raw artifact SHA-256: `7a86820e04a7f38711f25caffca57a94554bee1c5ec6b1ab3e353787c2952c08`.

Three retained repetitions contain3 verified single-prover proofs,6 verified
three-party proofs (3 each at zero and5ms relay-read delay), and3 Paillier runs.
All use the original public synthetic operands3/11 and return33. Nine actual
proofs/public outputs and the pinned verification-key digest are retained in
`proof-manifest.json` and `public/`. No witness/share/key/config/backend log is
included. Public numeric artifacts are not a production SRS or security approval.

| REP3 relay delay/read | End-to-end seconds (raw repetitions) | TCP payload bytes |
| --- | --- | --- |
| 0 | 0.134726, 0.133725, 0.133426 | 2720, 2720, 2720 |
| 0.005 | 0.243620, 0.239663, 0.246384 | 2720, 2720, 2720 |

These end-to-end clocks include relay setup/drain/teardown, dealer splitting,
startup/IO and verification. Per-party proving kernels and RSS are separate.
The per-read delay is not a calibrated network RTT.3 noisy repetitions do not
establish a speedup, WAN model or statistically significant performance result.
The Node single-prover uses a different implementation; no relative speedup is
asserted. Hardware is the same shared Darwin arm64 host with12 logical CPUs.

| Window | Clean time to synthetic target | Invalid-step time |
| --- | --- | --- |
| 1 | 176/5 | 187/5 |
| 2 | 89/5 | 20 |
| 4 | 47/5 | 58/5 |
| 8 | 29/5 | 8 |

Pipeline values are exact modeled seconds on the declared halving quadratic,
not measured training times. Missing/malformed-share runs remain timeout/rejected;
wrong-output and malformed-proof negatives fail real verification. Every HE run
retains valid ciphertext malleation33→34, accepted by HE and detected only by the
independent synthetic oracle. Attestation is **not-run**, protocol round-trip
counts and combined live cluster/harness memory are unmeasured. No full-stack PQ
configuration is supported; the proposed mixed-PQ configuration is unimplemented.

`development-failure-dirty.json` preserves the first instrumented relay failure.
Its source_dirty=true, uncommitted implementation and incomplete input snapshot
make it a development diagnostic, not clean-source evidence or a successful run.
The macOS retry reused a failed socket; the final source uses fresh connections.
The unsupported one-party Shamir/t0 attempt is recorded in the experiment README;
the successful trusted baseline uses actual snarkjs proofs instead.

Validation:17 M4 reference tests pass,46 combined language tests pass locally,
existing debug/release261/11/1040 conformance and3 controlled mutants pass,
4 Rust tests plus17 governance and16 pipeline tests pass. The hosted language
lane loads the reference tests; without installed external tools it explicitly
skips1 upstream comparison. The external proof/HE experiment is local/manual,
not a hosted experiment. DCO certification and independent review remain pending.

Reproduce with the optional bootstrap and runner commands in
`experiments/s02-protected/README.md`. This companion is not a CI-04 public
publication, scientific claim promotion or release approval.
