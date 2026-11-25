# Authoritative research contracts

Session 03 owns these specifications, `claims/`, source mappings and their
validator. Session 01 owns proof implementations, Session 02 owns independent
numerical/experiment implementations, and Session 04 owns CI and report tooling.
This directory does not replace their code or workflows.

The authoritative claim records remain `claims/registry.json`, compatible with
the shared `schemas/claims-1.0.0.json`. `claims/traceability-v1.json` adds the
required source, relation, implementation and evidence bindings without changing
that closed CI-05 schema. `claims/traceability-schema-v1.json` and
`claims/source-map-schema-v1.json` are versioned contracts, not alternate claim
statuses. `claims/schema-v1.json` references the shared claim schema locally.

`claims/source-map-v1.json` assigns permanent edition-scoped IDs to all 80
chapters, 48 exercises, indexed sections and 417 native equations. The legacy
`native-<UTF16 offset>` identifiers remain aliases. IDs are never recycled;
source revisions receive explicit source-version mappings and impact review.
An index or source inspection is not a completed extraction or a proof.

`protocol-v1.json` is the machine-readable service specification, with
`protocol-v1.md` defining its threat, transition and release semantics.
`relations/fzknum-1.0.0.json` is the normalized contract for the actual
three-client scalar computation. The manuscript/M0 two-feature relation remains
a separate specified target. Do not promote evidence across these relations.

Run the authoritative read-only checks from the repository root:

```sh
PYTHONPATH=src uv run --locked python specifications/validate.py
PYTHONPATH=src uv run --locked python -m unittest discover -s tests -p test_specification_registry.py -v
```

The validator resolves only locally registered schemas, checks content hashes,
source/claim/test references and authored evidence status, and reports unmet
external obligations. It never promotes a scientific status from a passing test
or downloads a source document. Formal evidence needs an explicit theorem,
axioms, trusted kernel and successful checker receipt; independent review needs
an identified reviewer, independence declaration, date, scope and artifact.
Metadata validation cannot establish the honesty of a receipt or reviewer.
Session 04 must run an approved checker before treating a formal receipt as
trusted execution evidence. No such formal or independent review is asserted
by the current records.

Original engineering documents and metadata use the repository software license.
The private manuscript, its export, images and equation XML remain outside the
repository and its Apache-2.0 publication scope. Obtain authorized source access
through the canonical Google Doc; no local manuscript path is assumed.
