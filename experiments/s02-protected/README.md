# Session02 M4 reference experiments: issues80–83

Branch `codex/s02/protected-experiments` is stacked on draft124. These are
original Python references and orchestration; no Rust relation, claim status or
shared CI control is revised. No merge is requested. Issue IDs are planning
references, not independently approved scientific claims.

## Reproduce

Run `./scripts/validate-s02-protected` for bounded mathematical/adversarial tests.
The existing language lane discovers these tests. A machine without the optional
external runtime explicitly skips its upstream-proof comparison; it does not
claim an executed collaborative proof. No dependency is downloaded by that test.

The following explicit, local CPU experiment needs Node/npm, network access for
setup, and either macOS arm64 or Linux x86_64:

```sh
.venv/bin/python scripts/bootstrap_s02_protected.py
PYTHONPATH=.:src .venv/bin/python scripts/run_s02_protected.py .tools/fresh-run --external --repetitions 3
```

The bootstrap verifies the upstream source commit and published release archive
hash, extracts only the executable, and uses `npm ci` with the retained exact
transitive lock/integrities. The runner checks source/fixture digests and runtime
bytes against that archive. External runtimes, setup keys, source code and
witness/share files stay outside the source distribution. coCircom is
GPL-3.0-only; snarkjs is GPL-3.0. Their upstream terms apply to those separately
installed programs. This repository contains original subprocess adapters and
metadata, not their implementation or a linked/redistributed binary.

The runner requires a fresh output directory and incrementally retains successful
and failed cases. `run.json` validates against the dedicated local companion
schema. This is not an alternative CI-04 publication/approval path. Final retained
evidence must name a clean immutable source commit. Local diagnostic timings are
not a performance ranking or a transfer of a published overhead figure.

##80: certified progress and sampling

`Frontier` tracks the parent/context and verified ancestor closure, blocks missing
ancestors, stale parent/context evidence, conflicting single-state releases and
unavailable state, and invalidates unaccepted descendants after failure. It
retains an already accepted release. This in-memory single-writer controller is a
**simulation**: its Boolean evidence cannot authorize a real proof-required
release. It does not provide durable storage, consensus, a privacy ledger or an
operational proof verifier.

The exact discrete-event model runs16 serial halving updates on an original
strongly convex quadratic. Training takes1/5s, proof work2 worker-seconds, eight
independent workers are fixed, and speculation windows1/2/4/8 are compared with
and without one invalid transition. Raw event traces retain certified-frontier
monotonicity, maximum depth, discarded work, rollback count, certificate delays
and time to the fixed synthetic objective target. This is modeled time, not
measured training throughput. Explicit stale/unavailable client fixtures are
reported as excluded, without changing their starting state. Contention, WAN
conditions and empirical learning quality remain unmeasured.

`tests/vectors/book/progress-v1.json` records inspected numerical facts from
Chapters69.4 and69.6: capacity `min(1/c,m/g)` with c=.2,g=2,m=8; fixed bad-set miss
probability `C(T-b,k)/C(T,k)` with T100000,k1000. One isolated bad step has only1%
detection; a fixed1% bad fraction has miss upper bound approximately4.32e-5.
The sample must be uniform without replacement after freezing the trace, every
selected bad step must be detected, and a missing witness cannot be replaced by
an easier challenge. These calculations do not certify a complete execution.

The fixture names the exact observed Docs revision, section heading IDs, native
UTF-16 equation ranges and inspected export hash. Revision tokens changed during
this session; an observed stable pre/post export pair is recorded, without an
atomic-snapshot or historical-edition equivalence claim. `MS20261125` is an
observation label, not an author-declared edition. Authoritative mapping and
current-edition migration stay with Session03; historical equation IDs are not
silently reassigned. Only mathematical facts/metadata are committed.

##81: actual collaborative proof and its disclosure boundary

