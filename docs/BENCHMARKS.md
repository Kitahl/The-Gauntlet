# FOIL benchmark pilots

This page reports **exploratory research-software evaluations**, not official leaderboard submissions.

The evaluated conditions use the same underlying model. Closed-book HLE, ARC-AGI-1, and GPQA-Diamond use a frozen Frontier-Exam FOIL + Mastermind configuration. The newer BrowseComp experiment separately ablates generic FOIL, a benchmark-blind saved profile, and a Mastermind final audit. These are benchmark configurations, **not permanent FOIL architecture layers**.

## Current results

### R1.5 natural-miss pilot: association not identifiable

The preregistered replay reproduced the historical ARC **9/12** and GPQA
**18/24** positive control, giving exactly **nine** naturally wrong target
outputs. RC4's gold-bound exact routes detected **9/9** misses and **36/36**
deterministic mutants with **0/27** correct-output false fires, zero provider
calls, and zero tokens.

That is not evidence that mutation kill rate predicts natural-error detection.
There are only two common operator classes and both synthetic and natural rates
are constant at 1.00, so a correlation is mathematically unidentifiable. The
legacy raw scanner/mutator rows and independently assigned natural-error
operator labels are also absent. The typed primary outcome is therefore
**`NOT_IDENTIFIABLE`**, and no gate or promotion state changed.

The perfect replay rate is scoped to host-supplied benchmark gold. It tests the
executable declared-universe path, not prose-to-obligation extraction or
natural defect discovery.

- Protocol and interpretation:
  [`benchmarks/FOIL_R15_NATURAL_MISS_PILOT.md`](../benchmarks/FOIL_R15_NATURAL_MISS_PILOT.md)
- Result:
  [`benchmark_runs/2026-08-24/r15_natural_miss_pilot/report.json`](../benchmark_runs/2026-08-24/r15_natural_miss_pilot/report.json)

### RC4 integrated v5 contract pilot

The preregistered RC4 pilot passed **6/6** synthetic integration cases: host
defect routing, correct-answer stand-down, admitted generated-origin retention,
incomplete-mutation rejection, development-gate non-promotion, and
development-study non-promotion. It used **0** provider calls, network calls,
tokens, candidate generations, and answer mutations.

This is executable wiring evidence, not a behavioral benchmark. The three
formalization rows are synthetic fixtures; no real route was calibrated and no
external promotion gate advanced.

- Protocol: [`benchmarks/FOIL_V5_INTEGRATED_SMALL_PILOT.md`](../benchmarks/FOIL_V5_INTEGRATED_SMALL_PILOT.md)
- Result: [`benchmark_runs/2026-08-24/integrated_small_pilot/report.json`](../benchmark_runs/2026-08-24/integrated_small_pilot/report.json)

### RC3 safe-finalization contract pilot

The preregistered, deterministic RC3 pilot passed **7/7** cases: **3/3**
mechanically verified host-supplied rescues (exact arithmetic, canonical JSON,
and numeric tolerance) and **4/4** preservation/rejection cases (correct-answer
clear stand-down, semantic-route stand-down, same-provenance rejection, and
tampered-candidate rejection). It recorded **0 unauthorized answer changes, 0
model calls, 0 network calls, and 0 token cost**.

This is software-contract evidence, not a model benchmark. Candidate answers and
promotion-gate receipts were frozen host fixtures, so the result does not measure
repair discovery, prose-to-obligation extraction, semantic efficacy,
calibration, or external promotion. See the
[preregistration](../benchmarks/FOIL_SAFE_FINALIZATION_SMALL_PILOT.md), raw
[result](../benchmark_runs/2026-08-24/safe_finalization_small_pilot/results.json),
and [run context](../benchmark_runs/2026-08-24/safe_finalization_small_pilot/RUN_CONTEXT.md).

### Earlier blinded and legacy pilots

| Evaluation | BASE | Assisted | Delta | Evidence status |
|---|---:|---:|---:|---|
| **HLE public text-only subset** | 1/6 · **16.7%** | 2/6 · **33.3%** | **+16.7 pp** | blinded CI-scored pilot |
| **ARC-AGI-1 evaluation** | 4/6 · **66.7%** | 5/6 · **83.3%** | **+16.7 pp** | blinded CI-scored pilot |
| **GPQA-Diamond** | 9/12 · **75.0%** | 9/12 · **75.0%** | **0.0 pp** | blinded CI-scored pilot · **null result** |
| SimpleBench public subset | 3/5 · 60% | 5/5 · 100% | +40 pp | legacy manual disjoint-subset pilot |
| Current-evidence retrieval holdout | 0/5 · 0% | 5/5 · 100% | +100 pp | custom mechanism holdout; not a standard benchmark |

### BrowseComp four-way ablation

| Condition | Correct / n | Exact-normalized accuracy |
|---|---:|---:|
| **BASE** | 1/2 | **50%** |
| **FOIL** | 2/2 | **100%** |
| **FOIL_PROFILE** | 1/2 | **50%** |
| **FOIL_MM** | 0/2 | **0%** |

