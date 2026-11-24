# FZKML — Federated Zero-Knowledge Machine Learning

`FZKML/fzkml` is the flagship research monorepo for studying verifiable
federated learning: protocol specifications, original reference implementations,
test vectors, claim records, and reproducible experiments belong together here.
Intended users are protocol researchers, implementers, and independent reviewers.

**Maturity: research prototype.** In addition to governance and CI tooling, this
branch implements a tiny exact three-client linear update, independent Python/Rust
conformance, an arkworks Groth16 local research proof, PyO3 bindings and a CPU
PyTorch comparison. All scenario inputs are public. No production security or
training-data privacy guarantee is established; the prototype is not externally audited.

The first implemented numeric workflow is a local deterministic round on three
original synthetic clients under the [exact contract](specs/NUMERIC-CONTRACT.md).
See [architecture](docs/ADR-001-RUST-PYTHON.md) and
[reproduction/API/evidence](docs/LANGUAGE-IMPLEMENTATION.md). Privacy, scalability,
robustness and convergence remain untested hypotheses.

Start with [the charter](docs/CHARTER.md), [contributing](CONTRIBUTING.md),
[governance](GOVERNANCE.md), [security reporting](SECURITY.md), and
[licensing](LICENSE-MAP.md). Cite the software using [CITATION.cff](CITATION.cff);
see [the credit policy](docs/CREDIT.md).

## Layout

| Path | Purpose |
| --- | --- |
| `src/` | Future original reference implementations |
| `specs/` | Versioned protocol and verification relations |
| `tests/` | Governance checks and future protocol vectors |
| `claims/` | Explicit claims and their evidence links |
| `experiments/` | Reproduction definitions and evidence conventions |
| `assets/` | Public asset provenance manifest |
| `compliance/` | File-license and dependency inventories |
| `scripts/` | Validation and source-distribution tools |
| `docs/` | Charter, policies, and review evidence |

## Local validation

Use the locked CPU setup and command below. Stage new public files before running
validation: licensing coverage uses the Git index, matching the files a PR contains.
CI also checks DCO trailers on the PR commit range. Governance/source validation
runs without uploading broad source archives or arbitrary inventory diffs.

Original code and engineering documentation use Apache-2.0, subject to the
path-specific exceptions in [LICENSE-MAP.md](LICENSE-MAP.md). The private book is
outside this repository's publication and licensing scope.

## CPU validation and public reports

Research infrastructure for scoped, reproducible claims. This repository currently
contains a CPU development scaffold and public reporting validators. It contains
no implemented proof backend and no measured scientific result.

