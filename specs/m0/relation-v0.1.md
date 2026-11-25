# Standalone local transition relation, version 0.1

Status: specified target for #13/#23; implementation belongs to #26/#28/#33.
The source is Chapter 40's worked-example prose and §43.1. Native equations in
that section are separately indexed as pending-source-review. The equations
below are an original explicit engineering definition, not a transcription or
verification of the omitted native equation objects.

For one two-feature example, let encoded input be `(X0,X1,Y)`, initial model
`(W0,W1)`, scale `S=16`, no bias, SGD rate 1, and no optimizer memory. Define
integer rounding `rnd16(v)=floor((v+8)/16)`, ties toward positive infinity,
including negative inputs. Compute:

```text
A = W0*X0 + W1*X1
Q = rnd16(A)
E = Q - Y
G0 = rnd16(E*X0); G1 = rnd16(E*X1)
W0_next = W0-G0; W1_next = W1-G1
delta = W_next-W
```

For each rescale, enforce `v+8=16*q+r` with integer `0<=r<16`.
This is the rounded analytical squared-loss gradient. It does not differentiate
the rounding operator. No sigmoid, floating point, minibatch reduction, clipping
branch or stochastic rounding is included. Reject if the exact encoded delta
has squared norm greater than `2*48^2`; this is an admission predicate, not a DP
sensitivity or robustness result. All bounds below are enforced for every
permitted witness, not inferred from a successful example.

Public instance: protocol/relation version, sid, round, client authorization,
policy digest, model version, key epoch, canonical parameter digest, input-model
commitment, dataset snapshot commitment, selected-record index and output-delta
commitment. Witness: the selected record, its authorized opening/membership
path, the model opening, intermediate integers and commitment coins. Enforce
that all commitment openings and selection checks refer to these same values.
The dataset selection rule is the lexicographically first training record in the
registered split for that client. M0 proves this single selected-record step;
it does not prove processing every record in the snapshot.

Range contract: `|Wj|,|Xj|,|Y|<=16`, `|A|<=512`, `|Q|<=32`,
`|E|<=48`, `|Gj|<=48`, `|W_next_j|<=64`, `|delta_j|<=48`.
Reject inputs outside the domain. For a future field circuit, each signed
integer must have one canonical bounded encoding. The absolute residual bounds
for the dot, rescale, residual, gradient-rescale and update equations are at
most 1024, 1047, 96, 1559 and 128 respectively. A prime larger than 1559
excludes nonzero modular aliases for these equalities under those bounds.
The additional norm equality needs its own residual/no-wrap ledger (including
the `2*48^2` bound); the five bounds alone do not cover that new predicate.
No production modulus or cryptographic security level is selected here.

An independent exact arithmetic implementation must first reproduce the
readable example `(X,Y,W)=((16,-8),4,(8,4))`, producing
`(A,Q,E,G,W_next)=(96,6,2,(2,-1),(6,5))`, and then test negative ties,
remainders -1 and 16, extreme permitted values and modular aliases. These
expected values are specification examples; no proof/backend run is asserted.
The integer contract, canonical serialization and complete circuit range ledger
must be approved before claiming implementation conformance.
