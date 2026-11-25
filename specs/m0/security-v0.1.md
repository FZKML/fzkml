# Standalone security target and obligation ledger, version 0.1

Status: #23 conditional argument and review plan. No concrete proof backend,
setup, commitment or authenticated transport is adopted by this PR. The first
target is one isolated invocation of the local relation in `relation-v0.1.md`.
Aggregation and DP are outside this standalone target; their future obligations
are retained in `docs/research/security-obligations.json`. This is not an
end-to-end proof or an instantiated cryptographic security claim.

## Games and assumptions

Fix canonical public context x, the exact relation R, a security parameter and
an honestly generated allowed setup. The soundness game lets a PPT adversary
produce `(x,pi)`; it wins if the verifier accepts and no permitted witness w
satisfies R(x,w). The knowledge game additionally requires the selected backend's
extractor under its stated model, success/error bounds and access assumptions.
Ordinary soundness does not supply an extractor.

The witness-privacy target compares the honest proof view with a simulator given
the public x and allowed setup trapdoor. The statement itself, output commitments,
acceptance bit, dimensions, timing, identity and metadata are not hidden by this
definition. Commitments need separate message binding and hiding under the
chosen message/randomness distribution. A plain dataset hash is not hiding.
Authentication requires signature unforgeability plus authenticated key-to-role
registration; signatures do not establish real-world identity uniqueness.

Conditional integrity reasoning: knowledge extraction yields a witness for the
same canonical x; semantic circuit conformance connects that witness to the
specified integer program; commitment binding connects its outputs to the
accepted commitment; the transport equality relation must connect that commitment
to the consumed contribution. Each arrow is a separate assumption/obligation.
Before a concrete backend, range ledger, canonical parser and equality binding
are implemented and reviewed, none is discharged by this outline.

Standalone completeness is correctness of honest opening, relation evaluation
and proof generation for the declared domain. Boundary tests check specific
implementations; they do not establish completeness for all inputs or
cryptographic soundness. Zero knowledge of a proof plus hiding of commitments
requires a compatible hybrid simulation; shared randomness/trapdoors and
statement-dependent setup can invalidate a naive combination.

Assumption families: setup ceremony and trapdoors; commitment binding/hiding;
backend soundness/knowledge/zero knowledge and its algebraic/oracle model;
signature/key registration; transport equality; protected aggregation threshold
and leakage; adequate independent honest entropy; complete range constraints;
and the trusted ledger selecting accepted state. Each has an open ledger entry,
owner issue, affected claims, required artifact and independent-review domain.

## Error accounting and composition boundary

Only a justified hybrid/reduction can combine bounded component advantages,
with explicit reductions, query counts, concurrency, setup reuse and number of
invocations. Standalone error probabilities cannot simply be summed into a
reactive guarantee. Cryptographic distinguishing advantage kappa and soundness
error are not DP epsilon/delta, prediction error or numerical approximation.
Integer conformance is exact; approximation relative to real-valued training is
a separate numerical-refinement statement with its own assumptions (#26/#65).

If a complete ideal output mechanism is (epsilon,delta)-DP and the real
transcript is kappa-indistinguishable from one common simulator of that
mechanism under identical public neighboring context, the two replacements
yield computational DP slack `delta + (1+exp(epsilon))*kappa` for efficient
events. This is a conditional derivation, not a bound for M0: M0 has no DP
mechanism and no complete transcript simulator. Public commitments, rejection
bits, prior releases, aborts and later corruption must satisfy that premise.
The native equation at §73.7 remains pending exact-source review.

Two different valid transitions can extend one parent if both are permitted and
the coordinator can obtain both certificates. Presenting those valid branches
to isolated verifiers violates agreement without proving a false statement.
Accepted-state uniqueness therefore comes from the chosen ledger/agreement
assumption, not standalone proof soundness. Recovery and durable release identity
must enforce the same state policy.

Adaptive corruption, simulation extraction under concurrency, recursive depth,
refresh/erasures, aggregation witness availability and full observer-transcript
privacy require later compatible theorems. Every unproved step remains open for
independent cryptography, protocol, numeric or privacy review. No formal lemma
is supplied. A future Lean/Coq/other artifact must identify theorem, source,
version, explicit axioms and trusted kernel, and run that kernel in CI; numerical
tests cannot be substituted for it. M0 may close only after review of the scoped
argument and ledger, while later composition remains explicitly unproved.
