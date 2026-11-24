# Synthetic fixtures and data policy, version 0.1

Status: #20; the generator and leakage-safe split helpers are implemented and
tested. They implement data-handling checks only. No training result, DP or
real-world authorization is inferred. External benchmark adoption still requires
the provenance review described in `assets/README.md` and GOV-08.

`scripts/research_fixtures.py` generates bounded integer records from a specified
public integer seed with SHA-256 domain separation. It uses no source inputs,
private samples, model downloads or uncontrolled RNG. Stable synthetic entity,
source, record, duplicate-group, event-time and label-availability metadata let
tests detect leakage. Repeated visits share an entity ID. Intentional duplicates
share an exact logical-record group and payload, while retaining distinct record
IDs. Metadata is retained even when records are excluded from a split.

The default has four sources, 12 entities per source, two visits per entity and
one extra duplicate per source. Train on entities 0–7 with event and available
label times at most 4; evaluate entities 8–11 after time 4 with labels available
by 12. Keep one canonical record per duplicate group. Return explicit excluded
record IDs/reasons for duplicate, entity and temporal rules. The resulting
training and evaluation sets share neither entities nor duplicate groups;
future visits of training entities are not independent unseen-entity evidence.
For known-entity forecasting, create a separately named/versioned split with
past-only context, no future labels, and the corresponding generalization claim.

Canonical JSON uses sorted keys, compact separators, UTF-8 and one trailing
newline. The SHA-256 representation digest is an integrity identifier, not a
hiding commitment. Even a cryptographically binding dataset commitment establishes
only consistency with the selected representation. It says nothing about truth,
consent, completeness, representativeness or the absence of earlier evaluation
contamination. Do not publish deterministic roots of real low-entropy private
datasets without a separate leakage analysis and hiding construction.

The original generator and generated default payload use Apache-2.0. Their
provenance, hash, configuration and intended permissions are in the asset
manifest. The entry is submitted for maintainer review; no benchmark terms
review is claimed. Each later public benchmark records an immutable source,
license/terms text and checksum, attribution, preprocessing and explicit download,
experiment, repository, release, model/checkpoint and generated-output decisions.
Unknown or restricted terms prohibit adoption until resolved. Public CI must
never upload real raw records, private paths, witnesses or secret randomness.
