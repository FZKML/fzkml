# Research releases and evidence publication

Policy version: 1.0.0, proposed under GOV-10 (#25). No release is created here.
Only a maintainer authorized by GOVERNANCE.md may approve a release, after the
required independent domain reviews. Authors cannot approve their own
security-sensitive changes. Current research artifacts are unsupported for
production; there is no security-maintenance promise for an unreleased prototype.

Use semantic versions for software/contracts, with incompatible statement,
numeric, serialization or leakage changes requiring a new relation/protocol
version and claim-impact review. A changelog distinguishes implementation,
specification, evidence, limitation and correction changes. Do not change the
meaning of a published claim ID or relabel an earlier artifact as a stronger
guarantee. New evidence links to the exact tested version.

Every release evidence manifest must identify the source commit/tag, source
edition and protocol/relation/parameter/key digests, dependency locks/inventory,
toolchain/build environment and hardware, approved dataset/model provenance,
test and checker outcomes, raw repetitions, failures/skips/timeouts, uncertainty,
benchmark artifacts/checksums and known limitations. Not-run/unavailable and
inconclusive are distinct from success. Failed hypotheses and negative results
remain alongside successful outcomes. Include the licenses/notices applicable to
the actual package contents; the root software license does not cover imported
data/models, private manuscripts or unpublished source material.

Before publication, an identified reviewer checks the exact artifact bundle for
private records/witnesses, raw samples, secret randomness, identifiers, private
paths, restricted assets and unapproved model/generated outputs. Review the
actual digest-bound files, not only their filenames or an approval boolean.
Manuscript read access is not permission to redistribute its body, export,
images or native equations. Publish original engineering summaries and source
locators only within the authorized scope. Uncertain rights or disclosure block
publication pending resolution.

Retain source/evidence manifests and immutable public artifact digests with the
release for the lifetime of that release's published scientific claim. Hosted
CI expiration is not archival retention; copy approved evidence to the selected
release archive before treating its run as durable release evidence. Session 04
owns the actual attestation/archive/retention tooling and verification.

Corrections append a dated record identifying the old claim/artifact digest,
tested version, reason, corrected record and impact on dependent claims. Preserve
the original public record when safe. If private/restricted data was disclosed,
use the private security route, suspend distribution, revoke/remove the payload
where possible, and preserve a non-sensitive digest/tombstone plus incident and
correction references. Do not republish sensitive content merely for retention.
Record affected consumers/releases and required revalidation; do not silently
overwrite evidence or erase failed results.

Release checklist: verify source and locks; run applicable PR/integration/numeric/
genuine-proof checks; retain and verify approved evidence; validate claim/source/
status mappings; obtain independent domain and publication/provenance approvals;
inspect package license/notice contents; synchronize version/citation/changelog;
record maintainer sign-off and unsupported conditions. A mocked/skipped proof
cannot satisfy a genuine-proof gate. No CI, provenance signature or release
sign-off substitutes for the underlying protocol/privacy review or scientific
evidence.
