# FOIL benchmark pilots

This page reports **exploratory research-software evaluations**, not official leaderboard submissions.

The evaluated assistance condition uses the same underlying model as the baseline. For the newer blinded runs, `FOIL_MM` means the frozen [Frontier-Exam FOIL](../benchmarks/FRONTIER_EXAM_FOIL.md) protocol plus a final Mastermind causal-defect pass. It is a benchmark configuration, **not a new permanent FOIL architecture layer**.

## Current results

| Evaluation | BASE | Assisted | Delta | Evidence status |
|---|---:|---:|---:|---|
| **HLE public text-only subset** | 1/6 · **16.7%** | 2/6 · **33.3%** | **+16.7 pp** | blinded CI-scored pilot |
| **ARC-AGI-1 evaluation** | 4/6 · **66.7%** | 5/6 · **83.3%** | **+16.7 pp** | blinded CI-scored pilot |
| **GPQA-Diamond** | 9/12 · **75.0%** | 9/12 · **75.0%** | **0.0 pp** | blinded CI-scored pilot · **null result** |
| SimpleBench public subset | 3/5 · 60% | 5/5 · 100% | +40 pp | legacy manual disjoint-subset pilot |
| Current-evidence retrieval holdout | 0/5 · 0% | 5/5 · 100% | +100 pp | custom mechanism holdout; not a standard benchmark |

**Do not average these rows into one headline accuracy.** They measure different constructs, use different protocols, and have small sample sizes.

The permanent machine-readable receipt is [`benchmarks/results/2026-08-22-blinded-pilot.json`](../benchmarks/results/2026-08-22-blinded-pilot.json).

## What the newer blinded runs test

### BASE

`BASE` is GPT-5.6 Sol answering directly without the benchmark-specific FOIL/Mastermind procedure.

### Frontier-Exam FOIL + Mastermind (`FOIL_MM`)

The assisted condition freezes seven behaviors before evaluation:

1. classify the domain and answer form;
2. preserve the exact claim, including quantifiers, exclusions, signs, units, and required format;
3. generate the strongest plausible challenger, counterexample, or alternative answer;
4. use a claim-native closed-book check when allowed, such as exact arithmetic or consistency checking;
5. verify answer-choice mapping, dimensions, indexing, representation, and output format;
6. calibrate confidence only after the verification pass;
7. run a Mastermind final pass: identify the earliest causal defect that could make the candidate answer wrong, apply the smallest supported correction, then reread the original question.

For closed-book HLE, ARC and GPQA evaluations, external web retrieval is not part of the assisted condition.

## Blinding and contamination controls

The newer harnesses generate question artifacts without benchmark gold. Predictions are committed before the scoring run reads the hidden answer fields.

Because both conditions were executed in one conversation, the run uses **deterministic disjoint subsets** instead of giving BASE and FOIL the same item. This reduces direct answer leakage, but it does **not** provide the causal strength of isolated same-item randomized A/B executions.

HLE additionally excludes an item whose answer had surfaced earlier in the session and a deterministic opposite-condition balancing item. BrowseComp preparation excludes items for which public benchmark traces/answers surfaced during research, plus balancing items. These exclusions are frozen without consulting the harness's hidden gold for the retained items.

## Benchmark-specific interpretation

### HLE: 16.7% → 33.3%

The difficult HLE text-only pilot shows a positive numerical delta, but `n=6` per condition is far too small for a general efficacy claim. It is evidence that the protocol did not merely operate on an already saturated task.

### ARC-AGI-1: 66.7% → 83.3%

The ARC pilot also shows a positive numerical delta. Again, six items per condition are insufficient for a robust effect estimate. A future isolated run should use substantially more ARC tasks and the same tasks across randomized independent executions.

### GPQA-Diamond: 75% → 75%

The 24-item GPQA-Diamond follow-up is the largest blinded run in this release and produced a **null result**: 9/12 in both conditions. This is retained prominently because the research question is whether the mechanism helps, not whether every benchmark can be made to show an improvement.

The null result suggests that the current Frontier-Exam procedure may add little on some expert multiple-choice problems when the underlying model already performs strongly, or that the sample is too small to detect a difference. The current evidence does not distinguish those explanations.

### SimpleBench: legacy manual pilot

The earlier SimpleBench public-subset run produced 3/5 BASE versus 5/5 FOIL. It predates the current blinded CI harness and is retained as historical exploratory evidence only. It should not be treated as equally strong evidence to the CI-scored runs.

### Current-evidence retrieval: custom mechanism holdout

The 0/5 versus 5/5 result tested a narrow mechanism: whether FOIL recognizes that rapidly changing software-version claims require fresh authoritative retrieval instead of model memory. It is useful mechanism evidence, but it is **not a standardized benchmark** and does not establish a general reasoning improvement.

## Negative and discarded results

Several math/error-localization stress pilots were discarded because the BASE condition scored at or near 100%. Reporting them as evidence for FOIL would be non-discriminating. Saturated evaluations are recorded as discarded rather than used to inflate the result set.

## Reproduction

The public harnesses are:

```bash
python benchmarks/harness/hle_arc_prepare_score.py
python benchmarks/harness/gpqa_prepare_score.py
python benchmarks/harness/browsecomp_prepare_score.py
```

They use pinned or explicitly identified public benchmark sources and deterministic seeds. The first run prepares blinded question artifacts. If the corresponding prediction file exists, the same harness generates a score receipt.

Current benchmark sources:

- HLE public subset: pinned Science-Star mirror of HLE benchmark data;
- ARC-AGI-1: pinned ARC-AGI repository commit;
- GPQA-Diamond: official `idavidrein/gpqa` dataset archive; the archive password is publicly documented by the GPQA repository;
- BrowseComp: OpenAI `simple-evals` public BrowseComp test-set source.

## What would constitute stronger evidence

The next meaningful step is not a larger marketing table. It is an **isolated same-item A/B evaluation** in which independent GPT-5.6 Sol executions receive the same frozen items and equal model/tool budgets, with condition assignment hidden from scoring. That design should include more items, confidence intervals, predeclared exclusions, and mechanism ablations such as:

- BASE;
- BASE + verification/freshness gate only;
- full FOIL;
- FOIL + Mastermind final pass.

Until then, the public claim is limited to the exact pilot results above.
