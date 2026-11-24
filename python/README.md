# Session 02 independent mathematical references

`fzkml_math/numeric.py` is the canonical arbitrary-precision Fraction oracle for
`fzknum-1.0.0`; `reference/numeric.py` preserves the historical imports. The
implementation is the existing independent Python oracle, promoted without
changing any algorithm, API, canonical bytes, contract digest or numeric-v1
fixture. It imports no Rust binding or torch. Run from the repository root with
`PYTHONPATH=.:src`; the repository namespace is `python.fzkml_math`.

`./scripts/validate-s02` runs the Python mathematical suite, deterministic vector
regeneration, lint/strict typing and an external Rust release-CLI comparison.
The existing language test module also loads the S02 cases, so the established
language workflow exercises them without changing shared workflow controls.
When that native CLI is not built, only its explicit comparison test is skipped;
`validate-s02` builds it and performs the comparison separately.

Original synthetic vectors live under `tests/vectors/synthetic/`. Inspected book
facts, source equation IDs, native UTF-16 locators, exact inputs, expected values
and tolerances live under `tests/vectors/book/`. Book fixtures are not regenerated
from a guessed model; adding/changing them requires source inspection. Private
manuscript exports and prose are never committed. The source revision and export
hash are bookkeeping, not an independently reviewed theorem or atomic snapshot.

## Two explicit arithmetic profiles

The implemented Rust candidate fzknum-1.0.0 uses one scalar feature, three clients,
scale 16, learning rate 1/4 and nearest-even rounding at each declared division,
then a rounded weighted average of full updated states. Its bytes/version and
all 261 prior valid vectors stay unchanged. A separate ordinary floating baseline
is an exploratory comparison, not an oracle for those integer semantics.

The inspected Chapter40 example has two features, learning rate 1 and nearest
rounding with ties toward positive infinity. `arithmetic.manuscript_step` gives
A=96, Q=6, E=2, G=(2,-1), W'=(6,5), decoded real-model half-squared loss 1/128 -> 1/2048 on the source inputs. It does not
validate the scalar Rust relation or silently revise it. The six native source
equations and Session03's edition-scoped IDs accompany that vector. Claim
registry ownership and status remain with Session03.

The original synthetic w=1, local states [1,1,2], weights [1,1,2] case independently
confirms that rounded full-state aggregation gives 2 while adding a rounded delta
gives 1. This is not a manuscript example. Odd integer translations change tie
parity under RNE, so moving rounding outside a state/delta transformation is
invalid in general. Session01 has this counterexample and owns any Rust change.

## Sensitivity of the released integer function

`FixedMean` declares public weights/denominator, bounded transmitted integers,
adjacency and maximum contributions per entity. It never infers personhood or
an unbounded-record sensitivity from a credential count. Small-domain enumeration
checks attainable neighboring outputs and provides witnesses. Private count,
compression, hidden residual and changed preprocessing need a new derivation.

For integer numerators separated by at most D and a fixed positive denominator N,
write D=qN+r with 0<=r<N. Nearest-even rounding changes by at most ceil(D/N) when
r>0. If r=0, translating by an even q preserves tie parity. Translating by an odd
q can add one more unit only when N is even, so half-integer lattice points exist.
Thus the lattice bound is q+1 for r>0 or (r=0, q odd, N even), and q otherwise.
The rounding errors are each at most 1/2; integer output differences then give the
first case, while exact integer translations give the remaining cases. This is
an original mathematical derivation, not a machine-checked universal theorem.
The suite exhaustively checks small lattice domains and bounded mean profiles.
The example RNE(1/2)=0 and RNE(3/2)=2 refutes a generic unadjusted ceil(2/2)=1 bound.
The earlier M0 half-up profile and its selected parameters remain separate.

## Privacy research reuse and independent checks

`python/reference-sources.json` identifies exact same-repository source commits
and byte hashes for unchanged math modules reused from PRs70,71 and73. They stay
at their existing `src/fzkml_protocol`, `src/fzkml_research` and
`src/fzkml_transcript` paths, so integration shares algorithms rather than
creating competing sampler, audit or accountant implementations. No Rust,
cryptographic state machine, shared claim registry or workflow is overwritten.