This is an **exploratory directional ablation with only two scored items per condition**. It does not establish that generic FOIL is superior, that the saved profile has no value, or that Mastermind is harmful. The conditions used deterministic disjoint subsets rather than same-item randomized executions, and the observed differences may be dominated by item difficulty and sampling noise.

The BrowseComp scorer uses **normalized exact string match**, not the official BrowseComp LLM-judge scoring method. The permanent result receipt is [`benchmark_runs/2026-08-22/browsecomp_four_way_results.json`](../benchmark_runs/2026-08-22/browsecomp_four_way_results.json).

### vNext re-score: descriptive evidence only

An internal evidence ledger circulated figures for a "vNext" configuration (a pooled 32/36 with
an exact McNemar p of .125). Those figures came from an unarchived scoring session and could not
be reproduced: the audit that checked them
([`validation/FOIL_LEDGER_AUDIT_2026-08-23.md`](../validation/FOIL_LEDGER_AUDIT_2026-08-23.md),
item A6) found no such result file in any branch or on disk. A mechanical re-score of the same
48-item vNext prediction file against the harness gold gives **ARC 12/12, GPQA 23/24, pooled
35/36**, with 8 discordant pairs all favouring vNext and an exact two-sided McNemar p of 0.0078.

**That stronger number is not superiority evidence and must never be reported as validated.** The
historical predictions it is compared against came from earlier *disjoint-subset* sessions, while
the vNext predictions came from a later *same-item* re-run in a different session with the
questions already public. Gold-blindness of the vNext session rests on a question-only pack
rather than on a verifiable receipt, and both benchmarks are public. The comparison is
**directional only**, and it is recorded here because the ledger's unreproducible figures should
not be the version that survives.

**Do not average these rows or conditions into one headline accuracy.** The evaluations measure different constructs, use different protocols, and have small sample sizes.

The earlier blinded receipt is [`benchmarks/results/2026-08-22-blinded-pilot.json`](../benchmarks/results/2026-08-22-blinded-pilot.json).

## 0.5.1 four-config Claude contract test (preregistered, not yet run)

A same-item paired comparison of **BASE vs FOIL** under four Claude Code configurations —
`C-SL`, `C-SH`, `C-OL`, `C-OH` = `{sonnet, opus} x {low, high}` effort — is preregistered in
[`benchmarks/CLAUDE_FOUR_CONFIG_PROTOCOL.md`](../benchmarks/CLAUDE_FOUR_CONFIG_PROTOCOL.md) and
implemented in `benchmarks/harness/claude_four_config_runner.py`.

**No unit has been executed. There are no results, and none should be inferred from the design.**

What it is: a **contract test of the FOIL skill text at matched cost**. The FOIL arm differs from
BASE by exactly two things — the skill file appended as a system prompt, and the `/foil solve`
invocation line in front of an otherwise byte-identical prompt. Model, effort, tools, tool
budget, working directory and settings are identical. It is **not** a personalization test; the
profile arms are a separate later experiment.

What it fixes relative to the pilots above: same items rather than disjoint subsets; isolated
per-unit executions in fresh working directories with the parent session's environment stripped;
opaque condition ids with the mapping sealed and hash-pinned before any run; a preregistered
analysis (mid-p McNemar primary, exact conditional as sensitivity, Wilson intervals, Holm across
the four configurations); and a scorer that refuses to open gold until the predictions are
committed.

What it still cannot do: **it is not powered.** At 24 GPQA items and 12 BrowseComp items with one
replicate, the power to detect even a large effect (30 % of items discordant, 85 % favouring
FOIL) is about **0.33** and **0.04** respectively. A non-significant result from this run means
"not powered to detect", never "no effect" and never "equivalent". The protocol's §10 carries the
full table and the reasoning.

## What the blinded runs test

### Closed-book HLE / ARC / GPQA

`BASE` is GPT-5.6 Sol answering directly. The assisted condition uses the frozen [Frontier-Exam FOIL](../benchmarks/FRONTIER_EXAM_FOIL.md) protocol plus a final Mastermind causal-defect pass. External web retrieval is not part of those assisted conditions.

### BrowseComp four-way conditions

All four BrowseComp conditions use the same GPT-5.6 Sol model and the same web-tool ceiling per item: at most 12 web search queries and at most 12 source follow-up operations.

- **BASE** — direct browsing, no FOIL protocol, saved profile, or Mastermind.
- **FOIL** — generic evidence-routing procedure: preserve clues, decompose constraints, identify candidates, seek decisive evidence, test a plausible challenger when feasible, then reread the required answer format.
- **FOIL_PROFILE** — the complete generic FOIL procedure plus the benchmark-blind saved profile frozen before BrowseComp item exposure at commit `013a728bfd6f57a8592fc3fc6e098ea52da357d5`.
- **FOIL_MM** — the complete generic FOIL procedure plus a Mastermind final audit, with **no saved profile**.

The profile and Mastermind additions are intentionally separated rather than combined, so the experiment does not confound them.

## Blinding, exclusions, and execution controls

The harnesses generate question artifacts without benchmark gold. Predictions are committed before the scoring run reads hidden answer fields.

