# Private transition proof: candidate v2

This document describes a bounded CPU research candidate for issues #32–#36. It
reuses the exact three-client fixed-point relation and Python `Fraction` oracle
from the language work. It does not claim production security, private training,
data authenticity, differential privacy, client participation, or durable state
acceptance.

## Statement and openings

`specs/private-transition-v2.json` defines fixed-width little-endian encodings
for a 392-byte context, a 472-byte statement, and a 652-byte proof envelope.
The v1 contract remains separately recorded in `specs/private-transition-v1.json`;
v2 changes the wire magic, commitment domains and proof statement, so v1 envelopes
are rejected by this implementation. The context binds a nonzero session and round,
the public full-state value at the parent, parent receipt, ordered roster,
three public aggregation counts, model version, preprocessing and initialization
IDs, fixed local-step count, data policy, optimizer, numeric relation,
transition-contract digest, and verifying-key ID. Unsupported model, policy,
optimizer, relation, or contract IDs are rejected. The statement adds
the model and data commitments and the declared aggregate output. The envelope
contains a backend ID, exact nested lengths, and one canonical compressed
BN254 Groth16 proof (128 bytes). Public-input order is domain, context digest,
model commitment, data commitment, counts, parent value, then output. The circuit
constrains the public parent value to its private initial weight.
Context parsing permits a parent output in [-80,80], but the implemented v1
initial weight is in [-32,32]. Proving fails closed if the previous output is
not representable as the next initial weight; the relation does not widen the
numeric-v1 input domain.

The model commitment is
`SHA256("FZKMOD02" || 32-byte blinding || SHA256(context) || i64le(weight))`.
The data commitment uses the distinct `FZKDAT02` domain and binds the three
ordered `(x,y)` pairs. Counts remain public and are bound to the context and
arithmetic. The candidate hiding argument assumes independent uniform secret
256-bit blindings and the random-oracle model. Collision resistance by itself
does not establish hiding. The implementation does not erase openings from
memory, prove data provenance, or show that the roster actually participated.

Each opening and proof uses OS randomness; deterministic openings exist only in
the public test fixture and constraint-audit helper. The proving parameters are
created fresh for each local session. This is not a trusted ceremony or
production setup. No seed-derived cryptographic randomness or exported key
format is provided.

## Circuit and parser evidence

### Backend decision

The CPU prototype uses arkworks Groth16 over BN254 (`ark-groth16` 0.5.0), an
established pairing-based proof backend with compact compressed proofs and
independent verifier support. It fits this small relation and permits actual
proof generation in unit/CLI runs. It requires a circuit-specific setup: this
code generates fresh parameters locally at process startup and does not run a
trusted ceremony, persist vetted parameters, or establish toxic-waste disposal.
The setup output is therefore for research measurement only. The backend's
proof verification and assumptions still require independent cryptographic
review; no formal soundness or composition claim is made here.

The circuit makes the weight, feature values, and labels private witnesses. It
checks their signed ranges, the existing prediction/gradient/update/aggregate
rounding relations, the two domain-separated SHA-256 commitments, and equality
to the public output. Count values are public inputs. The same maintained
arithmetic gadget is shared with the public-witness contract circuit.

`fzkml-private audit` consumes the shared 261-vector public arithmetic fixture
plus 32 deterministically generated bounded cases. The independent standard
library Python oracle supplies expected outputs. Every case is synthesized in
the private circuit and must satisfy it; the Rust reference computation also
must agree with the independent output. This is bounded implementation
conformance, not a proof of circuit soundness.

On the final local source tree, the audit passed all 293 cases with 196,140
constraints and 102 public fields. The fixture SHA-256 was
`454af1102b6eff77c878b9012600320bdb25c797447ff067c716ea9242d693b8`.

Tests include a unique-but-wrong relation, a negative remainder witness when
the remainder range is omitted, a missing divisor check, a missing output
equality, and detached model/data opening bytes. The detached and omitted
equality mutants demonstrate that the tests detect those specific faults.
Seeded parser mutations cover framing, size, malformed points, noncanonical
proof bytes, and an on-curve point outside the required subgroup. These finite
tests and mutation outcomes do not imply cryptographic soundness or security.

Verification compares the decoded statement with an independently trusted
`ExpectedTransition`, checks the configured verifier-key ID, and only then
verifies the proof against canonical public inputs. `TransitionChain` can consume
one accepted transition and derive the next expected context: receipt must hash
the preceding canonical statement, round must increase by exactly one, parent
value must equal the preceding full-state output, and session, roster, model,
policy, optimizer, relation, contract and key remain fixed. The new circuit
constrains each private initial model value to that public parent value. Counts
may vary within their declared bounds. This prevents state/delta confusion for
the implemented scalar full-state relation and rejects stale parents in this
in-memory reference.

The genesis `ExpectedTransition` remains a trusted caller input. `TransitionChain`
is not persistent, atomic across crashes, rollback-resistant, multiworker,
consensus-backed, authenticated, or an authorization service. A deployment must
protect and persist the authorized parent state and replay policy. Optimizer state
is the specifically named stateless SGD configuration; momentum and error-feedback
state are not represented or supported.

## Reproduction and measurements

`./scripts/validate-language` now runs the private-circuit conformance audit,
seeded parser/replay smoke, and an actual fresh-setup/prove/verify run on the
public synthetic vector. `scripts/profile_private.py` records setup, witness,
proving, verification and validation durations, peak resident memory, proof and
envelope sizes, constraint count, IDs, source revision, platform and workflow
identity. A single run is a diagnostic only, not a performance or utility study.

No manuscript-specific values, private inputs, user data, models, or training
observations enter the fixture or report. Independent cryptography, protocol,
and numerical review remains required before any stronger claim or merge.

### Local run snapshot

One release-mode run on 2026-11-24 using macOS 26.5.2, arm64, and Rust 1.85.1
generated and verified the two-transition public synthetic chain. Setup took
6.760 s; the two proving operations took
2.430 s and 2.905 s; the two standalone verification operations took 0.001303 s
and 0.001295 s. Witness preparation took 0.000027 s. The canonical proof payload
was 128 bytes and the framed envelope was 652 bytes. The circuit had 196,140
constraints and 102 public fields. A separate invocation of
`scripts/profile_private.py` observed peak process RSS of 789,495,808 bytes. This
is one noisy local sample on a shared
machine; setup is randomized, and these numbers are not a benchmark or a
performance claim.
