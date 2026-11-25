# Numeric and serialization contract fzknum-1.0.0

Normative constants/formulas are in `numeric-contract-v1.json`. Its exact-byte
SHA-256 is recorded in the oracle fixture and Python profile; its first 31 bytes
are a public field-domain input constrained equal to the compiled contract digest.
Changing any semantic rule requires a new contract/header version, regenerated
independent fixtures, new circuit setup, and review. Old fixtures cannot validate
a silently edited contract. The implementation is a candidate integration contract
for #26/#28, not a claim that their research acceptance criteria have been met.

## Exact operation and conversion boundary

The roster has exactly three ordered clients, one feature, one synthetic sample per
client, one common initial weight, no bias, one gradient update and one aggregate.
Count weights are declared public aggregation weights in 1..4; they are not a claim
that different local sample counts were actually trained. All inputs are public in
this first scenario. No data privacy, participation, commitment binding, or state
acceptance claim is made by the arithmetic proof.

Integers represent reals at scale 16. Inputs `w,x_i,y_i` are in [-32,32]. For
`RNE(n/d)`, d must be positive. Use mathematical Euclidean division `n=d*q+r`,
`0<=r<d`, including negative n: increment q if `2r>d`, or if `2r=d` and q is odd.
For example RNE(-6/4)=-2, RNE(-2/4)=0, RNE(6/4)=2. There is no truncation-toward-zero
shortcut, clipping, saturation, approximate equality, or implicit modular reduction.

For each client compute prediction, gradient and local update from the JSON
formulas in that order, rounding at **each declared division**. Aggregate local
updated weights with the declared counts and one final RNE. Do not move rounding
across multiplication, addition, client aggregation, or the learning-rate boundary.
No empty roster, zero/negative denominator or unsupported dimension is accepted.

PyTorch execution is exploratory CPU float64. Export the exact binary float value
through `float.as_integer_ratio`/`Fraction.from_float`, multiply that rational by 16,
and RNE once. Require finite real inputs in [-2,2] before quantization. NaN, either
infinity, out-of-range values, complex/integer dtypes, GPU, extra tensor dimensions,
unsupported operators and optimizer configurations fail explicitly. Quantization
error and float-vs-integer training error are measurements separate from proof
validity. Only the declared integer computation is checked by the proof.

## Wire format

Exactly 84 bytes, contiguous row-major client order; no padding/trailing bytes:

| Offset | Type | Meaning |
| --- | --- | --- |
| 0 | 8 ASCII bytes | `FZKNUM01` contract/header version |
| 8 | u16 little-endian | features, exactly 1 |
| 10 | u16 little-endian | clients, exactly 3 |
| 12 | u32 little-endian | scale, exactly 16 |
| 16 | i64 little-endian two's complement | common weight |
| 24+20i | i64 little-endian | x_i |
| 32+20i | i64 little-endian | y_i |
| 40+20i | u32 little-endian | aggregation count_i |

The decoder validates length/header before slicing or copying data. Reject out-of-
range signed values, counts outside 1..4, other shapes/order/scale and alternate
encodings. Signed-to-field embedding is z for nonnegative z, p-|z| otherwise;
no field bytes are accepted as an alternate signed wire encoding. Public proof
inputs are domain, w, interleaved (x_i,y_i,count_i), then output. Compressed proof
decoding is exact-length (128 bytes), canonical and subgroup-checked by arkworks.

## Range ledger and no-wrap argument

| Quantity | Sufficient integer bounds |
| --- | --- |
| w,x,y | [-32,32] |
| w*x | [-1024,1024] |
| prediction | [-64,64] |
| residual prediction-y | [-96,96] |
| residual*x | [-3072,3072] |
| gradient | [-192,192] |
| rounded gradient/4 | [-48,48] |
| local updated weight | [-80,80] |
| count*updated weight | [-320,320] |
| sum numerator, sum counts | [-960,960], [3,12] |
| aggregate | [-80,80] |
| rounding gadget floor q | [-1024,1024] |
| r, d-1-r | [0,d-1], d<=16 |
| 2r-d, comparison gap | [-16,14], [0,15] |

Rust uses i128 intermediates and fallible conversions; these permitted products and
sums are far below its bounds in debug and release. The circuit constrains every
public scalar range, each intermediate range, quotient/remainder, one-hot comparison
branch, quotient parity, and output. A bound is enforced by Boolean decompositions
of both v-low and high-v. At most 12 bits are needed for any such decomposition.
The largest quotient product is at most 16*1024; all constrained equality-side
differences have absolute value below 2^17, strictly smaller than p. Therefore an
accepted field equality for these bounded witnesses is an integer equality; a
nonzero difference cannot be a multiple of p. Domain equality is a separate fixed
constant, below 2^248. These are arithmetic no-wrap conditions, independent of the
cryptographic security parameter; they are not a cryptographic soundness proof.

## Hand-checkable golden case

w=8, x=[16,-8,24], y=[16,-16,8], counts=[1,2,1] gives predictions [8,-4,12],
gradients [-8,-6,6], updated weights [10,10,6], numerator 36, denominator 4 and
aggregate 9. Golden/random vectors are generated by Python's independent arbitrary-
precision Fraction oracle, without Rust bindings or circuit calls. The same public
fixture is consumed by debug/release CLI conformance and installed-wheel tests.
