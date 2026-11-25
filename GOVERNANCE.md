# Governance and review

## Authority and decisions

Consenting maintainers are recorded in MAINTAINERS.md. Routine changes need a
maintainer review, passing applicable checks, and documented validation. Authors
do not approve their own security-sensitive changes. Release authority belongs
to a listed maintainer after the release checklist and required reviews pass.

Protocol, cryptography, privacy, learning-validity, provenance-policy, or review
control changes need a public design issue stating the alternatives, assumptions,
affected claims, validation plan, and decision rationale. A qualified reviewer
independent of the author must approve security-sensitive changes. Cross-domain
changes need evidence of review for each affected domain. No such independent
reviewer is currently appointed; these changes wait rather than bypass review.

For contested protocol decisions, record objections and seek an independent domain
review. The maintainer records the resolution and dissent with a rationale; absent
adequate review or consensus on security assumptions, keep existing behavior and
defer the change. Conduct matters use the private route in CODE_OF_CONDUCT.md.

Maintainers join only with explicit consent, demonstrated contribution/review
capacity, a recorded appointment decision, and verified repository permissions.
Departures and succession require a recorded handover of review/release/security
responsibilities, contact routes, and access. If the sole maintainer is unavailable,
releases pause; contributors may propose a successor or maintain a clearly labeled
fork, but cannot claim existing authority without an authorized transfer.

## Review configuration

Once present on the default branch, `.github/CODEOWNERS` routes owner review for protocol,
cryptography, learning, claims, provenance, and CI paths, including CODEOWNERS itself.
GitHub uses the last matching pattern. Multiple owners on one line allow **any one**
of them to satisfy a code-owner approval; they do not require every listed owner.
The independent/domain review requirement above is a separate review rule.

Before merging this foundation, configure protection or a ruleset for `main`:
require PRs, one approving review, code-owner review, stale approval dismissal,
resolved conversations, and `governance` plus `dco` status checks. Restrict bypass
and direct pushes, including administrators where available. Changes to CODEOWNERS,
workflow files, governance policy, and validators require independent review.
Do not mark the control active merely because the files exist.

`docs/FOUNDATION-EVIDENCE.md` records actual configuration verification and gaps.
Test ownership through a PR touching a protected path, inspect requested
reviewers and CODEOWNERS errors, and confirm a missing review/check prevents merge.
Repeat after owner, access, ruleset, or workflow changes. A local syntax check
cannot establish GitHub access or protected-branch behavior.

## Releases

A release sign-off records the exact commit/tag, actual passing checks, claim
status, known limitations, provenance/terms review, archive contents, contact
readiness, independent approvals, and citation version/date. Do not release while
mandatory review or reporting-channel verification remains pending. Announce
scientific results only to the extent supported by linked evidence.
