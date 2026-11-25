# Data lifecycle and outcome contracts, version 1.0.0

This fills Session 03's specification/source-mapping/reference-validation slots
for #101–#105. Engineering requirement IDs are separate from scientific claim
IDs. The existing 23 claim statuses and authoritative equation catalog are
unchanged; affected hypothesis IDs are links, not promoted evidence.

| Issue | Delivered in this slot | Remaining issue-completion evidence |
| --- | --- | --- |
| #101 | Exact 2D ridge retained-statistic downdate/recompute, historical teaching inputs, original perturbation/residual example, lineage and known-copy/accounting checks | Protected statistics, genuine transition proof, finite arithmetic, authorized deletion/copy lifecycle system and independent review |
| #102 | Exact three-player allocation, uniform-error conditional bound, replication and visible-payout counterexamples | Current-source migration/review, private valuation and credential integration, real learner-utility uncertainty and separately authorized incentive design |
| #103 | Full count/diversity/label-quality factorial preregistration with L/F/P/Z controls, split/failure/falsification validation | Versioned batch relation, all training/protection/proof backends and actual paired benchmark runs/uncertainty |
| #104 | Four primary-source sector cards and an executed original synthetic pilot with two disjoint holdouts | Original-source access/rights, source-matched reproduction/replication and sector-specific review |
| #105 | Prospective institution-level offer study, ITT estimand, selection/attrition/interference and evidence-stage rules | Consent/institutional/protocol/privacy approvals, sampling/power design, recruitment, actual authorized contributions and causal analysis |

## Reproduction and artifact boundary

```sh
PYTHONPATH=src uv run --locked python specifications/validate.py
PYTHONPATH=.:src uv run --locked python -m unittest discover -s tests -p test_data_outcomes.py -v
PYTHONPATH=.:src uv run --locked python -m specifications.data_outcomes.run --output /private/tmp/fzkml-data-outcomes-reference.json
```

The authoritative validator checks closed contract/plan/card schemas, exact
historical source IDs/ranges, affected claim/test links and the inherited
preregistration hash. The local runner validates a closed artifact with exact
source/dirty state, program/contract/lock and pilot dataset/split/model/preprocessor
digests, environment, raw finite-reference observations and reproduction command.
It remains unapproved for scientific publication. Canonical result conversion,
publication, CI and archive tooling remain Session 04's ownership.

The pilot is actually executed. Factorial training, original-paper replications
and the adoption study remain not-run. No real payment, recruitment, record
removal or physical copy erasure occurs. The source-only archive excludes the
private manuscript and local raw artifact.

## Historical source inspection

`docs/research/data-outcomes-source-review.json` pins MS20261124, its exact text
version, observed revision, authorized private export digest and section ranges.
Selected old prose and equation text were inspected for the small ridge and
valuation inputs. Numerical outputs are transparent reference calculations;
current-edition reviewed numerical goldens, native-ID migration and independent
mathematical review remain pending. A current metadata token differs, so no
content-equivalence or edition migration is inferred. No manuscript prose/body,
export, image or equation XML is distributed.

## #101: retained-set removal and numerical certificate

The reference declares the fixed sum objective
`J(w)=sum_i (x_i^T w-y_i)^2/2 + lambda*||w||^2/2`, with lambda>0 and two exact
rational features. Its sufficient state is `A=sum_i x_i x_i^T+lambda I` and
`b=sum_i x_i y_i`. Removing authorized rows subtracts their data statistics while
keeping lambda fixed. Average objectives or sample-count-scaled regularization
require a different relation. Duplicate row identities and unauthorized removals
reject. The recomputed retained state and the downdate must agree exactly.

Because `A_retained >= lambda I`, an approximate candidate with residual
`r=A_retained*w_hat-b_retained` has parameter error at most `||r||/lambda`.
The reference checks the squared rational inequality and an original nonzero
perturbation example. This is conditional elementary linear algebra, not a
checked formal theorem or a finite-field proof. Encoding, rounding, sufficient-
statistic accumulation and modular no-wrap obligations belong to the selected
implementation. Optimality here concerns this convex objective, not arbitrary
network unlearning or downstream transformations.

The historical two-unit-coordinate example yields old `(1/2,1/2)` and retained
`(0,1/2)`. An additional original three-row example checks a nonzero parameter
change and residual bound. Source input/independent calculation scope is explicit;
these are not empirical removal or privacy guarantees.

The lineage checker consumes trusted parent/model, known-artifact inventory and
prior ledger state supplied outside the request. It cannot trust a deletion
request to declare its own complete cache inventory. A tombstone or reused old
model is insufficient. Source snapshots, derived artifacts, caches/checkpoints
and declared retained/uncontrolled copies remain separately accounted for.
The toy action labels do not delete files or establish authenticated durability.
Unobserved copies remain unknown. Earlier authorized releases/history persist;
deletion cannot refund already disclosed information. The sample retained-cost
counter is an arbitrary declared reference cost, not calibrated DP epsilon. A
new model release needs its own disclosure/accounting analysis. This task does
not erase the manuscript/source archives or earlier public artifacts.

## #102: valuation transformation and its limits

The historical three-player utility table is enumerated exactly. Its Shapley
allocation is `(13/30,1/3,2/15)`, summing to 9/10. This certifies a finite table
transformation; it does not establish that the table came from an authorized
learner, validation population or real counterfactual training process.

If `|u_tilde(S)-u(S)|<=eta` holds uniformly over every coalition, each marginal
changes by at most 2eta. Nonnegative Shapley weights sum to one for a player, so
allocation error is at most 2eta. The code checks the complete finite-table
premise. Average error on sampled coalitions or a correct surrogate-inference
circuit does not establish that uniform premise. True allocation gaps greater
than 4eta preserve ranking under those assumptions; closer scores need not.
Exact enumeration removes sampling error for the toy table, not uncertainty
about real utility. A sampling-based learner needs a distinct budget/CI protocol.

