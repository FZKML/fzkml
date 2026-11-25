# Project charter

## Identity and scope

The repository is `FZKML/fzkml`; its display title is **FZKML — Federated
Zero-Knowledge Machine Learning**. It is a research and implementation workspace
for researchers, implementers, and reviewers investigating what a verifier can
establish about a federated learning computation, under stated assumptions.

The initial scientific target is a deterministic local simulation of one training
round on original synthetic fixtures. A later verification relation must identify
public inputs, private witnesses, numeric representation, trust assumptions,
failure cases, and the precise computation verified. Networking, deployment,
production training, and claims of differential privacy or malicious-client
robustness are outside the initial implementation scope.

Currently implemented: governance/CI tooling and a candidate tiny public-input
exact linear round with independent vectors, a local arkworks research proof,
Python bindings and a CPU float comparison. See docs/LANGUAGE-IMPLEMENTATION.md.
Planned: a complete federated security protocol and broader scientific experiments.
Untested: training-data privacy, reviewed cryptographic soundness, scalability,
robustness and learning utility. There is no production readiness or external audit claim.

## Claims and evidence

Every scientific or security assertion gets a stable claim ID in `claims/` before
being advertised as established. Its record states the hypothesis, assumptions,
scope, current status (untested/supported/refuted/inconclusive), specification
version, implementation commit, experiment configuration, seeds, environment,
input provenance IDs, commands, artifact checksums, results, failures, limitations,
and reviewer. Evidence must be immutable or archived with a content hash.

An implementation issue closing means its acceptance criteria were reviewed; it
does not prove the related hypothesis. Negative results and refutations remain
in the record. CI validates engineering properties only within its test scope.
Versioned releases link exact commits to claim records and evidence manifests;
changing assumptions or implementations requires assessing which claims still hold.

## Repository boundaries

Keep code, specifications, vectors, claims, experiments, and docs in this monorepo
while they evolve together. Split a package only after an explicit governance
decision records a stable interface, independent release cadence or maintainership,
provenance migration, compatibility policy, and continuing claim/evidence links.
No package split is needed to begin research. The private manuscript is not an
input to public distributions; publishing it needs a separate rights decision.