Install [rustup](https://rustup.rs/) and Python 3.11.14. From a clean Linux checkout:

```sh
python3.11 -m pip install --require-hashes -r tools-requirements.txt
rustup toolchain install 1.85.1 --profile minimal --component rustfmt --component clippy
uv sync --locked
./scripts/validate
./scripts/build-public-report
```

`./scripts/validate` is the single CPU validation command after installation. It
checks exact tool versions, committed locks, Rust formatting/Clippy/tests, Python
formatting/lint/strict types, adversarial validator tests and workflow policy.
It requires neither GPU, cloud credentials nor paid services. Installation needs
network access to the reviewed package registries; validation uses installed tools.
`dist/` must not exist before building a report: move or remove your previous
generated report explicitly before rebuilding.

The Rust workspace reserves protocol ownership; Python owns reporting and
experiments. LANG-01 (#9) still owns the proof-backend decision. No language choice
provides a constant-time or cryptographic-security guarantee.

Reports are in `dist/report.md`, `dist/report.html`, `dist/plots.svg`, and
`dist/summary.json`; `results.json` and `claims.json` retain their exact inputs.
The checked-in v0.1 scaffold lists tiny proof, native/circuit conformance, negative
cases, costs and later research as **not-run**. Zero digests and workflow run 0 are
explicit placeholders in these unexecuted fixtures, never real provenance.

See [record contracts](docs/records.md), [workflow and publication policy](docs/security.md)
and [implementation evidence and remaining work](docs/implementation.md).

## Scientific specification integration

# FZKML — Federated Zero-Knowledge Machine Learning

`FZKML/fzkml` is the flagship research monorepo for studying verifiable
federated learning: protocol specifications, original reference implementations,
test vectors, claim records, and reproducible experiments belong together here.
Intended users are protocol researchers, implementers, and independent reviewers.

**Maturity: project foundation.** This branch implements governance and provenance
checks, a DCO check, and a source-distribution builder. No federated training,
zero-knowledge proof system, or security guarantee is implemented or demonstrated.
The research prototype is not production-ready or externally audited.

The [M0 research registry](docs/research/README.md) records 80 chapter and 48
exercise work mappings, selected manuscript prose claims, versioned deployment
and measurement specifications, and explicit source-review gaps. Deterministic
synthetic fixture generation and split checks are implemented. Training, proofs,
protected aggregation and scientific benchmarking remain planned and untested.

The first planned scientific workflow is a local, deterministic simulation of one
federated learning round on synthetic inputs, followed by an explicitly specified
verification relation and positive/negative test vectors. Privacy, proof cost,
robustness, and convergence remain untested hypotheses until recorded evidence
supports a precisely scoped claim.

Start with [the charter](docs/CHARTER.md), [contributing](CONTRIBUTING.md),
[governance](GOVERNANCE.md), [security reporting](SECURITY.md), and
[licensing](LICENSE-MAP.md). Cite the software using [CITATION.cff](CITATION.cff);
see [the credit policy](docs/CREDIT.md).

## Layout

| Path | Purpose |
| --- | --- |
| `src/` | Future original reference implementations |
| `specs/` | Versioned protocol and verification relations |
| `tests/` | Governance checks and future protocol vectors |
| `claims/` | Explicit claims and their evidence links |
| `experiments/` | Reproduction definitions and evidence conventions |
| `assets/` | Public asset provenance manifest |
| `compliance/` | File-license and dependency inventories |
| `scripts/` | Validation and source-distribution tools |
| `docs/` | Charter, policies, and review evidence |

## Local validation

Use the locked CPU setup and command below. Stage new public files before running
validation: licensing coverage uses the Git index, matching the files a PR contains.
CI also checks DCO trailers on the PR commit range. Governance/source validation
runs without uploading broad source archives or arbitrary inventory diffs.

Original code and engineering documentation use Apache-2.0, subject to the
path-specific exceptions in [LICENSE-MAP.md](LICENSE-MAP.md). The private book is
outside this repository's publication and licensing scope.

## CPU validation and public reports

Research infrastructure for scoped, reproducible claims. This repository currently
contains a CPU development scaffold and public reporting validators. It contains
no implemented proof backend and no measured scientific result.

Install [rustup](https://rustup.rs/) and Python 3.11.14. From a clean Linux checkout:

```sh
python3.11 -m pip install --require-hashes -r tools-requirements.txt
rustup toolchain install 1.85.1 --profile minimal --component rustfmt --component clippy
uv sync --locked
./scripts/validate
./scripts/build-public-report
```

`./scripts/validate` is the single CPU validation command after installation. It
checks exact tool versions, committed locks, Rust formatting/Clippy/tests, Python
formatting/lint/strict types, adversarial validator tests and workflow policy.
It requires neither GPU, cloud credentials nor paid services. Installation needs
network access to the reviewed package registries; validation uses installed tools.
`dist/` must not exist before building a report: move or remove your previous
generated report explicitly before rebuilding.

The Rust workspace reserves protocol ownership; Python owns reporting and
experiments. LANG-01 (#9) still owns the proof-backend decision. No language choice
provides a constant-time or cryptographic-security guarantee.

Reports are in `dist/report.md`, `dist/report.html`, `dist/plots.svg`, and
`dist/summary.json`; `results.json` and `claims.json` retain their exact inputs.
The checked-in v0.1 scaffold lists tiny proof, native/circuit conformance, negative
cases, costs and later research as **not-run**. Zero digests and workflow run 0 are
explicit placeholders in these unexecuted fixtures, never real provenance.

See [record contracts](docs/records.md), [workflow and publication policy](docs/security.md)
and [implementation evidence and remaining work](docs/implementation.md).