The interchangeable-resource example changes a controlled entity's allocation
from 1/2 to 2/3 by enrolling two identities, without adding coalition utility.
Efficiency/correct proofs therefore do not imply incentive compatibility or
entity uniqueness. Define reward recipients, credential issuers, admission units,
credential replacement and ownership/collusion; a fresh public key is not a new
independent contributor. Deduplication itself has a target and disclosure scope.

The payment observer is part of the privacy view. In a singleton additive game,
the visible allocation equals that utility. Hidden computation cannot conceal
an authorized payout's information. Public payment ledgers, each recipient's own
output, coordinator observations and disputes require separate analysis; joint
privacy is not public privacy of every payout. No real transfer or incentive
experiment is implemented or authorized here.

## #103: factorial information-value benchmark

`factorial-v1.json` extends the existing preregistration by exact hash: count
{8,32} × diversity{1,4} × labels{exact,1/4 deterministic corruption}; all eight
cells, arms L/F/P/Z and paired seeds 0–19. L is local-only, F ordinary federation,
P the declared protected mechanism, Z P plus the genuine proof policy. The
single-record M0/fzknum relation cannot measure consumed-count effects unchanged;
a versioned batch relation and actual backends are readiness gates.

Preserve identical honest records/cohort/initialization/operations/rounding and
release mechanism for the intended F/P/Z controls. Isolating proof overhead must
keep P/Z privacy mechanisms equal. Separately compare deployment admission and
cost from the same eligible population, retaining incomplete/invalid/excluded
contributors. A simulator or skipped proof cannot stand in for P/Z.

Preregister realized count/source/label-quality and non-IID checks, unique
protected entities, duplicate/related clusters, independent seeds, model effort,
held-out sites and entity/future-time splits. Our strict split check targets
unseen entities; other forecasting/transductive claims need their own declared
past-context policy. Fit preprocessing on training data only. Keep test target
information out of training, tuning and model selection.

The proposed scoped diversity hypothesis requires a useful MSE gain 0.01 at
matched count/label quality. An upper uncertainty bound below that threshold
refutes the minimum-gain claim; overlap, missing comparisons or underpower is
inconclusive. The decision function is a reference rule, not observed evidence.
Freeze version/criteria before runs. Retain all arms/seeds, unsuccessful attempts,
censoring and negative/adverse findings. Report site/time-held-out and worst-site
quality, appropriate calibration/group endpoints and uncertainty at the actual
independent unit. Synthetic learning gains would still not prove data access,
clinical/public benefit or generative-data value.

## #104: external evidence and one synthetic pilot

`sector-cards-v1.json` keeps each source's endpoint/population and local execution
separate. Primary sources and inspected versions are linked in each card:

- [EXAM author manuscript](https://dash.harvard.edu/server/api/core/bitstreams/6b7755b9-d34c-49b5-a67b-310167d6a6f1/content): the card separates training sources, independent tests and the selected-metric subset; no clinical or FZKML outcome is inferred here.
- [Starlit v2](https://arxiv.org/html/2401.10765v2): a synthetic financial-data evaluation, not a deployed FZKML fraud outcome.
- [FedCMAPSS v1](https://arxiv.org/html/2608.26433v1): simulated engine trajectories and task-specific RUL prediction benchmarks; virtual client/task counts do not establish physical deployment.
- [MELLODDY](https://pmc.ncbi.nlm.nih.gov/articles/PMC11005050/): cross-pharma predictive evidence with private source data/models; no proprietary experiment is reproduced here.

No original data or code is adopted. Missing access, denied terms or an unsuitable
population is unsupported, not successful replication. Paper results remain
external published evidence. Source datasets, splits, model/hyperparameters,
endpoints, software/hardware, privacy model and deviations must match before a
reproduction/replication claim. A changed fixture is an adaptation.

The actual pilot uses original synthetic site/machine/time observations and
rational ridge: 96 training rows from 32 entities at four sites; 16 future-time
new-entity observations; 24 observations from two held-out sites. It reports exact
MSE, worst-site MSE and a training-mean baseline. The target is synthetic/unitless,
not actual remaining life, fraud, medical outcome or a FZKML treatment contrast.
One deterministic fixture supplies no population CI. It exercises the pipeline
and leakage checks; it cannot certify any sector's source replication or benefit.

## #105: prospective access/adoption design

`adoption-v1.json` fixes the comparison at institution-level offers: locality-only,
secure aggregate and verified protected. Every offer must describe actual versioned
roles/views/releases, capability limits and comparable operational/governance
costs. Do not promise an unproved ZK/DP guarantee. These bundled contrasts estimate
offer effects, not isolated technical mechanisms.

The proposed primary ITT estimand is the difference in probability of an actually
authorized, transferred, validated novel contribution within 90 days among eligible
institutions consenting before random assignment. Establish the sampling frame,
baseline authorized access, novelty rule, stratification and assignment probability
before exposure. Consent to a study is distinct from organizational authority to
contribute a dataset. Willingness, authorization, transfer, novelty, learner utility
and beneficiary benefit are different outcomes.

Keep assigned denominators, cost-driven refusal and attrition. Distinguish known
zero contributions from missing follow-up, retain reasons and predefine sensitivity
bounds. Address shared governance and collaboration/interference between units.
Sample size, power and feasibility remain pending. Broader beneficiary and generated-
data claims require their own observations. Independent study/protocol/privacy
and institutional approvals precede recruitment. There are no participants,
contacts, approvals, observations or claimed effect in this implementation.
Hypothetical/synthetic records can exercise state checks but cannot establish
that otherwise unavailable data was unlocked.
