# Exact released integer query v1 — #54

Define a new, explicitly named DP reference query over four fixed public slots,
two coordinates, unit public weights, public denominator N=4 and public
per-coordinate cap C=48. Inputs are signed 32-bit-domain integers; clamp each
coordinate to [-48,48] **before** summing and then compute
`Q_j=floor(sum_i clamp(x_ij)/4+1/2)`. Python integers evaluate products/sums/division
exactly: the clipped sum is in [-192,192], output in [-48,48]. A public initial
model added afterward leaves sensitivity unchanged. This query is implemented
by `FixedSlotQuery.evaluate`; the transmitted DP value is the noise-added modular
output specified in DP-MECHANISM.md, never this clean Q to the public observer.

This extends M0's rounding/shape with explicit coordinate clipping; M0's norm
admission predicate is not silently reinterpreted as a DP guarantee. Clipping
arbitrary coordinates is a new declared function. It also differs from the
three-client, weighted, round-to-even language contract: no bound transfers to
that function until its own derivation is reviewed (#26/#46/#48).

Replacement adjacency changes one fixed slot's vector. Add/remove adjacency
replaces a slot's zero contribution with one bounded vector while preserving the
same public roster, message shape and denominator. It does **not** mean a missing
M0 client: M0 aborts on a missing client and that public abort can reveal presence.
No membership/participation privacy is asserted. A record, client and person are
separate units. One-record adjacency requires preprocessing to map the record
change into the declared bounded slot change. A person touching at most m fixed
slots gets the multiplicity bound below; without an enforced multiplicity bound,
no person-level parameter is claimed.

For integers s,t, fixed positive N and `rnd(u/N)=floor(u/N+1/2)`,
`|rnd(s/N)-rnd(t/N)| <= ceil(|s-t|/N)`: the fractional parts of two shifted floors
can change their integer difference by at most the ceiling of the shift. A
changed slot changes a coordinate sum by at most C (zero-slot add/remove) or 2C
(replacement). Consequently the L1 bound for d=2 coordinates and at most m
changed slots is `d*ceil(k*C*m/N)`, k=1 or 2. Here it is exactly 24m or 48m since
48 is divisible by 4. Extremizers at +/-48 in both coordinates attain 24 and 48
for one slot; the exhaustive tests cover rounding residues and reduced domains.
An L2 bound of sqrt(2)*12m or sqrt(2)*24m also follows, but the selected mechanism
uses the L1 bound and must not calibrate to a smaller L2 number.

Private denominator counterexample: the mean of [48] is 48; adding -48 yields
mean([48,-48])=0. The change 48 exceeds the naive C/new_count=24 bound. Recomputing
normalization after private filtering cannot reuse the fixed-denominator theorem.
All counts/weights/roster/quality-selection rules in this profile are public and
fixed, with no joins, data-dependent rejection or hidden optimizer state in Q.

Any later join, deduplication, variable weights/counts, robust estimator, sparsity
selection, compression, carry state or adaptive preprocessing needs a compatible
sensitivity extension for its exact released integer function. No tests on this
reference establish that compatibility. Independent mathematical review remains
required; the manuscript's native equations are not transcribed or verified here.
