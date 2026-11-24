# Research protocol and threat contract, version 1.0.0

Status: specification awaiting independent protocol/cryptography/privacy review.
This version connects the scientific registry to separately owned implementation
profiles. It does not assert one integrated, production-secure FZKML system.
Sources: manuscript chapters 2, 7, 12–17, 40–43, 46 and 73; source edition,
revision, section anchors and inspection scope are in the claim/source registry.
The service commands are an original concrete engineering specification.

## Profiles and participants

| Profile | Exact computation and trust boundary |
| --- | --- |
| `m0-two-feature-v0.1` | Specified four-client simulation around the manuscript's two-feature worked step; scale 16, rate 1, ties toward positive infinity. No implemented proof is inferred. |
| `fzknum-1.0.0` | Three clients, one feature/record each, shared scalar parent model, scale 16, rate 1/4, nearest ties-to-even and a rounded weighted average of full local states. The original research proof exposes inputs. |
| `fzk-private-1.0.0-candidate` | The same three-client numeric computation with private model/data openings and an aggregate-output statement; a single prover possesses all witnesses. This does not establish that independent silos participated. |
| `protected-aggregation-v1-candidate` | Per-client private local-transition proofs, Pedersen/VSS payload consistency and a 2-of-3 recipient aggregation design; public parent model, fixed roster and weights. Its witness/disclosure boundary differs from the joint private-transition proof. |

Model owner/coordinator, authorized clients, verifier, admission issuer, three
aggregation recipients and durable release authority are distinct roles even
when simulated on one host. The selected profile declares which roles exist.
The protected candidate assumes an honest-but-curious coordinator and at most
one colluding recipient, conditioned on its authorized aggregate. Two colluding
recipients, compromised signing authority, malicious storage rollback, adaptive
corruption, side channels and real-world identity/data authenticity are excluded.
The standalone profile assumes its selected proof system/setup model; the
transparent profile provides no witness or aggregate confidentiality.

The authoritative service has trusted authenticated role keys and trusted latest
state. Authentication means a pinned key authenticated bytes; it does not prove
consent, institution membership or one-person uniqueness. Ed25519 and Groth16
are candidate implementation choices, not manuscript-mandated primitives or a
reviewed composition. Local test/setup randomness is not a production ceremony.

## Bound statement and state

The context binds protocol/profile/relation versions and digests, sid, round,
parent state/receipt, model version, initialization, optimizer and complete-state
lineage, data policy, key epoch, expected verifier key, ordered roster, public
weights, denominator rule, deadline, accepted-root and release ID. A message
declares `full-state` or `delta`; these are not interchangeable numeric types.
The current implemented scalar relation aggregates full states.

Public state records the current context, phase, canonical accepted roster,
possible-disclosure reservation and authorized stored release. Client secret
state includes records, selected model/optimizer openings, local update and
blinding/randomness where the profile requires them. Recipient secret state
contains shares/openings. The joint prover sees every witness needed by its
relation; moving it to a remote server changes the observer view.

Canonical parsing rejects unknown versions, wrong lengths/endianness, extra
bytes, noncanonical field/point encodings and unsupported dimensions before
cryptographic verification. Public inputs are reconstructed in the declared
order and compared against independently trusted expected context. A successful
proof for another context, key, policy, parent or roster is not admissible.

## Reactive commands

1. `Initialize` fixes profile, relation, keys, authorized cohort, weight policy,
   complete initial state, leakage and one release identity before witness/noise
   generation. Private eligibility and sampling policies require extra analysis.
2. `Submit` authenticates and parses an envelope, checks context and identity
   policy, and records at most one contribution per declared admission unit and
   round. Identical retransmission returns its stored receipt; conflicting bytes
   for an occupied identity reject. Real-world uniqueness is an external premise.
3. `Verify` checks the exact expected statement/key and selected proof relation.
   It distinguishes a full training transition from a norm/property proof.
   Public acceptance/rejection bits and reasons remain observations. Unsupported
   or absent proof adapters are unavailable, not successful skipped proofs.
4. `Freeze` fixes an immutable ordered accepted cohort, weights and parent.
   The current fixed-roster profiles require all selected clients to submit valid
   contributions; the protected candidate additionally requires its availability
   receipts. An omitted/late/invalid contribution aborts instead of silently
   renormalizing a smaller cohort. A receipt's timeliness/completeness guarantee
   requires an authoritative receipt/deadline/availability service.