Because conditions were executed in one conversation, the runs use **deterministic disjoint subsets** instead of giving conditions the same item. This reduces direct answer carryover but does **not** provide the causal strength of isolated same-item randomized A/B executions.

HLE excludes an item whose answer had surfaced earlier in the session and a deterministic opposite-condition balancing item.

The BrowseComp four-way run had additional pre-commit exclusions, all preserved in the machine-readable receipt:

- public results exposed published BrowseComp answer/trace material for sampled items; each contaminated item's **complete four-condition block** was retired without consulting hidden gold;
- the frozen `<=12` search-query ceiling was exceeded on two original items; both complete affected four-condition blocks were retired rather than scoring unequal-budget executions;
- a later audit found that one item had been researched against the wrong prompt; its complete four-condition block was retired rather than silently granting a second search budget;
- deterministic replacement seeds `20260827`, `20260828`, `20260829`, and `20260830` generated fresh blocks from previously unsampled rows;
- the harness asserts a final balanced sample of exactly **8 questions: 2 per condition**.

These are validity caveats, not model results. They occurred before prediction commitment and are recorded explicitly rather than hidden.

## Benchmark-specific interpretation

### BrowseComp four-way: 1/2, 2/2, 1/2, 0/2

The only defensible claim is the observed pilot result: BASE 1/2, FOIL 2/2, FOIL_PROFILE 1/2, and FOIL_MM 0/2 under the frozen conditions and exact-normalized scorer.

The result is useful primarily because it rejects an easy narrative that every added layer automatically improves performance. On these eight disjoint items, generic FOIL happened to score highest, the profile condition tied BASE, and the Mastermind condition scored lowest. With `n=2` per condition and different questions assigned to each condition, there is no basis for statistical significance or a general component-effect estimate.

A follow-up should use isolated same-item randomized executions, larger samples, preregistered exclusions, and the official BrowseComp judge if comparability to published BrowseComp results is desired.

### HLE: 16.7% → 33.3%

The difficult HLE text-only pilot shows a positive numerical delta, but `n=6` per condition is far too small for a general efficacy claim. It is evidence that the protocol did not merely operate on an already saturated task.

### ARC-AGI-1: 66.7% → 83.3%

The ARC pilot also shows a positive numerical delta. Again, six items per condition are insufficient for a robust effect estimate. A future isolated run should use substantially more ARC tasks and the same tasks across randomized independent executions.

### GPQA-Diamond: 75% → 75%

The 24-item GPQA-Diamond follow-up is the largest earlier blinded run and produced a **null result**: 9/12 in both conditions. This is retained prominently because the research question is whether the mechanism helps, not whether every benchmark can be made to show an improvement.

The null result suggests that the current Frontier-Exam procedure may add little on some expert multiple-choice problems when the underlying model already performs strongly, or that the sample is too small to detect a difference. The current evidence does not distinguish those explanations.

### SimpleBench: legacy manual pilot

The earlier SimpleBench public-subset run produced 3/5 BASE versus 5/5 FOIL. It predates the current blinded CI harness and is retained as historical exploratory evidence only. It should not be treated as equally strong evidence to the CI-scored runs.

### Current-evidence retrieval: custom mechanism holdout

The 0/5 versus 5/5 result tested a narrow mechanism: whether FOIL recognizes that rapidly changing software-version claims require fresh authoritative retrieval instead of model memory. It is useful mechanism evidence, but it is **not a standardized benchmark** and does not establish a general reasoning improvement.

## Negative and discarded results

The GPQA null and the mixed/negative BrowseComp component outcomes are retained. Several math/error-localization stress pilots were discarded because the BASE condition scored at or near 100%. Reporting saturated evaluations as improvement evidence would be non-discriminating.

## Reproduction

The public harnesses are:

```bash
python benchmarks/harness/hle_arc_prepare_score.py
python benchmarks/harness/gpqa_prepare_score.py
python benchmarks/harness/browsecomp_prepare_score.py
python benchmarks/harness/browsecomp_four_way_prepare_score.py
```

They use pinned or explicitly identified public benchmark sources and deterministic seeds. The first run prepares blinded question artifacts. If the corresponding prediction file exists, the same harness generates a score receipt.

Current benchmark sources:

- HLE public subset: pinned Science-Star mirror of HLE benchmark data;
- ARC-AGI-1: pinned ARC-AGI repository commit;
- GPQA-Diamond: official `idavidrein/gpqa` dataset archive; the archive password is publicly documented by the GPQA repository;
- BrowseComp: OpenAI `simple-evals` public BrowseComp test-set source.

## What would constitute stronger evidence

The next meaningful step is not a larger marketing table. It is an **isolated same-item A/B or multi-condition evaluation** in which independent GPT-5.6 Sol executions receive the same frozen items and equal model/tool budgets, with condition assignment hidden from scoring. That design should include more items, confidence intervals, preregistered exclusions, and mechanism ablations such as:

- BASE;
- BASE + verification/freshness gate only;
- full FOIL;
- FOIL + frozen benchmark-blind profile;
- FOIL + Mastermind final pass.

For BrowseComp specifically, a stronger public comparison should also use the official LLM-judge scoring method. Until then, the public claim is limited to the exact pilot results above.
