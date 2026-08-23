# FOIL vNext V2 — Prospective Causal Evaluation

Status: **prospective / unscored**.

## Primary question

Does the V2 evidence-gated minimum-complement policy improve downstream performance at matched total cost, and does correct profile evidence add value beyond the same policy without a profile?

## Conditions

Run the same items under fresh isolated contexts:

1. `BASE` — direct strong-model baseline;
2. `FOIL_GENERIC` — permanent v0.4 FOIL solve+complement behavior without profile-driven routing;
3. `VNEXT2_NOPROFILE` — V2 task router with `profile=None`;
4. `VNEXT2_CORRECT_PROFILE` — V2 with a profile frozen before item exposure;
5. `VNEXT2_WRONG_PROFILE` — same V2 code with a preregistered mismatched/shuffled profile.

Optional secondary condition: `FOIL_MM`, retained only to test whether a mandatory extra audit adds value or friction.

## Isolation

Each `(item, condition)` execution must have:

- a unique session/execution ID;
- no sibling-condition outputs;
- no benchmark gold before all paired predictions are committed;
- identical model and model settings;
- identical tool availability;
- identical hard query/follow-up/tool ceilings;
- complete paired-item invalidation for contamination, wrong prompt, wrong item, retry asymmetry, or protocol violation.

## Task families

Use multiple mechanism-distinct families. Minimum recommended coverage:

- open-web discovery/retrieval;
- freshness-sensitive retrieval;
- closed-book technical reasoning;
- abstract transformation;
- closed-context multi-hop;
- numeric/quantitative checking;
- executable coding/debugging where a native runner exists.

Do not tune V2 mappings or thresholds after viewing benchmark gold.

## Profile controls

The correct profile must be frozen before the evaluation item set is exposed.

The wrong-profile condition must be generated prospectively by one deterministic rule, such as:

- participant/profile permutation;
- complement-label permutation;
- strength/gap reversal where ethically and semantically appropriate.

The wrong profile may not be selected after seeing item outcomes.

## Primary outcomes

For every condition report:

- benchmark-native correctness/quality;
- paired discordance versus BASE, FOIL_GENERIC, and VNEXT2_NOPROFILE;
- tokens;
- latency;
- external tool calls;
- intervention count;
- profile-complement count;
- unnecessary-intervention count where adjudicable;
- verifier completion/failure;
- protocol exclusions.

Use exact paired tests where appropriate and confidence intervals. Do not declare superiority from tiny samples.

## Personalization validity test

A useful profile mechanism should satisfy this ordering prospectively:

`VNEXT2_CORRECT_PROFILE > VNEXT2_NOPROFILE`

and should not be explained by generic extra work. A stronger falsification is:

`VNEXT2_CORRECT_PROFILE > VNEXT2_WRONG_PROFILE`.

If correct-profile V2 ties no-profile V2, the profile may be unnecessary. If wrong-profile V2 performs similarly to correct-profile V2, the claimed personalization mechanism is not established. If wrong-profile V2 harms results, report that as profile-risk evidence rather than hiding it.

## Minimum-complement mechanism checks

Mechanically verify in receipts that:

- benchmark names did not determine regime;
- stale/weak/strength-only profiles did not route;
- irrelevant profile gaps did not route;
- routed complements matched current task requirements;
- at most one targeted complement was emitted per policy decision;
- completed tasks did not receive gratuitous profile intervention;
- mandatory claim-native verifiers were not removed by profile routing;
- tool ceilings were never increased.

## Promotion rule

Do not replace permanent FOIL v0.4.0 with V2 merely because unit tests pass.

Promote only if prospective paired evidence shows a practically useful net benefit after accounting for accuracy/quality, cost, latency, false interventions, and robustness to profile error.

Until then classify V2 as:

`VALID_IMPLEMENTATION / BEHAVIORAL_EFFICACY_OPEN`.
