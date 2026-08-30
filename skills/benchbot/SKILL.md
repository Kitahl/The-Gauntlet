---
name: benchbot
description: Measure — evaluation and benchmarking module for Strong Inference. Trigger: /time, /benchbot, benchmark, baseline, capability, ceiling, cost, effort/reward, stop-go, comparison, or ablation. Designs evaluations that distinguish real mechanism gain from stronger models, more tools, or more compute.
---

# Measure

## Evaluation design

1. Define the construct and primary endpoint.
2. Select a strong direct baseline.
3. Match model/tool/data/compute budgets where the causal question requires it.
4. Add ablations for the mechanism under test.
5. Freeze test items/protocol before observing results when possible.
6. Use multiple seeds only when stochasticity materially affects outcome.
7. Preserve raw outputs and failure cases.
8. Report uncertainty and exclusions.

## Required distinctions

Do not conflate:

- benchmark score with general capability;
- assisted output quality with independent user competence;
- more compute with better routing;
- multiple agents with independent evidence;
- specification checks with behavioral efficacy.

## Stop/go

Ask:

- what result would change the decision?
- how much headroom exists over the strong baseline?
- is current work upstream of the load-bearing unknown?
- what is the cheapest discriminating experiment?

A negative result is a valid output and should be recorded rather than optimized away.

## Typed runtime contract

`tools/time_runtime.py` provides reusable paired-binary analysis with the discordance table, exact conditional McNemar p-value, Wilson intervals, Holm correction and first-class exclusion metadata. Fixed-n inference is not represented as anytime-valid; adaptive monitoring requires a separately validated sequential method. See `docs/specs/TIME_ENGINEERING_SPEC.md`.

## Compatibility

Public product name: **Measure**. Stable technical identity: `benchbot`; stable commands include `/time` and `/benchbot`. **Evaluation & Benchmarking** is the legacy public label retained in historical documentation and receipts.
