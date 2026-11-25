# ADR-001: Rust relation, Python research, one local CPU Groth16 baseline

Status: implemented research baseline, proposed for architecture/independent review.
Scope: #9, #27, #29, #30, #31; depends on the separate CI foundation #10/#15.

Rust owns validated protocol types, canonical decoding, exact integer arithmetic,
field embedding, range-constrained R1CS construction, local setup/proving and
verification. Python owns experiments, independent exact reference mathematics,
float64 ML comparison, preprocessing and tensor export. The PyO3 boundary is one
bounded immutable byte batch per operation; it does not reimplement verification.
No property follows merely from choosing Rust: memory safety does not establish
constant-time behavior, correct constraints, soundness, privacy or protocol security.

Select arkworks `ark-groth16=0.5.0` with BN254 on CPU for the first exact tiny linear
relation in `specs/numeric-contract-v1.json`. `Cargo.lock` pins all transitives; two
enum helper crates are locked to 4.3.0 for the existing Rust 1.85.1 toolchain.
The upstream [Groth16 project](https://github.com/arkworks-rs/groth16) explicitly
describes its implementation as an academic prototype without careful review and
not ready for production. MIT/Apache licensing alternatives and all resolved crate
licenses/notices are inventoried. No independently reviewed security strength,
constant-time implementation or setup ceremony is asserted here.

Each `ResearchSession` creates a fresh circuit-specific local randomized setup
using OS randomness, owns its immutable proving/prepared-verifying keys, and reports
the SHA-256 of its serialized verifying key. Setup trapdoor handling is not a
production ceremony; the process sees setup randomness. Proof randomness also uses
OS entropy, never fixture seeds. Keys are not imported from arbitrary callers or
persisted as production parameters. A result from another session is rejected.
There is no network state-acceptance service. A future service must pin a reviewed
relation and trusted setup/key digest rather than accept a caller-chosen key.

All tiny-scenario data and the aggregate are public. The proof checks only the
declared integer computation. It does not establish that data came from a client,
that clients used the claimed optimizer on real samples, or that a private training
procedure matches floats. The PyTorch comparison records quality errors separately.
The exact oracle is outside the binding package and imports neither Rust nor torch.

The first slice is sufficient with one Rust CLI/backend and one Python client:
build the wheel, run the synthetic smoke and independent conformance suites, then
run the CPU profile. TypeScript UI, custom C++/CUDA kernels, extra proof engines
and DSLs are outside this initial required scope. No accelerator is proposed on
the basis of this tiny profile.

A future zkVM/Noir/Circom adapter must consume the same canonical bytes and exact
relation version, preserve public-input semantics and range/rounding behavior,
and pass the independent fixture/mutation suite. A different meaning requires a
new contract version, not a tolerance adjustment. Cross-backend equivalence and
research dependencies #26/#28 still require their own review and evidence.

API references: [arkworks Groth16](https://docs.rs/ark-groth16/0.5.0/ark_groth16/struct.Groth16.html),
[PyO3 0.23.5 threading](https://pyo3.rs/v0.23.5/parallelism), and
[maturin mixed layout](https://www.maturin.rs/project_layout.html).
