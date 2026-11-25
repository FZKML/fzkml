# Dataset, model, checkpoint, and generated-output provenance

No external dataset, pretrained model, checkpoint, or benchmark input is adopted.
`manifest.json` inventories original public synthetic governance, exact arithmetic,
and private-transcript fixtures. None is a scientific dataset or training result.

Before adopting an asset, record its source URL, immutable version, local public
path (if redistribution is approved), SHA-256, exact terms/license, attribution,
intended use, and separate decisions for download, experimentation, repository,
release, and generated-output redistribution. For synthetic data record method,
seed/configuration, and every source input or explicitly none. Model/checkpoint
and generated-output rights require separate decisions; code licensing is not
sufficient. Use the existing entry as the manifest field example.

The maintainer records a terms/provenance review, reviewer, date, and rationale
before benchmark use. A changed version, source, terms, method, or intended use
requires a new review; unresolved rights block adoption. Approved payloads belong
in `assets/public/`, `tests/fixtures/`, `datasets/`, `models/`, or `checkpoints/` and
must all be registered. CI checks metadata and actual file hashes without fetching
remote data. Restricted assets stay outside Git, public logs/reports, and releases.
Do not place private data elsewhere to evade these reserved-path checks: reviewers
must inspect all additions because metadata checks cannot recognize private content.

Public reports contain aggregate approved results and public metadata only. Inspect
outputs for private samples, paths, identifiers, and restricted model/data content
before uploading. Generated artifacts are reviewed individually before release.
