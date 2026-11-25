# Foundation evidence and remaining acceptance work

This record covers issues #1–#8. It is engineering/governance evidence, not a
scientific experiment, legal audit, security audit, or independent review.

## Implemented artifacts

| Issue | Artifacts and validation |
| --- | --- |
| #1 | README, charter, code/spec/test/claim/experiment directories |
| #2 | Preserved Apache-2.0 LICENSE, exhaustive file map, import exceptions |
| #3 | File/dependency inventories, failing missing-license fixture, CI inventory diff, source license bundle |
| #4 | Verbatim DCO 1.1, sign-off instructions/check, missing-trailer tests, issue/PR templates |
| #5 | Consenting maintainer, governance, CODEOWNERS, conduct policy |
| #6 | Maintainer-supplied monitored private email and triage/disclosure procedure |
| #7 | Asset registry, separate usage/redistribution decisions, checksum and missing-field tests |
| #8 | Consented software author, official CFF schema validation, research-credit/release policy |

## External facts and pending controls

Verified from the GitHub connector on 2026-11-24: repository description and
Apache-2.0 license; initial commit author Guillaume Lauzier; authenticated account
`guillaumelauzier`; repository response reported admin/maintain/push permission.
The `main` branch response reported `protected: false`. No branch protection or
independent review is claimed by the presence of CODEOWNERS.

The authenticated GitHub CLI independently verified `guillaumelauzier` has the
repository `admin` role on 2026-11-24, satisfying CODEOWNERS write eligibility.
GitHub private reporting was initially disabled, was enabled through the API, and
was read back as `enabled: true`. The maintainer consented to the documented roles
and software credit and supplied guillaumelauzier@gmail.com as the monitored private
route. A benign private-report delivery/access test has not been performed. No
vulnerability or conduct report was sent.

The GitHub connector rejected mutations with HTTP 403. After the maintainer
authenticated the CLI, all eight issues were assigned to `guillaumelauzier` and
received claim comments linking this branch. The CLI was used for remote writes.

Before #5/#6 are closed: verify CODEOWNERS errors;
configure and test protected review behavior; appoint/obtain independent review
for sensitive controls; verify
private report receipt/access with maintainer participation. Record non-sensitive
outcomes here or in the reviewed issue/PR. Maintainer acceptance of policies and
review of license/terms inventory remain part of PR review.

## Reproducible validation

Local validation on 2026-11-24 passed: 41 inventoried public files, five pinned
development-only dependencies, one original synthetic governance fixture; all
16 unit tests; official CFF 1.2.0 schema validation; `pip check`; and source archive
construction. The archive test verifies exact contents and reproducible bytes.
The source builder also emits an archive SHA-256 sidecar. These results do not
substitute for the remote CI run or independent review.

Run the commands in README and inspect the CI artifact `governance-evidence`.
The archive must include LICENSE, DCO, the CFF upstream license, file/dependency
inventories, and asset terms/attribution records. Negative tests inject a missing
license entry, an unknown license, modified asset bytes, missing provenance,
restricted redistribution, and missing/mismatched DCO trailers. They must fail for
the specified reason. No federated-training/proof tests or scientific runs exist.