The selected existing construction is
[coCircom0.10.0](https://github.com/TaceoLabs/co-snarks/tree/97adcc06afc0d506c2d6aa9f81b2e342fd8108c0),
REP3/Groth16 over BN254. Python independently decodes its pinned R1CS/witness:
one constraint `(-a)*b=(-y)`, no public input variables, one public output33,
private operands3 and11. The similarly named source example elsewhere has a
different public-input declaration; the adapter checks the actual serialized
relation rather than assuming that prose/source file describes this fixture.
No authenticated commitments bind the private operands to an independently
authorized dataset/model. The verifier proves existence of factors of33; it
does not authenticate coefficient11. The field relation alone does not prove
signed integer input bounds. Only these
small independent reference values establish the no-wrap correspondence here.

Three actual external processes receive replicated witness shares and produce
proofs accepted by the real pinned verifier. A complete-witness single-prover
baseline uses snarkjs0.7.5 with `singleThread:true` and the same circuit/setup/key;
its proof is checked by coCircom. These are different implementations, so no
speedup ratio is inferred. The first instrumented relay attempt also timed out after a startup retry reused
a failed socket on macOS. The relay now creates a fresh connection per attempt;
the failed development record remains separately labeled, not a successful
repetition. The upstream one-party Shamir/t0 attempt failed with
`party id out-of-bounds`; it is not reported as a working baseline.

| Role | Declared/observed view |
| --- | --- |
| Synthetic dealer and local harness | Entire public fixture witness, all shares/files, all local traffic |
| Each REP3 worker | Public statement/setup plus two additive shares per secret |
| Two-worker coalition | Can reconstruct the witness; outside the allowed threshold |
| Single passive worker | Confidentiality is conditional on the construction and private channels |
| Verifier | Public product, verification key and Groth16 proof |
| Loopback byte-counting relay | Raw framed TCP traffic; trusted local instrumentation |

The pinned [upstream network implementation](https://github.com/TaceoLabs/co-snarks/blob/97adcc06afc0d506c2d6aa9f81b2e342fd8108c0/mpc-net/src/tcp.rs)
uses **plain TCP**, not TLS. Local replay therefore supplies neither authenticated
private channels nor independent physical-machine isolation. The test SRS has no
audited ceremony or toxic-waste-destruction evidence. This is a real arithmetic
proof reproduction, not a secure production distributed-witness deployment.
[The upstream MPC core](https://github.com/TaceoLabs/co-snarks/blob/97adcc06afc0d506c2d6aa9f81b2e342fd8108c0/mpc-core/src/lib.rs)
implements the passive-adversary protocols; at most one of three workers may be
corrupt under the declared private-channel model. Active security is unsupported.

Measured costs distinguish dealer splitting, concurrent process wall time,
per-party reported proving kernel, verification, proof/share payload bytes and
per-party max RSS. The counter measures framed TCP bytes, excluding IP/link
headers; it counts both directions once. An optional5ms delay applies to each
relay read, not to a calibrated WAN RTT. Connection counts are not protocol
rounds. Protocol rounds/RTTs, joint live cluster/harness memory, ceremony costs
and real network effects remain explicitly unmeasured. A50ms relay-drain period
and process/IO overhead are included in the end-to-end harness clock.

Missing/malformed shares retain failure/timeout rather than verification. Wrong
public output must fail the real verifier. An allowlist limits exported proof
fields; it is not a zero-knowledge proof or a side-channel audit. Raw shares,
keys, configs and arbitrary backend logs are not exported as public evidence.

Groth16 uses a QAP/pairing check, not a sumcheck reduction. Its terminal obligation
is the actual verification against the pinned key and public output, under the
[Groth16 assumptions/setup](https://eprint.iacr.org/2016/260). A separate original
F17 sumcheck counterexample shows why locally consistent constant polynomials
without an authenticated final evaluation can accept a false claim. It is a
negative reference, not a new proof system or a defect claim about coCircom.

##82: matched exact arithmetic, different assurance

The same operands and exact product are evaluated by the Python integer oracle,
an original2048-bit Paillier reference, and actual REP3/Groth16. HE uses a client
who knows a and owns the full secret key; the evaluator knows b and exponentiates
Enc(a) by b. The HE adapter protects a from the helper under its classical assumptions; it
does not claim to hide b from the decrypting client. Knowledge of
that output and either nonzero operand already determines the other operand:
this workload does not promise to hide authorized output implications.

[Paillier's construction](https://www.cs.tau.ac.il/~fiat/crypt07/papers/Pai99pai.pdf)
is additive homomorphic encryption, not FHE or a computation proof. The reference
uses signed centered integers and range checks, fresh OS randomness and64
Miller-Rabin rounds per prime candidate. It is unaudited, variable-time Python.
Setup/encryption/evaluation/decryption are separate costs, with cold setup and
online totals. Payload lengths are fixed-width accounting, not measured network
bandwidth or interaction time. Keys/random tapes are not retained.

The negative fixture deliberately changes a valid ciphertext so that33 decrypts
to34: HE does not detect this malleation. Only the independent synthetic oracle
recognizes the wrong result. A nonunit malformed ciphertext is rejected. No HE
integrity, threshold decryption, protected-helper witness or malicious protocol
claim is inferred. Groth16 supplies a different public verification relation,
which makes its assurance and cost different from HE-only evaluation.

Hardware-attested execution is **not-run**: no enclave, quote chain, measurement
binding, verifier or trust root is installed. A mock quote cannot satisfy it.
There is no claim of equivalent assurance or a measured HE/MPC/TEE bakeoff.

##83: fail-closed post-quantum inventory

`pq-inventory-v1.json` covers proof, commitment, signer, credential, transport,
setup and long-lived artifacts for the public research, private-v2, protected-aggregation, external
collaborative, Paillier and proposed mixed-PQ configurations. It pins implementation
sources, distinguishes missing integrations, records available sizes and preserves
null unmeasured/unreviewed security levels. BN254 field bits, Paillier modulus
bits and hash lengths are not security-level certificates.

BN254 pairing proofs and factoring-based HE block whole-stack PQ claims.
The source-pinned protected-aggregation profile also uses BabyJubJub Pedersen
commitments and Ed25519 issuer/client/recipient/durable-authority signatures;
these classical elliptic-curve components each require migration, alongside the
trusted private-delivery and storage assumptions. No new aggregation benchmark
is attributed to the inventory.
SHA-256 usage requires property- and quantum-model-specific review; it does not
repair vulnerable proofs or missing authentication/transport. A proposed ML-DSA
component is unimplemented and receives no performance result. [NIST's FIPS203–205
announcement](https://csrc.nist.gov/news/2024/postquantum-cryptography-fips-approved)
covers key establishment/signatures, not a replacement for the complete FZKML
proof stack. [NIST IR8545](https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8545.pdf)
identifies elliptic-curve discrete-logarithm quantum vulnerability. Tests reject a
claimed fully PQ mixed instance and every missing role. Inventory validation is
not independent cryptographic review. All four issues remain open for those
remaining security, integration, physical-network and external-review obligations.

The contributor explicitly certified and authorized DCO sign-offs for PR126
implementation and generated-evidence commits on2026-11-25. This certifies the
contribution under the DCO; independent scientific/security review and the
separate PR124 contribution certification are not supplied by this authorization.
