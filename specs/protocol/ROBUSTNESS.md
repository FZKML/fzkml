# Valid but harmful reference updates v1 — #53

Use the approved M0 two-feature, scale-16, half-up integer relation in
`specs/m0/relation-v0.1.md`. This deliberately does not adopt the separate
three-client RNE `fzknum` language contract. `training_step` is an arbitrary-
precision native reference; `training_relation` checks its exact declared step.
It is not a full-training proof verifier or a circuit.

Initial W=(0,0), X=(16,0), honest label Y=16 gives delta=(16,0). Poisoning the
label to -16 gives delta=(-16,0). Both squared norms are 256, within 4608; both
pass the norm property and both correctly execute the step on their respective
inputs. The honest evaluation squared loss, computed as an exact rational on
X=(16,0), Y=16, is initially 1, then 0 versus 4. Substituting the helpful delta
for the poisoned-data execution fails the exact training relation. Thus correct
execution on harmful input differs from incorrect execution.

These are bounded original synthetic examples, not estimates of a real learning
population. Proof validity concerns the declared relation; statistical utility
concerns a specified evaluation set; Byzantine tolerance requires a separate
adversary/aggregation theorem; source authenticity requires provenance or trusted
measurement. None implies another. There is no claim that these data are truthful
or representative or that norm clipping prevents poisoning.

A real full-training-proof execution remains **not-run** pending #33/#46. The
future circuit must bind the same poisoned/honest inputs, rounding and output;
its results must be added through CI-04 and its negative cases must reject the
incorrect trace. The native example alone does not close that acceptance item.
