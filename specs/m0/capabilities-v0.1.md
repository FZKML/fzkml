# Model and assurance capability types, version 0.1

Status: #21 specification. The complete family-by-mode matrix is
`experiments/m0/capabilities.json`; every cell is explicitly `planned`,
`unsupported` or `excluded`. No assurance mode is implemented by M0.

Full-training proofs cover every declared local transition in their specified
domain. Update-property proofs check the named predicate only. Endpoint
certificates certify a specified objective/residual condition and do not certify
the optimization trajectory. Inference proofs bind a declared forward
computation. Attestation has a hardware/vendor/software trust boundary.
Certified-history proofs additionally require connected complete state and a
composition theorem. None of these implies the others or aggregate privacy.

The experiment manifest must choose a matrix cell, exact relation/version,
observer, guarantee, accepted roster, numerical semantics, feature schema,
model architecture/version, initialization digest, optimizer state and update
type. `full-state` encodes the complete resulting local state. `delta` encodes a
difference from the explicitly bound initialization; never treat a full adapter
as a delta or average deltas with inconsistent bases. Padding, missing components,
per-component denominators and eligibility rules require their own typed policy.

For every family, name preprocessing, feature extraction, optimization,
randomness and lineage steps that the selected relation leaves unproved. These
are populated in the matrix. Tokenization/retrieval, teacher provenance,
preference collection, augmentations, entity correspondence, time windows,
diffusion sampling and simulator-to-environment transfer are substantive steps.
No general foundation-model or private-data utility claim follows from the
two-feature regression relation. A manifest selecting an unsupported or excluded
cell must produce `unsupported` without benchmark measurements. Changing cell,
trust boundary or update semantics changes the run identity.
