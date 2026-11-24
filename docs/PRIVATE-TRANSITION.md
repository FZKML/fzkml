# Private transition proof: candidate v1

This document describes a bounded CPU research candidate for issues #32–#36. It
reuses the exact three-client fixed-point relation and Python `Fraction` oracle
from the language work. It does not claim production security, private training,
data authenticity, differential privacy, client participation, or durable state
acceptance.

## Statement and openings

`specs/private-transition-v1.json` defines fixed-width little-endian encodings
for a 316-byte context, a 396-byte statement, and a 576-byte proof envelope.
The context binds a nonzero session and round, parent receipt, ordered roster,
three public aggregation counts, model version, data policy, optimizer, numeric
relation, transition-contract digest, and verifying-key ID. Unsupported model,
policy, optimizer, relation, or contract IDs are rejected. The statement adds
the model and data commitments and the declared aggregate output. The envelope
contains a backend ID, exact nested lengths, and one canonical compressed
BN254 Groth16 proof (128 bytes). Public-input order is domain, context digest,
model commitment, data commitment, counts, then output.

The model commitment is
`SHA256("FZKMOD01" || 32-byte blinding || SHA256(context) || i64le(weight))`.
The data commitment uses the distinct `FZKDAT01` domain and binds the three
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

Tests include a unique-but-wrong relation, a negative remainder witness when
the remainder range is omitted, a missing divisor check, a missing output
equality, and detached model/data opening bytes. The detached and omitted
equality mutants demonstrate that the tests detect those specific faults.
Seeded parser mutations cover framing, size, malformed points, noncanonical
proof bytes, and an on-curve point outside the required subgroup. These finite
tests and mutation outcomes do not imply cryptographic soundness or security.

Verification compares the decoded statement with an independently trusted
`ExpectedTransition`, checks the configured verifier-key ID, and only then
verifies the proof against the canonical public inputs. Reusing the same valid
proof can still pass cryptographic verification. `ConsumptionState` separately
rejects a second use within one in-memory process. It is not persistent,
rollback-resistant, multiworker, consensus-backed, authenticated, or an
authorization service; an external verifier must supply the trusted expected
statement/configuration and durable replay policy.

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
