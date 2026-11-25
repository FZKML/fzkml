# Rational folded discrete Laplace v1 — #55

Selected source: Canonne, Kamath and Steinke, *The Discrete Gaussian for
Differential Privacy*, NeurIPS 2020 supplement, **Definition 28 and Lemma 29**,
printed pp.26–27 ([primary paper](https://proceedings.neurips.cc/paper/2020/file/b53b3a3d6ab90ce0268229151c9bde11-Supplemental.pdf)).
Lemma 29 applies to an integer scalar query with a declared adjacent-input
sensitivity bound and independent discrete Laplace noise. For the parameter
p=a/b in (0,1), its scale is 1/ln(b/a). The original geometric formulation is
Ghosh, Roughgarden and Sundararajan (2012), Example 2.1 and equation (1), pp.1674–
1675 ([primary paper](https://timroughgarden.org/papers/priv.pdf)). We use the
privacy result, not that paper's utility-optimality claims for count queries.
No upstream sampler source is copied; the folded sampler and following
finite-ring/vector derivation are original and require independent review.

For Z with probability `(1-p)/(1+p)*p^|z|`, the likelihood ratio between integer
queries q and q' is bounded by `(1/p)^|q-q'|` by the triangle inequality. With
independent coordinates, ratios multiply and are bounded by `(1/p)^||q-q'||_1`.
Thus the exact vector Q in SENSITIVITY.md has pure output-DP parameter
`epsilon=Delta_1*ln(b/a)`, delta=0, conditional on ideal independent uniform coins.
Summing the pointwise inequality over any subset proves the event definition.
Taking residues mod a fixed public odd M and centered decoding is deterministic
postprocessing, so cannot increase that bound. The only public released value is
`center_M((Q_j + Z_j) mod M)`; the trusted central computing role sees Q and inputs.
No DP claim protects that role's clean view, raw updates or publicly aborting M0.

An integer-only finite-state sampler implements the folded distribution exactly.
For G geometric on nonnegative integers, P(G=k)=(1-p)p^k. Its residue r has mass
`(1-p)*p^r/(1-p^M)` by an infinite geometric-series identity. Use integer weights
`w_r=a^r*b^(M-1-r)`, r=0..M-1. Draw an unbiased integer U in `[0,sum w)` and select
its cumulative-weight interval. Draw two independent residues and subtract mod M.
Since the difference of two independent geometric variables has the two-sided
geometric law, this samples Z mod M without ever generating an unbounded noise
integer or truncating a tail. The independent analytic reference is
`P(Z mod M=r)=(1-p)/(1+p)*(p^r+p^(M-r))/(1-p^M)`, including r=0. Exact rational
convolution and interval-enumeration tests compare it with the sampler's masses.

Supported a,b,M are integers with 1<=a<b<=256 and odd 3<=M<=257. Defaults are
255/256 and M=257. Integer weights require fewer than 2065 bits; Python arbitrary
precision prevents arithmetic overflow. Noise addition is intentional modular
postprocessing; centered wrap affects utility and is not an arithmetic error.
Every output residue has positive mass. No tail cutoff, float logarithm, fixed
noise-bit cap or fallback-to-zero is used. `secrets.randbelow` supplies the
OS-backed unbiased draws. Its rejection loop terminates almost surely with finite
expected work; there is no hard worst-case runtime bound. Deployment must not add
secret-dependent truncation or retry policies without analysis. Tests use private
injected integer ranks only through internal helpers, never a public seed option.

For replacement of one slot Delta_1=48, epsilon=48 ln(256/255). The accountant
returns the conservative exact rational upper bound `48/255=16/85`, using
`ln(1+x)<=x`, and delta=0; no downward float rounding is permitted. Zero-slot
add/remove uses 24/255=8/85. Up to m affected slots multiplies the bound by m.
Up to k releases uses basic sequential composition k times that bound, including
adaptive queries only when each conditional mechanism preserves these assumptions.
This is an accountant interface, not a persistent release/budget enforcement
protocol. Retries, side releases and visible failure metadata need separate review.

The reference is central: untrusted client noise shares, honest-contributor
thresholds, distributed Gaussian/binomial noise, secret denominators, compression,
and malicious noise cancellation are unsupported. An MPC protocol may implement
this *same joint law* only after a separate proof/role review; independently
adding these noises at each client is a different law. Quantization/clipping must
match the exact Q. Modular reduction before rounded division by four is unsupported;
a modular inverse is not integer division. Public policy fixes shape and parameters before
secrets are read. Timing, memory, source compromise and failures are outside this
output-only theorem and remain operational security obligations. OS CSPRNG use
is an implementation assumption; information-theoretic ideal randomness is the
mathematical model. Distribution tests and exact finite checks are conformance
evidence, not a DP proof, audited implementation, or privacy claim for FZKML.
