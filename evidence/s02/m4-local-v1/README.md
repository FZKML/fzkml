# Session02 M4 retained local evidence

Calculation source: `3acde263a986433687572551a88c1013d591466e`; clean at run start.
Raw artifact SHA-256: `6689af2d11ed7f36d0f13152b5b6bb3915adb2f024dfbedb25b52c6e9cc08fe5`.

Three retained repetitions contain3 verified single-prover proofs,6 verified
three-party proofs (3 each at zero and5ms relay-read delay), and3 Paillier runs.
All use the original public synthetic operands3/11 and return33. Nine actual
proofs/public outputs and the pinned verification-key digest are retained in
`proof-manifest.json` and `public/`. No witness/share/key/config/backend log is
included. Public numeric artifacts are not a production SRS or security approval.

| REP3 relay delay/read | End-to-end seconds (raw repetitions) | TCP payload bytes |
| --- | --- | --- |
| 0 | 0.136637, 0.133625, 0.233090 | 2720, 2720, 2720 |
| 0.005 | 0.248739, 0.238752, 0.235941 | 2720, 2720, 2720 |

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
not measured training times. Missing/malformed-share runs retain timeout status and individual worker failures;
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
