# Observer-transcript reference, version 0.1

This specification and `src/fzkml_transcript/` address #56–#59. They are synthetic
conformance tools and exact analytic fixtures, not a deployed protected service.
The four-client M0 deployment remains transparent. References to reviewed
mechanisms, entropy services or trusted durable state are interface assumptions;
the real protocol dependencies #48/#49/#52/#54/#55 are not discharged here.

## Entropy and release policy (#56)

Fix the protected observer before drawing noise. Distinguish public experiment
seeds, private sampling randomness and cryptographic blinding. The declared
entropy policy requires private source material, data independence, independent
contributions for the additive-noise calculation, noise-independent inclusion,
and adversarial inputs fixed before the honest secret contribution is learned.
Unavailable assumptions reject the reference contract. These booleans document
external obligations; a caller setting them true does not establish honest
entropy. A proof of PRNG execution establishes a deterministic relation only.

For a conditionally uniform b-bit H independent of the adversary's chosen A
given its view, XOR with that fixed A permutes the b-bit space. If A can depend
on H, choosing A=H forces zero. The exact enumeration checks this distinction;
it is not a distributed randomness protocol. Domain separation requires a
compatible generator/distribution argument and cannot create entropy.

For independent surviving secret standard-Gaussian contributions with loadings
L_i, subtract known coalition/recovery contributions and use
`Sigma_H = sum_{i in H} L_i L_i^T`. Test every permitted surviving set against
every declared sensitive direction. A count of honest parties is insufficient
when their loadings do not cover those directions. Correlated sources instead
need the joint conditional law; they cannot enter this independent-sum routine.
Inclusion depending on noise, seed grinding, public seed exposure, dropout and
recovery revealing a seed invalidate the corresponding assumptions.

`EntropyUseRegistry` binds one locked public context and one externally issued
entropy-instance ID to a release ID, never storing seed bytes or deterministic
hashes of a low-entropy secret. It refuses changing that descriptor or reusing a
declared instance across releases. It is in-memory conformance state, not durable
anti-rollback protection. Covertly reusing a seed under a new instance ID remains
an external entropy-service violation. A crash must not authorize a fresh draw
under an already consumed release. The durable transcript journal tracks the
separate mechanism application and output identity; production integration must
atomically connect both services.

The analytic retry counterexample uses ideal Z~N(0,sigma^2), with the rejecting
party able to test Z's sign. Repeated draws until Z>=0 produce half-normal noise.
For neighboring query values 0 and Delta>0, `[0,Delta)` has probability
`erf(Delta/(sigma*sqrt(2)))` under the first input and zero under the second.
At Delta/sigma=0.1 this is 0.07965567455405796; any DP delta for that release
must be at least that value, regardless of epsilon. Expected attempts are two.
This conclusion assumes access to the sign of hidden noise. It does not assume
every aggregator has that access. Publishing a single already-private output or
an abort symbol via one fixed public-output predicate is post-processing;
resampling repeatedly, or filtering by a private noise test, is a different
mechanism. Attempt counts and failure diagnostics are additional observations.

## Fixed-cohort ledger (#57)

The `ReferenceAccountant` uses one explicit synthetic server observer,
synthetic-record adjacency, immutable policy digest and fixed unique cohort.
There is no subsampling amplification. Each observable aggregate, participation
message, proof/public input, diagnostic, failure, evaluation or recovery output
must have exactly one classification:

| Classification | Required reference justification |
| --- | --- |
| Accounted release | Registered finite-arithmetic theorem/entropy interface, unique application ID, declared epsilon/delta cost and available synthetic contract |
| Post-processing | Prior output references or fixed public context, no new protected access, declared transformation; identical delivery must match the retained digest |
| Computationally hidden | Explicit simulation/hiding assumption, separately classified public-input parents and a separate declared computational advantage |
| Explicitly unprotected | Named gap; this taints the complete-view claim and blocks subsequent accounted protected-release authorization |

Basic composition sums the declared epsilon/delta costs, assuming each mechanism
satisfies that conditional guarantee under the allowed prior history. New noisy
evaluations have new application IDs and pay again, including ones described as
failed/retried attempts. Accounted failures retain their cost. A byte-identical
retry of an event returns the original receipt and is not charged twice. Budget
exhaustion rejects authorization before publication. Rejected requests have no
protected output; any externally visible denial needs its own classified event.
Neither a clean sum revealed on failure nor a fresh private evaluation can be
reclassified as free post-processing. Hidden proof messages do not hide their
public inputs, acceptance bits, timing or participation. Computational kappa is
reported separately; it is not added to DP delta without a compatible theorem.

