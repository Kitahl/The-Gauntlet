# FOIL RPS v0.6.0 — Terra Low/High tiny smoke

Status: **FROZEN_TINY_SMOKE / NOT A PREREGISTERED STAGE A RUN**  
Date frozen: 2026-08-25  
Seed: `20260825`

## Question

On four frozen no-tool items, does current FOIL plus the proposed RPS policy show
any rescue, damage, conflict signal, or token-cost signal relative to BASE?

This is an integration and mechanism smoke only. It cannot calibrate, promote, or
establish superiority.

## Matrix

- Models: `gpt-5.6-terra` at `low` and `high` reasoning effort.
- Arms: `BASE` and `RPS_060`.
- Items: two fresh GPQA-Diamond questions and two ProcessBench-GSM8K traces (one
  labelled clean and one labelled erroneous), selected before calls.
- Units: 4 items × 2 model settings × 2 arms = 16; plus two positive controls.
- Every unit is a fresh ephemeral, read-only Codex context. Tools are prohibited.
- No retries. No replacements based on model outcomes.

## Selection

- GPQA source is pinned to revision `56686c06f5e19865c153de0fdb11be3890014df7`.
  The first three candidates used by the earlier dose-response pilot and all frozen
  development exposures are excluded. Remaining eligible rows are hash-ranked.
- ProcessBench uses the official converted GSM8K parquet whose SHA-256 is
  `9896315aff77fff8fe60361f05b612250598a4bd88a70ffba567b4d580d6d4a3`.
  Earlier adaptive-pilot items are excluded; one clean and one erroneous row are
  hash-ranked within their strata.

Public item artifacts omit answers, correctness labels, and ProcessBench error
indices. Predictions and public receipts must be committed before scoring refetches
the pinned sources and opens gold.

## Conditions

- `BASE`: item prompt plus common answer/trace contract only. The trace records
  `rps_eligible=false` and no check.
- `RPS_060`: the current FOIL skill plus the frozen prompt-only RPS experiment
  fixture. No runtime changes, profiles, external reviewer, tools, or second model.

The RPS public trace is self-reported telemetry, not proof that a hidden parity check
was executed correctly.

## Measurements

Report each benchmark and model setting separately, plus a plainly labelled total:

- paired correctness, rescues, damages, and net rescues;
- RPS conflict count, conflict precision/recall, repair yield, and damage given repair;
- input, cached-input, output, and total token counts where the CLI reports them;
- output-token and total-token multipliers;
- invalid calls, tool events, provider calls, profile writes, and answer mutations.

## Decision boundary

No pass/fail promotion gate is attached to four questions. A damage is a warning;
zero damages is not a safety bound. Apparent lift or savings are observations only.
The full supplied HLE/GPQA protocol remains unrun.
