# M0 deployment and reactive functionality, version 0.1

Status: proposed specification, #13; no protocol implementation or independent
security review. Sources: manuscript §§2.1–2.3, 43.1–43.4 and 73.1, 73.4, 73.6;
exact source revision and locators are in `docs/research/`.

## Chosen deployment

One local process simulates four authorized cross-silo clients C0–C3, one
coordinator A and a public verifier V. The model owner is A. The task is two
feature squared-loss linear regression, no bias, one round and one selected
record per client. There is no network confidentiality or process isolation in
this simulation. Every fixture is original synthetic data. Institutional
identity, consent, truthful data, real deployment and useful learning are outside
the assurance of this artifact.

The proposed adversary is static, polynomial time, controls A and at most one
client, can schedule, replay, withhold and alter messages, and sees corrupted
clients' complete stored state. Corruption is chosen before initialization.
Adaptive/mobile corruption, host compromise, side channels and outsourced
proving are excluded. Cryptographic guarantees require a future instantiated
backend; the local simulator itself provides none. Authentication and a trusted
durable, append-only single-writer ledger are explicit ideal services. The
ledger, not a proof, selects one authoritative successor. This is a trust
assumption pending replacement and review under #51, not implemented consensus.
No fairness or guaranteed delivery is promised against a withholding server.

## State and commands

Public state is `(sid, round, policy_digest, relation_digest, model_version,
model_commitment, key_epoch, accepted_roster_digest, phase, release_ledger)`.
Local client state holds the dataset snapshot, selected record, model, optimizer
state (empty for this SGD profile), contribution and commitment randomness.
The coordinator's state holds authenticated submissions, validation decisions
and the durable output record. Future protected aggregation must specify the
additional computing parties and their views before enabling that mode.

1. `Initialize` fixes sid, the four sorted client IDs, public weights `a_i=1`,
   denominator `N=4`, initial encoded model `(8,4)`, scale 16, relation version,
   dataset selection rule, key epoch, permitted leakage, one release ID and a
   fixed deadline. An incompatible context cannot share sid.
2. `Submit` accepts at most one authenticated envelope per `(sid,round,client)`.
   The envelope binds policy, model, relation, dataset snapshot, full-state/delta
   type, key epoch, update commitment and payload digest. A retry with identical
   bytes returns the stored receipt; different bytes for that key are rejected.
   Proof acceptance means only the declared relation was accepted. Binding to a
   future protected payload is a separate obligation under #44.
3. `Close` deterministically freezes the sorted accepted roster at the deadline.
   All four expected clients must have valid submissions. A missing, invalid or
   unauthenticated contribution aborts the round, without renormalizing weights
   or silently choosing a smaller cohort. No late inclusion after Close.
4. `Compute` forms `D_j = round(sum_i a_i * delta_ij / N)` in signed integers,
   where `round(z)=floor(z+1/2)`, then `W_next=W+D`. It uses exactly the closed
   roster and its committed weights. Signed range/overflow checks are required.
   Field inversion is not integer rounded division. The initial transparent
   simulation may expose every delta; aggregate confidentiality is unsupported.
5. `Release` requires successful Close and Compute and the selected verification
   barrier. It durably stores `(release_id, parent_state, roster, W_next,
   transcript_digest)` before publishing the same record. Retransmission returns
   these identical bytes. A conflicting result or fresh randomized evaluation
   needs a new authorized operation; never overwrite an existing release ID.
6. `Abort` retains the closed/partial roster, public coarse reason and receipts.
   It releases no new model. Already observed data cannot be made secret by
   deleting a failed run. A new sid is required to retry an aborted computation.
7. `Recover` restores only the latest durable state and output record. An
   uncertain external delivery returns the stored bytes, never recomputes a
   randomized result. Missing or contradictory ledger state fails closed.
   Refresh and key rotation during this one-round profile are unsupported.

The receipt rule guarantees only receipt and later validation under this trusted
ledger model. Timely submission completeness against a malicious coordinator
requires an independent availability/receipt service; it is not implied by a
membership proof. Empty roster, zero/negative denominator, duplicate IDs,
wrong versions, stale parent model, unexpected dimensions, noncanonical values,
and conflicting release records reject before authorization.

## Views and permitted releases

| Observer | Declared view |
| --- | --- |
| Public/V | Policy, roster identities and weights, model/version commitments, proof/public statements, acceptance/rejection/abort bits, release record, final model, message lengths and timing available from the transcript |
| A | Public view plus received messages and scheduling; transparent simulation also reveals individual encoded contributions and all fixture contents |
| A plus Ck | Server view plus Ck's records, optimizer state, contribution, openings and protocol coins; public synthetic inputs remain known to everyone |
| Honest Ci | Own complete local state plus broadcast public transcript and final output |

The declared release is the final model and audit metadata. Public synthetic
records permit debugging, but their publication does not model private-record
protection. A future protected mode must remove raw witnesses from diagnostics
and state whether A sees a clean or noisy aggregate. A later three-trustee,
one-corruption design is a new version, not an assurance inherited here.
Acceptance, dropout, failure reasons and timing are leakage; none is free
because a proof is zero knowledge. M0 has no DP adjacency, epsilon or delta.
The candidate privacy units for later analysis are separately a record, entity,
client or organization; they must be selected before privacy accounting.

## Capability boundary

| Property | M0 status and evidence needed |
| --- | --- |
| Computational validity | Specified one-step relation; backend and adversarial implementation tests pending |
| Witness privacy | Conditional standalone proof target; no implemented hiding/proof backend |
| Aggregate privacy | Unsupported in transparent mode; protected transport and composition pending |
| Differential privacy | Unsupported; no mechanism, entropy protocol or accountant |
| Robustness | No poisoning guarantee, including for valid updates |
| Availability/agreement | Abort allowed; authoritative state assumes the external trusted ledger |

Tests must cover duplicate/racing submissions, replay, malformed context, late
proofs, omission, exact roster/weight conservation, all abort points, conflicting
branches and crash recovery. These are obligations for future implementations,
not claimed passing tests in this specification PR.
