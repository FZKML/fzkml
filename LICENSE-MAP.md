# License scope and provenance

The existing, unmodified [LICENSE](LICENSE) is Apache License 2.0. Original
implementation code, tests, configuration, and newly authored engineering
documentation are contributed under Apache-2.0. This does not establish ownership
by FZKML of every contribution; contributors retain their respective rights.

`compliance/files.json` is the exhaustive path-based license map. Every tracked
file must have an entry: SPDX license expression, origin, attribution, upstream
source/version for imports, modification record, and required license/notice paths.
Adding an unlisted file fails CI. `LICENSE` itself is the preserved license text.

| Artifact | Treatment |
| --- | --- |
| Original repository files | Apache-2.0, inventoried individually |
| `DCO` | Verbatim upstream DCO 1.1; `LicenseRef-DCO-1.1` |
| `compliance/cff-schema.json` | Pinned upstream CFF schema; CC-BY-4.0 |
| Third-party notices/texts | Their original terms, never relicensed by the root license |
| Downloaded datasets, models, checkpoints | Separate asset terms; not inferred from code licensing |
| Private manuscript and private/restricted inputs | Excluded; no publication or relicensing authorization |

No imported ASF implementation or ASF NOTICE is present. Do not invent an ASF
affiliation or a copyright holder. Add a top-level NOTICE only when applicable
attribution requirements warrant it. Upstream materials retain their license
texts, notices, and attribution. Modified imported files must prominently identify
changes as well as recording them in the manifest.

The source builder includes all inventoried source files and their required texts.
Development tools are inventoried in `compliance/dependencies.json` and the
uv/Rust integration `compliance/ci-dependencies.json`;
they are not bundled into the source distribution. A future wheel, container,
binary, or model distribution requires an inventory of its actual transitive
contents and applicable licenses/notices before that format is released.

## Review procedure

For every new dependency or import, record the exact version/immutable source,
checksum, SPDX identifier (or documented LicenseRef), attribution, notices,
modifications, and distribution scope. Inspect direct and transitive dependencies.
Review changes to both inventories in the uploaded CI diff. New, missing, unknown,
or changed terms require maintainer review before adoption. Uncertain rights or
compatibility remain unresolved until a documented decision, with qualified advice
when appropriate. Automated checks establish metadata coverage and byte integrity;
they are not a rights audit or an automatic compatibility decision.

Authoritative texts: [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)
and [DCO 1.1](https://developercertificate.org/).
