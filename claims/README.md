# Claim records

`registry.json` is the CI-05-compatible claim registry. Exact manuscript locations,
source/version metadata, observer/privacy/numeric context and required validation
are in [docs/research](../docs/research/README.md). The generated coverage report
distinguishes work mapping, partial extraction and evidence strength.

No scientific or security claim is established. Use the record fields defined in
docs/CHARTER.md. Governance and metadata test results do not establish protocol
security. No manuscript body is licensed or distributed through this registry.

The S03 authoritative overlays are [traceability-v1.json](traceability-v1.json),
[source-map-v1.json](source-map-v1.json) and [editions-v1.json](editions-v1.json).
They preserve the shared claim schema and add exact source IDs, content hashes,
relation/implementation bindings and evidence attestations. See
[session interfaces](../specifications/session-handoffs-v1.md) and run
`PYTHONPATH=src uv run --locked python specifications/validate.py`.

Five scoped analytic/synthetic references have named passing test evidence;
these do not establish a complete training, cryptographic, DP or adoption claim.
Formal proof and independent review remain separate, currently empty categories.

[candidate-evidence-v1.json](candidate-evidence-v1.json) records immutable external
numerical evidence awaiting contribution/adoption gates. It is schema checked
and source mapped, but is separate from adopted claim evidence. Hosted CPU and
language test scopes, local skips and pending certification remain explicit.
A candidate record never promotes a claim or native-equation review status.