Creation is explicit and exclusive; recovery cannot initialize a missing or
empty journal. Appends are serialized with Unix interprocess locks, flushed and
fsynced, with the containing directory synced at creation. The authorization
record is written before a caller could publish. A failure after authorization
conservatively retains cost. The hash/sequence chain catches truncation and
inconsistent records; trusted root anchors can detect rollback to a prefix.
A fresh process needs a separately retained trusted anchor to detect a valid
old snapshot. A local hash chain is unauthenticated and supplies neither consensus
nor protection against an attacker rewriting the entire chain. Parent directories,
filesystem locking/fsync and external latest-state custody are trusted. Windows,
network filesystems, Byzantine storage and protected publisher integration are
unsupported. Journals hold public synthetic IDs and payload digests only.

## Gaussian geometry (#58)

The model is a fixed, public, data-independent workload, fixed private
contributions and a centered joint **continuous Gaussian** with one
dataset-independent PSD covariance Sigma. For a neighboring mean shift d outside
Range(Sigma), the affine supports differ: a null direction has deterministic
distinct outputs and finite-epsilon DP with delta<1 fails. An unsupported
direction is represented as `None`, never as zero cost. If d is supported,
`D_alpha = alpha/2 * d^T Sigma^dagger d`, alpha>1.

The exact rational solver finds any solution of Sigma*x=d and evaluates d^T*x;
for PSD Sigma and supported d this equals the pseudoinverse quadratic form.
Exact Schur elimination checks PSD, including zero pivots. There is no floating
eigenvalue threshold. Floats are rejected as matrix input. Small positive and
negative rational pivots remain distinguishable. The helper is dimension-bounded
and intended for small reference matrices, not a numerical SDP optimizer.

For jointly Gaussian, data-independent (Z_U,Z_V) with invertible Sigma_VV,
conditioning on known Z_V leaves
`Sigma_res = Sigma_UU - Sigma_UV * inverse(Sigma_VV) * Sigma_VU`.
Reject singular observed blocks in this interface. Data-dependent observations
require their own disclosure analysis. A declared finite set of participation/
recovery covariances must cover every permitted pattern; absent patterns,
unsupported directions or costs beyond the bound reject. This certifies only
the supplied finite set. Continuous sensitivity sets need a valid finite
reduction or robust bound, and adaptive training needs an applicable theorem.

For the inspected Chapter 75.6 example, C=1 and
`K=(8/5)*I_3-(1/2)*11^T`, with eigenvalues 1/10,8/5,8/5.
Convexity reduces the scalar cube maximum to its eight vertices; the result is
43/10. For vector rows of norm at most one, the objective is
`(8/5)*sum ||g_i||^2-(1/2)*||sum g_i||^2 <= 24/5`.
Three planar unit vectors 120 degrees apart attain it. Their exact Gram matrix
has diagonal 1 and off-diagonal -1/2, avoiding a floating sqrt(3) approximation.
Scalar sensitivity therefore cannot replace vector sensitivity for this class.

These calculations do not implement a Gaussian sampler or establish DP for a
discrete, truncated, fixed-point or modular mechanism. The finite counterpart
requires the matching sampler theorem/approximation analysis under #55. Related
primary sources: [Mironov 2017, v3](https://arxiv.org/abs/1702.07476v3) and
[Choquette-Choo et al., ICML 2023](https://proceedings.mlr.press/v202/choquette-choo23a.html).
No external code or dataset from these sources is imported.

## Completion-aware population (#59)

Condition on a declared public history and fixed potential updates g_i. Let p_i
be the fixed nonnegative target weights summing to one and pi_i>0 be each
positive-weight client's **final inclusion** probability. The estimator
`sum I_i*p_i*g_i/pi_i` has target mean `sum p_i*g_i` by linearity, without an
independence assumption. Its variance is the sum over i,j of
`p_i*p_j*(pi_ij-pi_i*pi_j)*<g_i,g_j>/(pi_i*pi_j)`.
The implementation independently enumerates a complete finite inclusion law and
checks its expectation/variance against this covariance expression.

In the source's two-client example, equal target weights, gradients (1,-1) and
final inclusion probabilities (1,1/10) give weighted mean zero and variance 9/4;
the unweighted observed mean has expectation 9/10. Using invitations (1,1)
instead of final inclusions gives a biased weighted mean 9/20. Dependent laws
with the same marginal probabilities 1/2 can give variances 0,1/2 or 1. Resource
coverage is reported separately at invited, selected, completed, accepted and
released stages. These stages must be nested and resource classes cover the
initially invited population. Counts and realized completion fractions are not
sampling probabilities or independent observations by themselves.

Inverse weights increase rare clients' variance and fixed-slot sensitivity.
Random denominator normalization, capping or clipping after weighting generally
changes the estimator; it is not silently treated as unbiased. Probabilities
depending on private data, adaptive gradients, estimated propensities and
unmodeled proof deadlines require additional analysis. This reference implements
no DP amplification theorem. Existing #60 compression/error-feedback work keeps
its own claim and branch; its actual transmitted vector, state lineage and
sensitivity must match any mechanism later registered in this ledger.
