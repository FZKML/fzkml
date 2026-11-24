# Security policy

## Supported versions

No version has been released. Only the current default-branch research foundation
is maintained on a best-effort basis. Future research implementations will not be
production-ready or externally audited by default; no security support SLA applies.

## Private reporting

Report vulnerabilities privately to **guillaumelauzier@gmail.com**, monitored by
founding maintainer Guillaume Lauzier. Describe the affected commit, reproduction,
impact, and assumptions. Email is not an end-to-end encrypted channel; do not send
credentials or private datasets. Request a suitable transfer arrangement for
sensitive reproduction inputs. Do not open a public issue containing vulnerability
details, exploit inputs, or affected users' data.

GitHub's [private report form](https://github.com/FZKML/fzkml/security/advisories/new)
is enabled as an additional route (verified through GitHub's API on 2026-11-24).
Maintainer receipt/access testing is still pending, as recorded in
docs/FOUNDATION-EVIDENCE.md; enabling the setting alone does not prove delivery.

## Handling and disclosure

Guillaume owns acknowledgement, private triage, remediation coordination, and
advisory publication. Responses are best effort, with no invented turnaround
promise. If acknowledgement is delayed, follow up through the same private route.

1. Acknowledge receipt privately and agree on a communication channel.
2. Reproduce using minimal inputs, restrict access, assess affected versions,
   assumptions, severity, and related claims; obtain independent review as needed.
3. Coordinate a fix and regression test in a private advisory/fork when available.
   Avoid exposing the report through public CI logs, branches, fixtures, or PRs.
4. Agree on disclosure timing and reporter credit, document disagreements, and
   coordinate with affected upstreams. Do not promise indefinite secrecy or a
   fixed deadline the project cannot staff.
5. Publish remediation, affected versions/commits, limitations, and an advisory
   when coordinated disclosure is appropriate; update claim/evidence records.

Before declaring reporting operational, verify private report submission, maintainer
receipt/access, and private coordination with a benign test and record only its
non-sensitive outcome. No test report has been sent by this implementation.
