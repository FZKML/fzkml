# M5 synthetic model workloads

This slice covers FZK-R051 through FZK-R057. The literal fixtures are original
and public. The run contract names the observer, privacy unit and release for
each workload. The run record binds the inputs and implementation files by
digest and records the proof phase times and outcomes. These fixtures do not
use numerical values taken from the manuscript.

## Reproduce

Use the repository's Rust and Python environments and run from the repository root.

```sh
uv sync --locked
cargo test --release --locked -p fzkml-core --lib model_workloads::tests
cargo build --release --locked -p fzkml-core --bin fzkml-m5-proof
uv run --locked python -m unittest discover -s experiments/m5
uv run --locked python experiments/m5/run.py --output /tmp/fzkml-m5-run.json
uv run --locked python experiments/m5/run.py --check /tmp/fzkml-m5-run.json
```

The existing Rust workspace test command exercises the three real proof
round trips and negative cases. The independent Python runner checks each
output and records a separate release-mode CPU repetition. It measures the
whole child process peak RSS. Setup, proving and verification times use a
monotonic clock in the child. The record retains the base Git SHA and exact
source-file digests when the source tree is dirty. No proof generation is
performed in `--check` mode. Use the Rust test and runner to reproduce execution.

## #89 · Clipped coordinate median

Five ordered private vectors have two signed integer coordinates in
`[-4,4]`, with squared norm at most 16. Both coordinates go through a fixed
sorting network. A comparator selects a permutation of its two operands
and proves that their ordered difference is in `[0,8]`. The public result is
the middle value in each sorted column. Permuting equal values has no effect
on the result. The clip check validates the supplied payload; the circuit
does not attest to its origin or compute it from a raw update.

The SHA-256 preimage is the eight ASCII bytes `FZKM5MD1`, a fresh secret
32-byte blinding, and ten bytes obtained by adding 4 to the coordinates in
row-major order. Each shifted byte is constrained equal to its arithmetic
wire. The separate neural circuits use the same construction with different
tags. A verifier must obtain its expected root and circuit-specific key from
a trusted source. The joint prover sees all updates. The verifier receives
the root and aggregate. There is no secure aggregation transport or roster
authentication in this workload. Hiding relies on secret fresh high-entropy
blindings and the modeled hash and proof assumptions.

- **Sum-only limitation.** The scalar lists `[-2,-2,0,2,2]` and
  `[-2,-2,-2,2,4]` both sum to zero and have medians 0 and −2.
- **Replacement sensitivity.** In two dimensions, at least three vectors
  match or exceed each coordinate's median magnitude in its median sign
  direction. The two sets must intersect. Thus the median lies in the
  radius-(C) ball. Its L2 sensitivity is at most (2C), and the reference
  reaches it by replacing one ((-4,0)) with ((4,0)) when the four other
  inputs split evenly between the extremes. The integer radius-four disk has
  maximum L1 norm 5, so the same argument gives an L1 bound of 10, attained
  by opposite ((3,2)) and ((-3,-2)) medians. As a calibration target,
  independent two-sided geometric noise on each coordinate with mass
  proportional to `exp(-epsilon * abs(k) / 10)` gives an output-only
  likelihood ratio at most `exp(epsilon)` under fixed-roster replace-one
  adjacency. Noise, transcript privacy and composition are outside this run.
