# Conditional finite-ring reference proposition, version 1.0.0

This original derivation defines a small test mechanism. It does not transcribe a
manuscript theorem or certify a distributed implementation.

Fix the public cohort of three slots. Clip each scalar integer contribution to
[-1,1]. The query is the sum reduced modulo q=17, with no other released metadata.
Adding/removing a client means replacing one fixed slot by zero, so the circular
query displacement is at most 1. Replacing one fixed slot gives displacement at
most 2. Client participation and cohort membership are fixed public inputs; this
is not participation privacy or an arbitrary training-update sensitivity bound.

Let d(z)=min(z,q-z) for canonical residues z. Set w(z)=2^(8-d(z)), W=sum w(z)=766.
An ideal secret uniform ticket in {0,...,W-1} mapped to consecutive intervals of
length w(z) yields noise probability w(z)/W exactly. Release only (query+noise)
modulo q. Circular distance is 1-Lipschitz per unit circular step. Consequently
w(z)/w(z+t) <= 2^|t|. Every output point, and hence every event, has probability
ratio at most 2^Delta under the declared adjacency. This is pure DP with epsilon
Delta*ln(2) and delta=0 for this observer and ideal sampler. The checker enumerates
all residues and shifts, using exact fractions, rather than approximating a
continuous Gaussian or interpreting residues as unbounded integers.

With fresh independent ideal noise for each new authorized release, likelihood
ratios multiply (equivalently epsilons add). The reference accountant admits at
most two new releases and checks an explicit ratio budget. Retransmission is free
only when it sends the exact same cached release bytes under the same release ID
and noise instance; the metadata checker cannot establish that an external sender
actually obeyed this rule. Abort after potential disclosure never refunds cost.
No subsampling amplification is asserted.

The DP definition and basic composition are published external foundations:
[Dwork and Roth (2014), Definition 2.4 and Corollary 3.15](https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf).
The finite cyclic law, ticket map and bounded enumeration here are original
reference constructions, not published evidence for FZKML's deployed protocol.

Required assumptions: secret ideal uniform tickets, independence between fresh
releases, correct clipping/query implementation, fixed public membership, release
of the residue alone and exact cache identity. Actual finite-entropy sampling,
shares, proofs, logs, aborts, selection, adaptive metadata and a complete observer
view require separate analysis. Passing this checker establishes parameter
conformance to this proposition, not system DP, cryptographic security, formal
proof or independent review. The proposition itself remains pending mathematical
review. Native production sampler conformance is pending.
