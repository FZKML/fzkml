# v0.2 protected aggregation research implementation

This draft implements issues #44–#50 on top of PR #72's Rust numeric contract.
It is a scalar, fixed-cohort research artifact. Passing fixtures establish the
observed implementation behavior; independent cryptographic, protocol and
publication-control review is pending. The issues remain open. No production
security, general federated-learning service, DP guarantee, formal composition
proof or book theorem is certified here.

## Design decision and alternatives

Use degree-one Shamir sharing with Pedersen verifiable secret-sharing commitments,
three aggregation recipients, threshold two, and a separate private Groth16 local
transition relation. Pedersen's construction supplies the algebraic sharing and
opening consistency argument under prime-order-group/discrete-log assumptions;
its paper does not certify our circuit, authentication, storage, generator map or
composition. See [Pedersen, CRYPTO 1991, sections 3–4](https://cgi.di.uoa.gr/~aggelos/crypto/page8/assets/Pedersen-VSS.PDF).
The present decision is a proposal for independent review, not an approved
protocol standard. Exact machine-readable choices are in
[aggregation-v1.json](../specs/aggregation-v1.json).

Pairwise masking was considered: it would require a distinct key agreement,
mask-cancellation and dropout-reconstruction protocol before a credible vertical
slice. Encryption to the coordinator would reveal individual contributions at
decryption. A standalone norm proof supplies no payload equality. A production
multiparty setup, distributed ledger or anonymous credential system would each
require a separate reviewed protocol. The chosen VSS construction makes opening
checks and threshold recovery explicit in the smallest scalar integration case.
No copied third-party implementation or paper prose is included in this code.

## Exact proved relation and payload

Inputs are bounded integers `w,x,y` in [-32,32]. Scale is 16; every division uses
round-to-nearest with ties-to-even (RNE):

```
p = RNE(w*x / 16)
g = RNE((p-y)*x / 16)
v = w - RNE(g / 4)                  full state, constrained to [-80,80]
u = v + 80                         encoded dense scalar, [0,160]
D = (x+32 + 65*(y+32))*G + rd*H     hidden synthetic-data commitment
C0 = (u + ctx)*G + r0*H             proof-bound output commitment
C1 = a*G + b*H                     sharing coefficient commitment
s_j = u + j*a; t_j = r0 + j*b      private payload to recipient j in {1,2,3}
G*s_j + H*t_j = C0 - ctx*G + j*C1  recipient acceptance equation
```

The circuit makes `x,y,r0,rd` private; public inputs are `w,ctx,C0.x,C0.y,D.x,D.y`.
`ctx` is the little-endian first 31 bytes of the domain-separated SHA-256 context
ID and is range constrained to 248 bits. The context includes version, session,
sequence/round, complete parent state, exact ordered roster and weights, recipient
keys, issuer, authority, proof key, dimensions, encoding and budgets. Client
signatures bind the full context ID, credential, both commitments, data commitment,
proof and child state ID. Canonical JSON is serde's fixed struct/tuple field order,
integer-only encoding without whitespace; cryptographic points/scalars use exact
32-byte validated compressed arkworks encodings and proof length is exactly 128.
No cross-language alternate canonicalization is implicitly accepted.

A valid proof accompanying a different delivered share fails the recipient's
opening equation (D.2). Wrong session, weights, key, dimensions or encoding fail
scope/signature checks or change the proof's context. This is a bound on the
actual rounded scalar supplied to sharing. Low-rank norm-only encoding is rejected;
no matrix adapter, Gram identity or dense low-rank conversion is implemented.
The local clipping policy is the explicit bounded arithmetic domain; it does not
claim a general norm-clipping mechanism. Data provenance/feature extraction and
truthfulness are outside the relation: a malicious client can prove an allowed
transition on adversarial but in-range inputs.

`H` is a fixed domain-separated SHA-256 try-and-increment y-coordinate map into
BabyJubJub, followed by cofactor clearing and identity/G exclusion. Unknown
logarithm relative to G is an explicit random-oracle/parameter-review assumption;
this is not an RFC 9380 suite. Hiding comes from independent uniform Pedersen
blindings. Computational binding and Groth16 soundness need their usual group,
setup and knowledge assumptions. BN254 does not carry a 128-bit claim here. The
local random Groth16 setup is not a multiparty ceremony. Secret erasure,
constant-time execution and side-channel protection are unverified.

## State, admission and observer views

The versioned complete parent includes model, monotonic sequence, optimizer,
preprocessing/initialization/policy IDs, local step count and full-state kind.
Only `sgd-rne-v1`, one local step and absent momentum/error feedback are supported.
Any supplied hidden optimizer/residual state is rejected; those algorithms cannot
silently omit state. Each accepted child commitment covers the same metadata and
proved output. The released child advances sequence even if its model repeats.
The authority checks the current parent at begin, admission, freeze, disclosure
reservation and release commit, using immediate SQLite transactions for mutations.

The trusted issuer signs serial, stable entity pseudonym, client key and round
validity. The credential does not establish personhood or anonymity. Admission
atomically enforces unique `(context,serial)`, `(context,entity)` and canonical
nullifier `H(domain,session,round,issuer,serial)` in one SQLite authority. Maximum
accepted contribution count is one per issuer-attested entity per round. Trust
in the issuer's consistent mapping is essential; multiple falsely distinct
entities are not detected. A person can control multiple entities. No
person-level sensitivity bound follows. Revocation is checked at admission,
freeze and the first disclosure reservation. Revocation after reservation cannot
undo disclosure; the roster/decision remains immutable.

| Role | Allowed view |
| --- | --- |
| Client | Own inputs, keys, witness, blindings, three shares and public context |
| Recipient j | Public context/contribution/proof, only its per-client share/opening, accepted root, signed permit and own aggregate opening |
| Coordinator/ledger | Public credentials, stable pseudonyms and validity/revocations, commitments/proofs, signed availability receipts, fixed accepted roster/weights, permit, verified aggregate openings, clean weighted sum and released model |
| Measurement log | Fixed synthetic reference result, aggregate IDs, public setup/key digests, phase costs, size totals, process RSS and explicit limitations |

Witness and private Packet types have no Debug or Serialize. Contribution
construction consumes its non-cloneable witness, making commitment blindings
single-use at this API boundary. Delivery retries reuse the original immutable
contribution and packets; newly proving a replacement is not an idempotent retry. The coordinator API
never takes individual packets. The fixture runs all roles in one process and
delivers typed objects through APIs; authenticated confidential channels and role
isolation are assumptions, not implemented transport properties. The in-process
orchestrator has all roles' memory. Logging policies and constant message shapes
do not prove timing or side-channel privacy. Stable entity/serial/client keys,
round participation and repeated contexts are linkable metadata.

## Accepted receipt, release and failures

All three signed availability acknowledgments are required for each client before
admission. Recipients pin the first contribution body for a serial/context and
reject equivocation. Freeze requires exactly the ordered three-client context
roster with exact declared weights; incomplete sets, duplicates and wrong weights
are rejected. The accepted root hashes complete accepted envelopes including
proofs and credentials. This checks declared-set conservation, not timely service,
fair inclusion, willingness to serve, or all submitted requests being accepted.
Recipients keep private shares in memory: loss after acknowledgment is a detectable
availability failure, not magically durable recipient storage.

The state machine is `open -> frozen -> observing -> released`, or an immutable
abort before release. Session/sequence slots prevent reinterpretation. A unique
parent disclosure slot prevents a second aggregate context even across sessions
and even after an exposed attempt aborts. This is deliberately conservative:
a parent can become unusable after a reservation that never actually disclosed.

Before any aggregate share is returned, a FULL/WAL SQLite transaction commits the
root, deterministic signed permit and `possibly-exposed-clean-sum` observation.
Recipients require that permit and the same accepted root. Recipient j produces
weighted shares/openings; the coordinator verifies the weighted Pedersen equation,
strict signature and role/release binding. Two distinct valid coordinates recover
`sum(weight*u)`; values outside `[0,160*denominator]` fail without field wrap.
Subtract `80*denominator` and apply RNE using the exact fixed denominator. No
individual contribution is reconstructed on dropout. The verified clean sum
observation is durable before returning it. Finish commits the immutable result,
child head and cached outbox before caller delivery. Duplicate delivery returns
the same decision and records a redelivery event. Attempt events are append-only
by `(context,attempt,outcome)`; released/aborted decisions cannot be overwritten.

An abort before reservation has no new protected aggregate observation in this
API model. Reservation retains conservative possible-exposure evidence across
crash/abort. Observing the sum then failing the user-facing round retains
`exposed-clean-sum`. This is disclosure accounting, not an epsilon/delta accountant;
removing a UI result cannot erase the clean sum. A previously issued permit
cannot be recalled from recipients on abort; possible-exposure evidence therefore
persists even if the aborted ledger refuses further observation/release calls. Reopening uses the same genesis,
issuer and authority binding; a new authority/database is a new trust domain, not
rollback-resistant recovery of the old one.

Privacy assumes at most one colluding recipient and an honest-but-curious
coordinator, conditioned on the authorized clean aggregate and public metadata.
The aggregate itself can reveal a remaining client's contribution if others are
known; this is not output privacy. Availability requires at least two valid
cooperating recipients after all three preparation receipts. The total unavailable
budget includes malformed, withholding and crashed recipients: one malicious
withholder plus a different crashed honest recipient leaves only one and aborts.
One malformed report is rejected; a retry with the other two verified reports can
complete. Configured corruption or unavailability budgets above one are rejected.
Two secretly colluding recipients, corrupted signing authority, issuer abuse,
malicious disk rollback, compromised host and unavailable threshold are outside
the supported guarantee. Runtime checks do not detect hidden out-of-model
collusion. Client dropout before preparation can abort; after freeze the roster
cannot shrink or change its denominator. No unconditional liveness is claimed.

SQLite durability relies on trusted storage, OS/VFS synchronization, private parent
directories and one non-rollbackable authority. Files are created mode 0600 and
symlinks, hardlinks and broad permissions are rejected; this is not protection
against a malicious local filesystem or trusted-directory replacement race.
[FULL/WAL synchronization behavior](https://www.sqlite.org/pragma.html#pragma_synchronous)
and [Ed25519 strict verification](https://docs.rs/ed25519-dalek/2.2.0/ed25519_dalek/struct.VerifyingKey.html#method.verify_strict)
are library properties; our integration still requires review. Process-exit tests
do not simulate power loss or prove the storage stack's durability.

## Reproduction and evidence

Run `./scripts/validate-aggregation` with the repository's pinned Rust 1.85.1,
Python 3.11.14 and uv 0.9.11 environment. It checks real release-mode proofs and
runs three fresh synthetic native processes. The original numeric-v1 fixture
uses model 8, x=[16,-8,24], y=[16,-16,8], weights=[1,2,1]; local full states are
[10,10,6], exact weighted sum 36, denominator 4, released model 9. These are original
repository synthetic reference values, not reproduced manuscript calculations.
All repetitions, setup costs and limitations are retained in
`.tools/aggregation/aggregation-{profile,result}.json`. Schema 1.1.0 records local
execution truthfully with null workflow IDs; CI uses the actual CPU workflow run.

Timers separately record native reference training, host witness/blinding creation,
proof/contribution construction (including circuit synthesis), verification and
admission, freeze/reserve, recipient aggregation and durable release. End-to-end
wall/RSS include all native roles, setup and SQLite. Logical application bytes
count delivery multiplicities, canonical public JSON and fixed private fields;
there is no measured network transport. Communicate time is envelope encoding
only and is not a complete communication latency. RSS uses a fresh sampler whose
only child is the native process; compilation and Python/git child RSS do not
contaminate it. No per-role memory, learning quality or scaling claim follows.
Publication review stays pending and public report rendering rejects these
records; schema changes do not manufacture approval.

| Issues | Executable evidence | Pending review/limit |
| --- | --- | --- |
| #44 | Real private proof, substituted payload/output/data rejection, wrong context/key/encoding tests, R1CS mutation checks | Hiding/binding/composition argument and parameter selection need independent review; scalar only |
| #45 | Complete-state IDs, stale/replayed parent checks, optimizer/residual and delta rejection | Momentum/error-feedback algorithms unsupported |
| #46 | Three real client proofs/shares, exact 36/4->9, API observer separation, phase/size/RSS records | Transport/process isolation and independent security/publication review |
| #47 | Four concurrent SQLite admissions yield one acceptance; expired/bad credentials, entity quota and revocation reject | Trusted issuer/entity definition; no personhood or unlinkability |
| #48 | Canonical fixed roster, signed availability, sum opening checks, omitted/duplicate/wrong-weight/role rejection, lost storage failure | No fairness/timely-submission completeness guarantee |
| #49 | Actual subprocess exits after reservation and after outbox commit; reopen/redelivery, clean-sum versus no-sum abort, cross-session disclosure-slot rejection | No power-loss/rollback proof; observation is conservative, not DP |
| #50 | Substituted/malformed shares, unauthorized permit, missing/duplicate roles, threshold failure, equivocation and range checks | Privacy and availability bounds above; no detection of hidden excess collusion |

Source manuscript inspected for task scope: canonical Google Doc
`14tD223seyGYrtYZJOuPKtH0lwlKo4To4p4aRHhKI9RY`, tab t.0, snapshot MS20261124
(no author-declared edition), revision
`AHj4eMTDhszajz9XWwtYr25APOt8jDNWJ06dbjKxf-xlK9xmwk34ZzwRRUkjWfouVFGjH-x3SMlEEFPR_syq3-Z8kERBX1SruWGFOdkln3SW`.
Task mappings inspected: D.2 payload substitution; D.11 abort visibility; D.12
complete artifact; D.14 lineage; D.18 full-state semantics; D.28 nullifier/identity;
D.31 dense versus low-rank binding; D.34 aggregate conservation; D.47 extraction
scope. The mapping is source-review metadata, not an extracted theorem registry
or permission to redistribute private manuscript text. No manuscript passages
or private numerical inputs are committed.
