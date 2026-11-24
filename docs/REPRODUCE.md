# Clean environment reproduction and retention

Start on a clean Ubuntu 24.04 runner with Git, CPython 3.11.14, Rust 1.85.1 and
the reviewed source commit. The hosted image is mutable: record ImageOS and
ImageVersion, CPU/memory and OS in each run. Toolchains are version pinned;
Python packages and uv use lockfiles with artifact hashes, Rust uses Cargo.lock.
No immutable container image is claimed. Setup uses the same reviewed action SHAs
and bootstrap as `.github/workflows/cpu.yml`.

Run `./scripts/reproduce --contract-only` for an isolated archive export, new
virtual environments and hash-locked package install. It regenerates and verifies
CI-04 semantic summaries/reports using the synthetic reference fixture. This is
metadata pipeline reproduction only. Run `./scripts/reproduce --full` for the
reference proof gate; missing backend/authorized input returns UNREPRODUCIBLE
and a nonzero exit. Currently full reproduction is unavailable. Large datasets
and weights stay outside git. No third-party model or dataset is required by the
contract fixture. Later external inputs need version, digest, retrieval URL,
license/authorization and preprocessing instructions in the shared result plus
asset registry before use. Missing/changed inputs must fail, not fall back.

Compare declared accepted outputs, relation identities, numerical tolerances and
repeated measurement distributions. Randomized proof bytes need not match. The
artifact verifier checks byte integrity for the bundle that was actually published;
that does not impose byte-identical proofs on a new reproduction.

Tagged evidence is published only from protected version tags whose commit is an
ancestor of the protected default branch, after `release-evidence` environment
approval, actual validation and real proof success. The bundle includes a Rust
library, source archive, schema-valid results, transitive SPDX inventory,
reproduction instructions and a digest manifest. It records experimental limits.
Routine PR artifacts are never all attested or promoted to a release.

Independently obtain the expected SHA and version tag from a reviewed release:

```sh
gh release download vX.Y.Z --repo FZKML/fzkml --dir release-bundle
./scripts/release-evidence verify release-bundle --tag vX.Y.Z --commit EXPECTED_40_HEX_SHA
```

The command constrains GitHub repository, signer workflow, source SHA/ref and hosted
runner identity using `gh attestation verify`, then checks inventory digests and
result provenance. It verifies the manifest and library attestations separately.
Failure to retrieve attestations is failure; a local digest-only check cannot label
the release verified. See the [GitHub verifier manual](https://cli.github.com/manual/gh_attestation_verify).

Keep tagged release evidence indefinitely at the manifest's release URL. Mirror
the exact bundle and attestations before deleting/moving assets; record replacement
location/digests in the release and never silently replace a version. Retention is
a maintainer obligation, not a GitHub availability guarantee. Short-lived research
diagnostics use 7 days, reconciliation 14 days. No tagged release or independent
external attestation verification has occurred as part of this implementation.
