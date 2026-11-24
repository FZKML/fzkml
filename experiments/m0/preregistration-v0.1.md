# Matched experiment preregistration, version 0.1

Status: #19 design frozen before any benchmark in this branch. No run, quality
gain or proof overhead is reported. Change the version and record the reason
before altering thresholds, seeds, exclusions or resource budgets after observing
results. Sources: §§43.3, 77.1, 80.1–80.4 and exercises D.45/D.48.

Arms: L trains a local model at each site; F performs ordinary federation; P
performs that same federated computation with the selected protected aggregation
and release mechanism; Z performs P with the specified proof policy. A pooled
synthetic reference is optional and explicitly labeled. M0 currently implements
none of these training/protection arms. P and Z remain not-run until aggregation,
proof and any claimed privacy mechanism are versioned and available. A clear
simulator is never labeled protected federation.

The first arithmetic profile uses four clients, one round, two-feature
squared-loss regression, initial encoded W=(8,4), rate 1, scale 16 and ties
toward positive infinity, exactly `relation-v0.1`. Each client uses its first
canonical training record; public equal weights and denominator 4 are fixed.
The generator's remaining records supply evaluation and future profile design.
Sample-count experiments that change consumed records require a new relation
version supporting a declared batch reduction; they cannot claim to measure
sample-count effects with the one-record relation unchanged.

Compare F/P/Z on the same complete honest trace first: fixed records, roster,
initialization, operations, quantization, final bytes and release policy. Assert
byte equality where the mechanism is identical; a changed DP release is a
different comparison. When isolating proof overhead, P and Z share the same
privacy unit, mechanism/accountant, noise distribution and resource budget.
Use an explicit deterministic simulation tape only for synthetic trace matching;
never publish production protection randomness or call that tape DP evidence.

Separately compare deployments from the same initially eligible clients, with
identical arrival/deadline schedule and per-role budgets. Retain invited,
completed, verified, accepted and released client counts. Proof-induced exclusion
is an outcome. Do not condition the primary deployment comparison on only the
clients whose proofs completed. Test one declared deviation at a time, and include
bounded valid-but-harmful contributions to expose the relation's limits.

## Analysis fixed in advance

Use public experiment seeds 0–19, paired across all arms. A seed is the unit of
an independent simulated repetition, not each record or each retry. Each seed
has at most two attempts; both retain costs. Keep a 300-second wall cap, one CPU
worker per role, one concurrent local simulation, 2 GiB per worker and no GPU.
Record actual host hardware and scheduling. A larger backend needs a new
preregistration before measurement, rather than silently changing the budget.

Primary arithmetic endpoint: exact agreement of the accepted model for matched
honest traces. Primary quality endpoint: held-out entity/future-time MSE on
decoded values, with useful-quality threshold MSE <= 0.05. This is an engineering
surrogate threshold, not an externally validated outcome. Primary operational
endpoint: time to an authorized certified result meeting that threshold; never
reached within the cap is reported as censored, with reached/eligible fraction.
MSE is nonnegative and unbounded, so CI-04's ratio-valued quality field cannot
encode it directly without a reviewed schema extension.

Report every paired seed difference (quality, wall time, total work, bytes),
mean and median, plus paired nonparametric bootstrap 95% intervals using 10,000
resamples of whole seed pairs and public analysis seed 20261124. No significance
claim is based on these small synthetic data. Report missing-pair counts and
reasons, all failures/timeouts, and complete-case estimates explicitly conditional
on completion. Do not impute absent quality as zero, omit failed resource costs,
or replace capped time with the mean of successful runs. Report worst-site and
per-site quality, cohort-tail latency, exclusions and all declared endpoints;
secondary exploratory analyses are labeled as such.

For information-value experiments, preregister a distinct profile with independent
factors: consumed sample count {8,32}, source diversity {1,4} at matched total
count, and label quality {exact, declared 1/4 deterministic synthetic corruption}.
Cross all eight cells; fix feature/label mechanism, optimizer effort, model size,
splits, evaluation population and noise across the intended contrasts. Avoid
counting repeated visits/duplicates as new entities. Explicitly separate
entity-disjoint generalization from held-out-source evaluation; the default
split holds out entities and future time, not whole sources. An honest null or
adverse diversity effect refutes the claimed benefit in that scope. A claim
that proofs unlock new institutional access additionally requires a consented
field study of authorization and participation; synthetic utility cannot
establish adoption, clinical benefit or organizational willingness.
