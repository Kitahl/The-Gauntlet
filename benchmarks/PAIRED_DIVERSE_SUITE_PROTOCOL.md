# Prospective paired FOIL/profile benchmark suite

Status: **prospective / unscored**. This protocol does not modify the permanent FOIL or Mastermind architecture.

## Research questions

### Experiment A — BrowseComp-40 paired ablation

On the same 40 fresh BrowseComp items, under isolated executions and identical browsing budgets, compare:

1. `BASE` — direct GPT-5.6 Sol browsing;
2. `FOIL` — generic FOIL evidence routing;
3. `FOIL_BROWSECOMP_PROFILE` — FOIL plus the previously frozen BrowseComp-specific profile;
4. `FOIL_GENERAL_PROFILE` — FOIL plus the prospectively frozen general routing profile;
5. `FOIL_MM` — FOIL plus Mastermind final audit, with no profile.

This is 40 items × 5 conditions = **200 isolated executions**.

### Experiment B — ten-benchmark diversity screen

Use ten same-item paired questions from each benchmark:

1. BrowseComp — long-tail open-web discovery;
2. FRAMES — multi-hop factual retrieval/reasoning;
3. WebWalkerQA — website traversal and information seeking;
4. FreshQA — freshness, temporal facts, and false premises;
5. Humanity's Last Exam (HLE) — broad expert academic reasoning;
6. GPQA-Diamond — graduate-level science reasoning;
7. ARC-AGI-2 — abstract transformation/generalization;
8. HotpotQA — explainable multi-hop QA;
9. MuSiQue — compositional multi-hop QA;
10. DROP — reading comprehension with discrete/numerical reasoning.

Each benchmark uses the same 10 items across four conditions: `BASE`, `FOIL`, `FOIL_GENERAL_PROFILE`, and `FOIL_MM`. The first 10 BrowseComp items are reused from Experiment A, so the diversity screen adds 9 × 10 × 4 = 360 executions. Total unique executions across both experiments: **560**.

## Frozen profiles

- BrowseComp-specific profile: `benchmarks/profiles/BROWSECOMP_BENCHMARK_PROFILE.json`, historical freeze commit `013a728bfd6f57a8592fc3fc6e098ea52da357d5`.
- General profile: `benchmarks/profiles/GENERAL_BENCHMARK_PROFILE_V1.json`, prospective freeze commit `124c06b173ba6eff2fe0d23660a1ced8b7b975c2`.

The general profile was committed before generating or viewing any new-suite item.

## Isolation requirement

A paired result is valid only when every `(benchmark, item, condition)` unit is executed in a fresh isolated model context. A unit must not have access to:

- sibling-condition answers or traces for the same item;
- hidden benchmark gold;
- earlier execution outputs from this prospective suite;
- public benchmark traces that disclose the answer to the selected item.

Each prediction receipt must include a unique `isolation_session_id`. Reusing a session ID across two units invalidates those units.

## Tool regimes

Tool availability follows the intended benchmark regime and is identical across conditions within a benchmark.

### Open-web regime

BrowseComp, WebWalkerQA, and FreshQA:

- at most 12 search queries per item;
- at most 12 source follow-up operations per item;
- current public web is allowed;
- benchmark-gold pages, leaked answer keys, and published model traces for the selected item are prohibited.

FRAMES may be run in either open-web or fixed-reference mode, but the mode must be frozen for the full paired sample before execution. The initial screen uses open-web mode with the same 12/12 ceiling.

### Closed-context / closed-book regime

HLE, GPQA-Diamond, ARC-AGI-2, HotpotQA, MuSiQue, and DROP do not receive general web search. They receive only the benchmark material that the selected regime ordinarily exposes (question/options, ARC examples, or supplied passages/context). No condition receives additional evidence unavailable to another condition.

## Condition procedures

### BASE

Solve directly using only the tools and context allowed by the benchmark regime. No FOIL decomposition, profile routing, or Mastermind audit is required.

### FOIL

Before commitment:

1. preserve every explicit constraint and the exact output contract;
2. identify the smallest set of uncertainties that can change the answer;
3. route evidence acquisition or reasoning toward those uncertainties;
4. test a plausible challenger or contradiction when useful;
5. cross-check the final answer against the original task.

### FOIL_BROWSECOMP_PROFILE

Use `FOIL` plus the complete frozen BrowseComp-specific profile. It is used only in Experiment A.

### FOIL_GENERAL_PROFILE

Use `FOIL` plus the complete frozen general profile. The profile may change effort allocation but may not change the benchmark's tool regime or budget.

### FOIL_MM

Use `FOIL`, then run the Mastermind final audit without either profile:

1. identify the earliest causal defect that could make the candidate wrong;
2. test the smallest discriminator capable of exposing that defect;
3. apply only supported corrections;
4. reread the original task and verify exact output formatting.

## Trace requirements

Every execution must record:

- benchmark/item/condition;
- `isolation_session_id`;
- final answer;
- tool counts (`search_queries`, `source_followups`, other benchmark tools when applicable);
- phase allocation: `discovery`, `candidate_testing`, `verification`, `disconfirmation`, `final_audit`;
- whether a viable candidate existed before verification began;
- confidence before answer reveal;
- one primary failure code if incorrect.

Failure-code vocabulary:

- `DISCOVERY_FAILURE`
- `WRONG_CANDIDATE`
- `REASONING_ERROR`
- `STATE_TRACKING_ERROR`
- `VERIFICATION_FAILURE`
- `BUDGET_EXHAUSTED`
- `OVERCAUTIOUS_ABSTENTION`
- `EXACT_OUTPUT_ERROR`
- `TOOL_EXECUTION_ERROR`
- `CONTAMINATED`
- `OTHER`

The trace schema exists to test mechanisms such as discovery-versus-verification allocation; traces are not allowed to alter gold scoring after the fact.

## Contamination and execution-integrity rules

1. Selection is frozen before any new-suite gold is consulted.
2. If a public answer key or published trace for a selected item is exposed during an execution, that execution is `CONTAMINATED` and is not silently replaced after observing gold.
3. Replacement items, if required, are drawn only by a preregistered deterministic replacement seed and the complete paired item is replaced across all conditions.
4. Budget overruns invalidate the complete paired item, not only the offending condition.
5. Wrong-prompt, wrong-item, or non-isolated execution invalidates the complete paired item.
6. Exclusions are reported as exclusions, never converted to model errors or successes.

## Scoring

- Use benchmark-native scoring when practical.
- BrowseComp records normalized exact match as a deterministic audit metric and must be labeled as **not the official BrowseComp LLM judge** unless the official judge is separately run.
- Multiple-choice HLE/GPQA items use exact option scoring.
- ARC-AGI-2 uses exact grid correctness under the benchmark task rule.
- HotpotQA/MuSiQue/DROP use their standard normalized answer EM/F1 where adapters support it.
- FreshQA uses FreshEval-style semantic correctness for final reporting; deterministic string overlap may be retained only as a secondary audit metric.
- FRAMES/WebWalkerQA non-exact free-form answers require a frozen semantic adjudication method before final scoring.

No gold is revealed until the complete expected prediction matrix for the relevant scoring block is present.

## Analysis

Primary outputs:

- per-benchmark accuracy/correctness by condition;
- paired item-level deltas;
- macro-average across benchmarks for the diversity screen;
- exact paired discordance counts versus `BASE` and versus `FOIL`;
- Wilson intervals for binomial accuracy where applicable;
- exact McNemar/binomial test on discordant paired outcomes where the scoring is binary;
- failure-code and phase-allocation breakdowns.

With `n=10` per benchmark, per-benchmark significance claims are not expected. The diversity suite is a mechanism screen. BrowseComp-40 is the stronger component test, and any apparent effect should be followed by a larger preregistered replication before a general efficacy claim.

## Publication boundary

These are research-software experiments, not official leaderboard submissions. The suite may establish prospective paired evidence about these frozen procedures on these samples; it does not by itself establish that FOIL, either profile, or Mastermind generally improves GPT-5.6 Sol.
