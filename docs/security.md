# Workflow and public artifact policy

Public fork builds use `pull_request`, standard ephemeral `ubuntu-24.04` runners,
empty workflow permissions and explicit per-job `contents: read`. Checkout does
not persist credentials. There are no repository, environment or cloud secret
references, privileged trigger chains, self-hosted runners, reusable workflows,
executable caches, PR comment bots or artifact downloads. A PR can modify its
own checks, so protected branch review of workflow and validator changes remains
essential. This policy checker is a conservative regression guard for these
small workflows, not a general security analysis of arbitrary shell programs.

The workflow checker rejects non-allowlisted/unpinned actions, unsafe triggers,
write permissions, missing/over-30-minute timeouts, matrices above 16 combinations,
secret references, persistent runners, cache actions, checkout ref overrides,
shell expression interpolation and uploads outside the reviewed report path.
Action SHAs are immutable and updates require review. Python, uv, Rust, runner
family and all dependencies are pinned; the actual hosted runner image revision
is recorded in the job summary. The Ubuntu family pin is not a byte-identical
runner image. Rust dependencies and bundled native code are inventoried with preserved notices;
Cargo.lock is enforced.

Trusted report publication rebuilds from reviewed `main` in the `public-reports`
environment. It never consumes PR-produced archives, data, executables or caches.
The publication is a commit-versioned GitHub Actions artifact, retained seven days,
not a release or an indefinitely hosted report. No release, Pages or cloud write
permission is granted. PRs get bounded job summaries; generated files are tested
locally but PR artifacts are not uploaded. Release/long-term report archival is
pending an explicitly reviewed publication path.

Public artifacts have exactly six allowed paths, with no subdirectories:

| Path | Content |
| --- | --- |
| results.json | Closed-schema public result bundle with raw repetitions |
| claims.json | Closed-schema claim registry and evidence mappings |
| summary.json | Deterministic coverage and run statuses |
| report.md | Escaped job summary/static report |
| report.html | Escaped static HTML, restrictive CSP, no scripts |
| plots.svg | Generated numerical panels; no imported markup |

Each file is at most 1,000,000 bytes; total at most 4,000,000 bytes; JSON has depth
at most 24 and 30,000 nodes; arrays and strings have schema limits. Symlinks,
hardlinks, special files, unknown paths, duplicate JSON keys and nonfinite numbers
are rejected. An existing output directory is never overwritten. Before upload,
the validator regenerates every output and compares exact bytes, so an edited
HTML/SVG/summary cannot be smuggled through. Diagnostic messages are bounded error
codes, never raw input, environment dumps or validation exception contents.

Targeted scanning blocks the synthetic `FZKML_FORBIDDEN_SECRET` marker, common
GitHub/AWS credential forms, private-key headers and credential assignments.
Closed fields prevent witness/raw-record/share/participant additions; data/model
IDs must be public or synthetic and license/publication metadata is required.
Narrative fields still require human publication review. Pattern matching cannot
recognize all credentials or infer whether arbitrary prose contains private
information. A self-declared review ID does not replace approval by the reviewer.

Synthetic examples are generated placeholders and contain no training data or
protocol randomness. The fixture metadata uses CC0-1.0 only for its synthetic
placeholder assets; the repository code remains Apache-2.0. Future real datasets
must supply their actual license and permitted-publication decision.

Repository administrators must maintain and verify these controls. Actual
configuration evidence and unresolved settings are in `docs/implementation.md`:

- Protect `main`: require the CPU validation check, pull requests, CODEOWNERS
  review, dismissal of stale approvals, resolved conversations, and no unchecked
  bypass. Restrict changes to workflow/policy/toolchain paths through review.
- Protect `public-reports`: allow only `main`, require an appropriate reviewer,
  restrict bypass and document whether self-review is allowed. Merely naming the environment in YAML
  does not configure these protections; GitHub may otherwise create it unprotected.
- Set Actions default workflow permissions to read-only and require approval for
  first-time external fork workflows. Keep fork write-token/secret options off.
- Enable secret-scanning alerts and push protection where supported. Record
  availability/limitations if the repository plan or visibility does not support them.
- Verify settings through repository ruleset/environment/security API or UI and
  retain dated evidence.

CODEOWNERS names one current owner. Adding two names would allow either to approve;
it would not enforce two independent approvals. If two distinct reviews are
required, enforce the approval count and independence with suitable rules or a
separate reviewed check.

Action releases verified against their official release refs and `action.yml`:
checkout v7.0.1, setup-python v7.1.0 and upload-artifact v7.0.2. All use Node 24;
the exact immutable commit SHAs are shared by the workflows and action allowlist.
