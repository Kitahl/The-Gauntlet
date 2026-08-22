# Frontier-Exam FOIL — benchmark-only configuration

This is a **benchmark protocol**, not a new permanent FOIL architecture layer.

Purpose: test whether FOIL's existing evidence/verification behavior plus a Mastermind pre-commit audit improves difficult closed-answer benchmark performance.

## Condition

`FOIL_MM` uses the same underlying model as `BASE` and receives no benchmark gold information.

For every item:

1. **Classify** the domain and required answer form.
2. **Freeze the claim** actually being asked; preserve quantifiers, signs, units, exclusions, and qualifiers.
3. **Generate a challenger**: the strongest plausible alternative answer, counterexample, or failure mode.
4. **Verify natively** when benchmark rules permit: exact arithmetic, enumeration, symbolic manipulation, or consistency checks. No external web search for closed-book HLE/ARC items.
5. **Check representation**: answer choice ↔ derivation, dimensions, units, sign, indexing, and required output format.
6. **Calibrate** confidence only after the verification pass.
7. **Mastermind final pass**: identify the earliest causal defect that could make the proposed answer wrong, apply only the smallest supported correction, and re-read the original question to ensure the correction did not change the task.

## BASE

`BASE` answers directly using the underlying model without the seven-step FOIL/Mastermind protocol and without external tools/retrieval.

## Validity boundary

Because BASE and FOIL_MM are executed in one conversation, they use deterministic **disjoint subsets**. This avoids direct same-item answer contamination but is weaker than isolated same-item A/B inference. Results are exploratory pilot estimates, not official benchmark submissions.