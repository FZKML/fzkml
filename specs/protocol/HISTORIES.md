# Connected history reference v1 — #51

This is a scoped executable interpretation of the M0 deployment in
`specs/m0/deployment-v0.1.md`. `fzkml_protocol.histories.assess` requires an explicit
certificate verifier; there is no default that accepts proofs. Experiments use an
**ideal validity oracle** over deliberately created reference certificates. No
signature, real proof or cryptographic backend is implemented by this module.

The externally pinned genesis fixes the session, policy/relation digests, model
and version, optimizer state (empty only), key epoch, four-client ordered roster,
phase, release IDs and release-ledger digest. Canonical domain-separated SHA-256
binds the entire public state. It is an integrity hash, not a hiding commitment.
The verifier must authenticate these exact roots as the proof's public statement;
merely checking a proof for another program/model or trusting a certificate hash
is insufficient. Unknown optimizer, rotation, roster or context changes require a
new protocol profile, not ignored fields.

For every edge, require exact parent and child roots, the same session/policy/
relation/key epoch, strictly consecutive sequence and model version, the supported
released phase, and one appended unique release ID with the complete ledger root.
Certificate bytes must be retrievable and hash to the referenced certificate ID.
Check the entire path before selecting any edge. Duplicate/reordered/disconnected
valid certificates do not constitute an accepted history. A missing certificate
is **unavailable**, not valid; withholding stalls verification even when a prover
could have generated a locally valid certificate.

Local validity, connectivity, global consistency, certificate availability and
observed completion are separate report fields. Two different children of the
same parent may both satisfy a relation: local proof validity does not select a
unique next state. Without selection both histories remain globally unresolved.
`TrustedLedger` provides only a locked, in-memory single-writer compare-and-set:
under its explicit trust assumption, the first complete path is selected and a
conflicting child is rejected. Prefix conflicts do not partially mutate its state.
It is neither durable nor consensus. Recreating/rolling back that ledger permits
equivocation again; the reference tests reproduce this limitation. Deployment
requires authenticated, durable, rollback-resistant selection, persistence before
acknowledgement and replay of the same stored result after uncertain delivery.
Those implementation dependencies remain #45/#48 and are not supplied here.

A possible quorum replacement needs an independent consensus specification.
For n signers, at most f Byzantine signers, and certificate quorum q, honest
intersection requires `2q-n>f`, plus authenticated identities, honest sign-once
rules for the complete parent/context and durable anti-double-sign state. For
n=4, f=1, q=3, intersections contain at least two signers and hence an honest one.
These arithmetic conditions alone do not implement a consensus protocol. Liveness
also needs an available honest quorum, certificate/data dissemination and a
stated timing/leader-recovery model. Neither a local proof nor a quorum formula
ensures delivery against a withholding coordinator. Independent cryptographic and
distributed-systems review remains open under #23/#51.

For the distinction between safety, authenticated quorums, persistent state and
liveness under timing assumptions, see Castro and Liskov, *Practical Byzantine
Fault Tolerance*, OSDI 1999, sections 3–4
([primary paper](https://pdos.csail.mit.edu/6.824/papers/castro-practicalbft.pdf)).
No claim is made that this reference implements PBFT or inherits its theorem.
