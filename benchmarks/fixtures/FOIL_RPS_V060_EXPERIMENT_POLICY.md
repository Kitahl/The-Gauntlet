# FOIL RPS v0.6.0 experiment policy

Status: frozen prompt-only experiment fixture

## Residual Parity Search for no-tool closed-book reasoning

When a task is closed-book or externally tool-disabled, a provisional answer exists,
and no stronger permitted claim-native verifier is available, FOIL may use
**Residual Parity Search (RPS)** before final commitment.

RPS is a reasoning-control mechanism, not independent evidence.

### Goal

Do not generate a second full solution by default. Spend the minimum extra reasoning
needed to detect whether the first route entered a wrong basin, then repair only the
implicated suffix.

### Compact state

Before final commitment, retain only:

- the provisional candidate answer;
- at most three load-bearing hinges/assumptions;
- the most fragile hinge;
- the required final answer form.

Keep this state compact; do not create a second full explanation.

### Primary parity check

Run exactly one cheap, claim-native check when one applies. Prefer, in order:

1. exact inverse/reconstruction relation;
2. invariant, unit, sign, normalization, conservation, or boundary check;
3. minimal counterexample or contrapositive;
4. necessary consequence of the candidate;
5. one property that discriminates the top two candidates;
6. representation/inverse-transform consistency.

Do not count generic "review your answer" or prose criticism as a parity check.

The check returns one of:

- `PASS`
- `FAIL(<hinge>)`
- `UNCERTAIN`
- `N/A`

A `PASS` means no contradiction was found; it is not proof of correctness.

### Fast accept

If the primary parity check passes and no hard contradiction remains, finalize the
original candidate. Do not generate a challenger, second full solution, Council, or
Mastermind pass by default.

### Local conflict repair

If the parity check fails at hinge `h`:

1. freeze the reasoning prefix before `h`;
2. construct the strongest plausible **incompatible local mechanism or assumption**
   `h'` that still respects the original problem;
3. recompute only the reasoning suffix downstream of `h'`;
4. compare the resulting candidate with the original using evidence from the
   discriminating checks, not prose quality.

"Opposite" means a credible incompatible mechanism, not literal negation.

### Conditional second check

Run at most one orthogonal second parity check only when:

- the first check is uncertain or not applicable;
- the repair changes the answer;
- the repair introduces a new untested load-bearing hinge.

Do not repeat the same check in different wording.

### Discriminating tie-break

If the original and repaired candidates remain live, ask for one smallest fact,
calculation, sign, bound, invariant, counterexample, or necessary consequence whose
outcome differs between them. Resolve that discriminator and select accordingly.

Do not ask which explanation "sounds better."

### Stop law

Default maximum:

- one initial solution;
- one primary parity check;
- one local repair branch;
- one secondary parity check;
- one discriminating tie-break;
- zero full restarts.

If still unresolved, preserve uncertainty rather than entering an unbounded
self-debate loop.

### Check-bank defaults

- arithmetic/algebra: reverse substitution/reconstruction, then units/sign/bounds;
- proof/logic: counterexample/contrapositive, then boundary/equivalent form;
- physics/engineering: dimensions/conservation/limit, then sign/order-of-magnitude;
- probability/statistics: normalization/extreme case, then independent intermediate;
- causal: counterfactual/negative-control consequence, then competing-graph discriminator;
- science mechanism: necessary mechanistic consequence, then competing mechanism;
- multiple choice: property separating the top two, then necessary-consequence elimination;
- factual closed-book: distinctive property/relation, then strongest competing entity;
- abstract transform: supplied-example consistency, then inverse/representation change;
- code/algorithm without execution: invariant/pre-post condition, then adversarial boundary input.

When an exact external/tool verifier is available and allowed, prefer it over RPS.

RPS must not update the user's competence profile and must not be represented as
independent verification.

## Evidence boundary

- Internal RPS parity checks are same-model reasoning controls, not independent
  evidence. When a stronger claim-native verifier is available and permitted, it
  outranks RPS.
- A result supported only by internal RPS remains `DERIVED` unless separately
  `PROVEN`, `MEASURED`, or `CITED`. A parity pass means only that the selected
  internal contradiction check did not fire. RPS outcomes never create user
  competence evidence.