- **Geometric median.** Let an inlier fraction (1-alpha) lie within distance
  (r) of (g), with (alpha<1/2). For any (z) at distance (D) from
  (g), each inlier's distance to (z) minus its distance to (g) is at
  least (D-2r). Each outlier contributes at least (-D). By optimality
  at a geometric median, the sum is nonpositive, which yields
  (D <= 2(1-alpha)r/(1-2alpha)). The scalar special case in the reference
  has distance 1 and bound 8/3. The proved estimator is the coordinate
  median described above. For other geometric median estimators and
  secure averaging constructions, see [Pillutla, Kakade and Harchaoui](https://arxiv.org/abs/1912.13445v2).
- **Public cosine threshold.** Given a public reference (r) and private
  (u), the reference accepts cosine at least (1/2) when both squared
  norms lie in `[1,16]`, (d=u·r>=0) and (4d²>=||u||²||r||²).
  The respective products are bounded by 1024 and 256. Both zero-vector
  cases reject. This gate is a separate reference calculation. A deployment
  would need to bind its result to the same committed payload in its own
  relation and account for leakage from the decision. No pairwise distances
  are disclosed or computed by the median relation.

## #90 · Neural inference and full update

The model has one input, two ReLU units, one linear score, no bias and no
batch-normalization or preprocessing stage. Weights are in `[-4,4]`, the
feature is in `[-2,2]` and the training label is in `[-1,1]`. Inference outputs
the score and uses tag `FZKM5IF1`. Training uses tag `FZKM5TR1` and outputs
the four updated weights in their original order. Input order is the two
first-layer weights, two second-layer weights, feature and (training only)
label. Encode each as one byte after subtracting its declared lower bound.

The derivative of squared loss `(score-y)^2/2` uses `ReLU'(0)=0`. Each step
is the gradient divided by four, rounded to the nearest integer with ties
to even. All four gradients use the previous weights. The prover constrains
both forward and backward paths, both ReLU branch implications, the
rounded division and all output equalities. The preregistered fixture gives
score −2, gradient `[12,-6,-6,-6]` and next weights `[-2,3,0,3]`. Classification
ties predict the positive class. The integer update gets one of three
held-out signs right and the rational update gets three of three. This
fixture illustrates a rounding-induced utility gap on a fixed trace.

| Value | Integer bound |
| --- | --- |
| Each hidden preactivation | −8 through 8 |
| Each activation | 0 through 8 |
| Score and residual magnitudes | 64 and 65 |
| Each gradient magnitude | 520 |
| Rounded gradient magnitude | 130 |
| Each next weight magnitude | 134 |

The largest order, range and arithmetic residuals are below (2^{17})
using the declared operand and gadget bounds. This is below the BN254
scalar modulus. It prevents modular aliasing in these integer equations.
SHA-256 has its own Boolean circuit. The proofs use local circuit-specific
Groth16 setup with the existing arkworks version. The setup and witnesses
are held in one process. These runs leave multi-example training, external
key custody and distributed proving open. See [Groth's construction](https://eprint.iacr.org/2016/260).

## #91–#95 · Reference experiments

| Issue | Executed synthetic experiment | Open evidence |
| --- | --- | --- |
| #91 | Fit one rank-one correction to a frozen two-token bigram head, compare exact and quantized corrections on an entity-disjoint holdout, measure host CPU token predictions, and test a separate authorization-first retrieval allow-list with a synthetic canary. | Transformer and GPU experiments, proof resources, certified latency, zero-knowledge retrieval or retrieval completeness. |
| #92 | Execute a bounded majority preference, teacher/student cohort-logit transfer with clipping and a minimum cohort size, and a naive generator that emits a unique synthetic canary. | Real preference alignment and privacy calibration. The isolated canary test gives one observed leakage case. |
| #93 | Run two binary worlds with identical marginals, opposite optimal predictors, a swapped alignment and an absent modality. Authorized exact paired truth tables score 2/2. The best deterministic marginal-only rule guarantees 1/2 over the two worlds. | Learned embeddings, negative sampling, retrieval quality at scale and a proof of paired training. |
| #94 | Enforce a two-edge user cap in two synthetic silos with a declared item vocabulary, reject duplicate and unauthorized edges, and evaluate top-one recommendation for users absent from the training split. Item embeddings are fixed public inputs. | Trained embeddings, negative sampling, aggregation or neighborhood completeness proofs, and any user-, node- or edge-level privacy claim. |
| #95 | Fit a seasonal profile to separate training entities and earlier event times, compare per-source horizon errors with persistence, and record actual host CPU time, serialized payload bytes and modeled invitation/completion/admission under a deadline and memory cap. | Physical edge measurements, network transport and control or safety guarantees. |

The paired evaluation uses held-out copies of the same finite synthetic worlds
to evaluate identifiability. The recommendation support edge for each held-out
user is distinct from its evaluation target. The forecast history and target
windows are disjoint across cutoffs. The recording never treats modeled device
budgets as measured hardware constraints.

## Recorded CPU diagnostic

One release-mode run on macOS arm64 with Rust 1.85.1 is in
[observed-arm64.json](observed-arm64.json). The proof process peak RSS was
171,720,704 bytes. Each verifier rejected a changed
output, changed commitment and malformed proof. The timing is a single host
observation and excludes compilation and network execution.

| Relation | Constraints | Setup (s) | Witness and proving (s) | Verification (ms) | Bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Inference | 39,589 | 1.354 | 0.596 | 1.054 | 128 |
| Median | 40,048 | 1.423 | 0.604 | 1.728 | 128 |
| Train | 39,912 | 1.399 | 0.602 | 1.010 | 128 |
