# FZKML — Federated Zero-Knowledge Machine Learning

`FZKML/fzkml` is the flagship research monorepo for studying verifiable
federated learning: protocol specifications, original reference implementations,
test vectors, claim records, and reproducible experiments belong together here.
Intended users are protocol researchers, implementers, and independent reviewers.

**Maturity: project foundation.** This branch implements governance and provenance
checks, a DCO check, and a source-distribution builder. No federated training,
zero-knowledge proof system, or security guarantee is implemented or demonstrated.
The research prototype is not production-ready or externally audited.

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

Python 3.9+ and Git are required for the standard-library checks:
Stage new public files before validation; licensing coverage is checked against
the Git index, matching the files a PR will contain.

```sh
python3 scripts/check_governance.py
python3 -m unittest discover -s tests -v
python3 scripts/build_source.py
```

For full citation schema validation, install the pinned development requirements
in a virtual environment and run `python3 scripts/check_citation.py`. CI runs all
these checks, checks DCO trailers on the PR commit range, and uploads inventories,
their diff, and the source archive. No scientific experiment is implied by CI.

Original code and engineering documentation use Apache-2.0, subject to the
path-specific exceptions in [LICENSE-MAP.md](LICENSE-MAP.md). The private book is
outside this repository's publication and licensing scope.
