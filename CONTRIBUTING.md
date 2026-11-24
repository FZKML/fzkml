# Contributing

Open an issue describing the problem, affected claim IDs, and intended validation.
Claim an unassigned issue with an assignee and a coordination comment naming the
branch and scope; check existing claims before starting. Submit focused PRs using
the template. Review follows [GOVERNANCE.md](GOVERNANCE.md).

Submit original code and engineering documentation under the applicable
[path license](LICENSE-MAP.md), normally Apache-2.0. Identify all copied, adapted,
generated, dataset, and model materials, with sources, terms, notices, and changes.
Do not submit private manuscript content or restricted inputs. Confirm that you
have authority to contribute, including relevant employer/institutional permission.
Do not assume a GitHub account or project membership establishes ownership.

## Developer Certificate of Origin 1.1

Read the verbatim [DCO](DCO) before certifying your contribution. Add a sign-off
using your own name and an email address you may publish:

```sh
git config user.name 'Your Name'
git config user.email 'your-public-email@example.org'
git commit -s
```

A GitHub-provided noreply address is acceptable. Contribution history, names,
emails, and sign-offs are public, maintained indefinitely, and may be redistributed.
Never add another person's certification without their authorization.

A `Signed-off-by: Name <email>` trailer certifies the DCO; it is not copyright
assignment, a cryptographic signature (`git commit -S` is separate), or automatic
legal verification. CI requires a matching trailer for each commit author and
each `Co-authored-by` identity. Do not sign off another author's work for them.

For an unpublished latest commit, read the DCO then use:

```sh
git commit --amend --no-edit --signoff
```

For earlier commits on your own PR branch, coordinate with collaborators, use
`git rebase -i <base>` and amend each affected commit, then push with
`git push --force-with-lease`. History rewriting changes commit IDs and signatures.
Ask maintainers for help when rewriting shared history is inappropriate. The
initial upstream commit predates this policy; the check covers new PR commits.

PRs must link validation commands and actual artifacts, failures and untested
conditions, affected specifications/claims, and license/provenance impact. Adding
assets requires manifest and terms review before benchmark use. Credit follows
[docs/CREDIT.md](docs/CREDIT.md). A future CLA needs a separate documented project
need and reviewed agreement; no CLA or rights transfer is introduced here.
