# Compliance inventories

`files.json` lists every tracked public path; originals refer to LICENSE and
upstream imports include immutable source/version, preserved attribution, exact
SHA-256, changes, and applicable texts. There is no blanket wildcard that silently
licenses a new import. Add and review an explicit entry when creating a file.

`dependencies.json` lists all five direct/transitive citation-validator packages,
their exact versions, source archive hashes, accepted artifact hashes, MIT texts,
and scope. `requirements-dev.txt` locks their install artifacts with pip hashes.
No external Python package is needed by the governance validator, tests, or source
builder; no runtime package is bundled in this initial source-only distribution.
Python, Git, hosted runners and the pinned GitHub Actions are execution tools,
not distribution contents. New distribution formats require a fresh inventory of
their transitive contents. Do not describe this initial inventory as covering an
as-yet unbuilt wheel, container, binary, or proof system.

Update dependency metadata from exact upstream/PyPI releases; verify the source
hash and inspect actual license texts, notices, and transitive requirements.
Update requirements hashes and the inventory together. CI rejects drift and
uploads the diff for review. Changing `approved_licenses` is a maintainer decision
recorded in a PR, not an automated declaration of compatibility. Imported tool
license texts in `third-party/` are preserved for inspection even though the
tools themselves are not in the source archive.

The CFF schema and its CC-BY-4.0 license are copied without modification from
[Citation File Format](https://github.com/citation-file-format/citation-file-format/tree/dd51afe18fe23b4daaaf923d305e3046415b2c7c),
by the Citation File Format contributors. Attribution is retained here and in the
file map. [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) applies to those
imported files only; the project Apache-2.0 choice does not relicense them.
