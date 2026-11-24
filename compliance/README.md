# Compliance inventories

`files.json` lists every tracked public path; originals refer to LICENSE and
upstream imports include immutable source/version, preserved attribution, exact
SHA-256, changes, and applicable texts. There is no blanket wildcard that silently
licenses a new import. Add and review an explicit entry when creating a file.

`dependencies.json` lists all five direct/transitive citation-validator packages,
their exact versions, source archive hashes, accepted artifact hashes, MIT texts,
and scope. `requirements-dev.txt` locks their install artifacts with pip hashes.
The CPU CI foundation adds `ci-dependencies.json` for the exact uv lock and
hash-pinned uv bootstrap. Its pristine license texts are in `third-party/ci-*`.
The combined CPU command uses `uv.lock`; the older `requirements-dev.txt` remains
the independent citation-validator lock from the governance foundation and is
still checked against its original inventory. No installed tool package is bundled
in the source-only archive. The CI integration validates new Python manifests,
all uv artifact hashes and notice digests; Rust currently has no external crates.
Python, Git, hosted runners and the pinned GitHub Actions are execution tools,
not distribution contents. New distribution formats require a fresh inventory of
their transitive contents. Do not describe this initial inventory as covering an
as-yet unbuilt wheel, container, binary, or proof system.

Update dependency metadata from exact upstream/PyPI releases; verify the source
hash and inspect actual license texts, notices, and transitive requirements.
Update requirements hashes and the inventory together. CI rejects drift and
checks the diff in the PR for review. Changing `approved_licenses` is a maintainer decision
recorded in a PR, not an automated declaration of compatibility. Imported tool
license texts in `third-party/` are preserved for inspection even though the
tools themselves are not in the source archive.

This PR proposes MIT/Apache-2.0 development tools plus MPL-2.0 pathspec and
PSF-2.0 typing extensions. Only their verbatim license texts and provenance are
copied; the tools are installed during development, not redistributed here.
The new approved-license entries and package adoption require maintainer review
with this PR. Byte checks establish metadata integrity, not legal clearance.

The CFF schema and its CC-BY-4.0 license are copied without modification from
[Citation File Format](https://github.com/citation-file-format/citation-file-format/tree/dd51afe18fe23b4daaaf923d305e3046415b2c7c),
by the Citation File Format contributors. Attribution is retained here and in the
file map. [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) applies to those
imported files only; the project Apache-2.0 choice does not relicense them.
