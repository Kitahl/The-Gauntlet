# BrowseComp four-condition FOIL ablation

This is an exploratory benchmark protocol. It does not modify the permanent FOIL architecture.

## Research question

With the same GPT-5.6 Sol model and the same web-search capability, does BrowseComp exact-answer performance differ among:

1. `BASE` — no FOIL procedure;
2. `FOIL` — generic FOIL evidence-routing procedure;
3. `FOIL_PROFILE` — FOIL plus a benchmark-blind profile frozen before BrowseComp item exposure;
4. `FOIL_MM` — FOIL plus a Mastermind pre-commit audit, without the profile.

The fourth condition is intentionally **FOIL + Mastermind with no profile**. This isolates the profile and Mastermind additions rather than combining them.

## Shared tool budget

Every condition has the same available per-item budget:

- at most 12 web search queries;
- at most 12 source follow-up operations (open/click/find);
- no benchmark-gold access;
- no use of answers or traces from prior BrowseComp evaluations.

A condition may stop early when it has sufficient evidence. The budget is a ceiling, not a requirement to spend all calls.

## Condition procedures

### BASE

Browse directly for the answer. No FOIL decomposition, profile routing, or Mastermind audit is required.

### FOIL

Before commitment:

1. preserve every clue and exact output requirement;
2. decompose the question into independently searchable constraints;
3. identify candidate entities/answers;
4. seek evidence for decisive constraints;
5. search for at least one plausible challenger or disconfirming constraint when feasible;
6. cross-check the final exact answer against the original question.

### FOIL_PROFILE

Use the complete `FOIL` procedure plus the frozen profile at `benchmarks/profiles/BROWSECOMP_BENCHMARK_PROFILE.json`. The profile may change search allocation and verification priority, but not the total tool budget.

### FOIL_MM

Use the complete `FOIL` procedure. Then run a Mastermind final audit:

1. identify the earliest causal defect that could make the candidate answer wrong;
2. test the smallest discriminator capable of exposing that defect;
3. apply only a supported correction;
4. reread the original question and confirm exact-answer formatting.

Do **not** use the frozen profile in this condition.

## Experimental boundary

Because all four conditions are executed in one conversation, they use deterministic disjoint subsets. This avoids direct same-item answer carryover but is weaker than isolated same-item randomized A/B testing. Results are exploratory and are not an official BrowseComp submission.