5. `Aggregate` consumes only contributions cryptographically linked to the
   verified update and frozen roster. Per-client validity, payload equality and
   aggregate conservation are three separate obligations. Weighted full-state
   aggregation uses exact signed integers and the declared rounded division;
   field inversion does not replace it. A party must actually have the witness
   or a justified distributed protocol needed to generate an aggregate proof.
6. `ReserveDisclosure` durably reserves the disclosure slot and any budget before
   aggregate shares or other protected information can escape. A crash after a
   possible disclosure retains its charge/reservation, including on failed rounds.
7. `Release` checks the accepted-state certificate, threshold, verification
   barrier and accounting contract, then stores the immutable output before
   delivery. Repeated delivery returns those identical bytes. Fresh randomized
   evaluation is another mechanism, even if called a retry.
8. `Abort` retains receipts, phase, declared leakage and accounting history.
   Failure to publish a final model does not erase a previously visible clean
   aggregate, diagnostic or private acceptance bit. A changed cohort/context or
   new randomization needs a newly authorized operation.
9. `Recover` reconciles the latest trusted state, possible-disclosure record and
   cached release. Missing/contradictory state fails closed. Local in-memory
   consume-once state is not durable recovery. A hash chain alone does not stop a
   malicious server from presenting a valid older prefix or distinct branches.

The authority selects one successor per parent. Proof validity alone cannot
establish agreement among isolated observers or completeness of timely
submissions. Branching, refresh, key rotation, asynchronous staleness, dropout
after freeze and mobile corruption require a new explicit profile and theorem.

## Observer views and release boundaries

| Observer | Visible information and qualification |
| --- | --- |
| Public verifier | Public context, identities/pseudonyms and weights as declared, commitments, proof/public inputs, acceptance/failure metadata, timing/length information, authorized output and ledger commitments |
| Coordinator | Public view plus received protocol messages; transparent profile exposes records/updates; protected candidate excludes individual shares from its coordinator API, subject to its actual transport/custody assumptions |
| Coordinator plus one recipient/client | Union of those views, that party's local records/openings/shares/randomness and authorized aggregate; privacy analysis conditions on all known contributions/noise |
| Joint standalone prover | Every private witness used in its joint transition, regardless of verifier zero knowledge |
| Durable authority | Accepted-state/release records, authentication and possible-disclosure state; rollback/corruption of that authority is outside the trusted-storage profile |

Witness privacy, aggregate confidentiality, DP, robustness, agreement and
availability are separate capabilities. A deterministic dataset hash is not a
hiding commitment. Dataset binding proves representation consistency, not truth,
consent, completeness or representativeness. A valid bounded/algorithm-compliant
update can remain statistically harmful. An authorized clean aggregate is not
DP. No current profile advertises a complete transcript DP guarantee.

For future DP, declare adjacency (record, entity, client or organization), actual
released function and all observable participation/proof/failure/evaluation data.
Fix cohort accounting before using any subsampling theorem. Require a matching
finite-arithmetic sampler theorem, honest conditional entropy after collusion/
dropout/recovery, and complete-view simulation. Continuous Gaussian covariance
fixtures are not a finite sampler or adaptive-learning proof.

## Numeric separation that implementations must preserve

The manuscript example is an input/expected-trace fixture, not authorization to
replace the implemented rounding or optimizer. With ties-to-even, converting a
full-state average into a parent-plus-rounded-delta average can change results:
take parent 1, local states (1,1,2), counts (1,1,2). The full-state average rounds
6/4 to 2, while parent plus rounded average delta is 1+RNE(2/4)=1. The valid
implemented inputs `(x,y)=(0,0),(0,0),(8,8)` produce those states. This is an
original derived conformance counterexample, not a manuscript numerical quote.
Session 02 should verify it against its independent oracle before adoption.

Rounding also changes sensitivity reasoning. On the integer-numerator lattice
with fixed denominator 2, RNE(1/2)=0 and RNE(3/2)=2. The numerator changes by 2,
but the output changes by 2, exceeding ceil(2/2)=1. Odd integer translations can
swap half-tie parity. This original counterexample refutes an unqualified
ceil(D/N) shortcut for this RNE lattice; it is not a general sensitivity theorem.
Any privacy bound must specify the exact lattice, denominator, adjacency and
payload. It does not change the separate M0 ties-toward-positive-infinity rule.

Evaluation metrics must also declare whether they use exact decoded-model
predictions or the rounded encoded prediction from the training relation.
These can have different losses even for the same final weights. Neither a
loss label nor a source-example match proves useful learning or a privacy bound.
