# M0 research registry

This directory records source locations and original engineering decisions for
issues #12–14 and #19–23. It contains no manuscript body or native equation
payload. The manuscript remains outside the software license and distribution.

- `manuscript.json`: canonical Google Doc, observed revision, text-only digest,
  extraction method and source-access limitations.
- `coverage.json`: all 80 chapters and 48 exercises, their issue mappings and
  explicit extraction state. A mapping is a work assignment, not evidence.
- `source-index.json`: section anchors and native-equation positions. Equation
  contents are unavailable through the Docs read used here and remain pending.
- `claim-context.json`: source locations, observer, privacy unit, numeric scope,
  required validation and implementation state for each registered claim.
- `coverage-report.md`: generated accounting; never a book-verification badge.

The one claim registry is `claims/registry.json`, using CI-05's
`schemas/claims-1.0.0.json`. Scientific context lives in a keyed companion file
for precise coalition views, source locators and validation obligations. The
shared registry also supplies CI-05's coarse observer, privacy-unit and numerical
identifiers. The current M0 claim records concern an external reviewer and
declare no implemented DP unit; exact conditional views remain in the companion.
No second claim-status enum or result validator is introduced. See
`specs/m0/measurement-v0.1.md` for
the scientific requirements consumed by CI-04, including outstanding interface
gaps. Schema changes belong to #15/#16 and require coordinated review.

For authorized source access, open the URL in `manuscript.json` using the
connected Google Docs integration or request access from the document owner.
Do not assume a local copy exists. Record the revision before and after reading,
the tab, heading anchor and UTF-16 range. Compare the text digest only after
using the stated extraction method. Native equation omission prevents this hash
from identifying a complete mathematical edition. Before promoting an
equation-dependent claim, inspect the actual equation through an authorized
render/export, record its exact locator, and retain an authorized immutable
snapshot outside the public source distribution. No permission to publish the
manuscript, its images, or restricted source artifacts follows from read access.

`MS20261124` is a local registry edition label for the observed source revision;
it is not an author-declared manuscript edition or publication date. Claim IDs
are permanent. Corrected statements get explicit version changes and an impact
review; never reuse an ID for a different proposition. Group repeated equations
under one claim, and retain all supporting locations in `claim-context.json`.

Validation (locked CI-05 environment; no source download):

```sh
PYTHONPATH=src uv run --locked python scripts/check_research.py
PYTHONPATH=src uv run --locked python -m unittest discover -s tests -v
```

The checker calls the shared schema and semantic claim validator in this checkout.
During parallel development, an explicit `--ci-root` argument checks this registry
against the shared schema in another checkout.
The research checker adds scientific metadata consistency and coverage checks;
neither command establishes a theorem or protocol security.