The new finite-law oracle independently convolves geometric residues and checks
the closed-form folded PMF, normalization, support and exact inverse-CDF test
boundaries. Whole finite neighboring laws can have their hockey-stick divergence
calculated exactly. This is distinct from an empirical frequency test, and is not
a proof of DP for an arbitrary sampler, entropy source, input universe or observer.
The existing folded mechanism's selected theorem is CKS, Lemma29; parameters,
query sensitivity, modulo post-processing and honest private entropy remain
separate requirements. See [CKS](https://arxiv.org/abs/2004.00010) and the original
PR70 derivation; this independent finite check does not certify that composition.

Other checks cover resampling versus post-processing, identical marginals with a
disjoint joint transcript, singular Gaussian support and conditional covariance,
dependent inclusion variance, noninjective projected norms, and failure/retry
accounting with exhaustion. The reused Gaussian examples are ideal analytic
geometry, not a discrete Gaussian sampler. Ledger budgets are declared synthetic
contracts and retain costs after failures; they are not a deployed privacy service.

For the source's hypothetical independent-run audit, one-sided binomial inversion
reproduces pL~.0821053, qU~.00368208 and epsilon lower bound~3.10451 with 95%
simultaneous confidence. Zero observed events do not mean zero probability.
Correlated scores from one model are rejected as independent model runs; missing
trials yield inconclusive inference. Numerical inversion uses 80-digit Decimal
and bisection, not verified interval arithmetic. The statistical method is
[exact binomial inversion](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm);
statistical confidence is not a posterior probability of privacy or a DP proof.

For the source's hypothetical fairness release, the certificate reproduces the
noise bound 11.9829 and population-gap upper bound~.5898 at conditional 95%
confidence. Small denominators or missing IID/frozen-classifier/noise assumptions
remain inconclusive. The ideal real-Laplace calculation is not a finite-arithmetic
DP implementation or a deployment fairness claim. The deterministic toy dataset
retains entity/source/time/duplicate metadata, enforces entity-disjoint holdout
and excludes future training records; its representation digest establishes
neither truth, consent, completeness nor representativeness. Repeated entities
are clustered observations and may not be counted as independent runs.

## Scientific records and limits

`PYTHONPATH=.:src .venv/bin/python scripts/run_s02_experiments.py .tools/s02`
produces a schema-validated local companion with source/lock/fixture digests,
assumptions, exact rational results, confidence calculations and the retained
small-denominator inconclusive result. No GitHub run ID or publication approval
is invented. The calculation runtime is diagnostic, not a hardware benchmark.
A retained record must name a clean immutable source commit; changes to inputs or
semantics require regeneration. Public-report promotion needs its own review.
No claim statuses are promoted, no issues are closed, and no merge is requested.

Initial development tests exposed an overly strict signed-field bound at p17,B8
and a missing section locator for the prose batch example; both were corrected.
The tests now distinguish strict 2B<p signed interpretation from strict residual
bounds, and attach the existing section ID to prose-only equations. These fixes
are not experimental support for any privacy guarantee.


## Session01 v2 handoff

`private_v2.py` independently encodes the S01 candidate context/statement and
checks the public parent-value/count relation. The pinned contract digest is
820850561fb327bd6c267ca5fc1c31078a20e05ed8b32b77c6775161572a9cd3.
`tests/vectors/synthetic/private-transition-v2.json` retains the exact candidate
contract bytes as fixture input, canonical contexts/statements, two chained
numeric outputs 9 then 10, malformed contexts and stale/wrong-parent cases. Run
`scripts/generate_s02_private_v2.py --check` without another checkout. S01 owns
the normative spec and Rust consumer; this is not a second independent protocol.

The 392-byte context, 472-byte statement and 652-byte envelope framing are
independent public test vectors. **The envelope layout contains an invalid zero
proof and must fail a real-proof gate.** Public fixed test openings are not
private operational entropy. Python does not implement Groth16 or subgroup
verification. A previous statement must already have been cryptographically
accepted before applying the pure lineage predicate. Native proof evidence
remains S01's responsibility. Contexts accept parent values in[-80,80], whereas
fzknum-1.0.0 arithmetic accepts initial weights only in[-32,32]; an out-of-range
parent is format-valid but unsupported for proving, and is explicitly rejected.


The Chapter40 loss fields use the exact decoded real linear prediction, not the
rounded program prediction. At W'=(6,5), decoded prediction 7/32 gives loss 1/2048;
the half-up encoded prediction is 4, with encoded residual 0 and corresponding
rounded-residual loss 0. These extra reference-only values are separately labeled
and do not alter the inspected manuscript outputs.

## Later numerical refinement (#85)

`refinement.quadratic` is an original synthetic precision experiment with
f(w)=(w-1/3)^2/2, analytic optimum 1/3, L=mu=1 and initial 0. It computes the exact
gradient, rounds each step at scales 1,2,4,8,16,32, and records every objective
gap, step perturbation, stationarity residual and conservative recurrence bound.
At rate 1/2, error obeys e_next <= e/2 +1/(2S) for this declared quadratic. The
rate 3 counterexample violates the contraction assumption and eventually fails
the declared state range instead of silently clipping or wrapping. These are
finite deterministic trajectories, not a theorem for other optimizers.

The classifier helper reports observed unchanged classes separately from the
strict margin>2*error certificate. A small-margin unchanged example remains
uncertified; a permitted perturbation can change its class. Stored-weight i32
margins are labeled separately from circuit residual/no-wrap analysis. Actual
constraint costs, attention refinement and general convergence remain not
measured, so #85 stays open. No new manuscript values are inferred.

The entity/time toy dataset tests fixture policy; it is separate from the one-
sample-per-client fzknum batch and is not fed into a proved training relation.
