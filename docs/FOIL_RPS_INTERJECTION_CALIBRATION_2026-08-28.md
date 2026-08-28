# FOIL RPS interjection calibration

**Date:** 2026-08-28
**Status:** benchmark-active host verification; model interjection disabled

## Decision

FOIL has two mechanisms that were previously described together as an
"interjection":

1. A precommitted deterministic host check can inspect a mechanically decidable
   property and, when it produces a unique result, select that result in an
   explicitly benchmark-only path.
2. A model can be asked to review the answer in the same context or produce a
   blind rival in a fresh context. These routes generate hypotheses; without an
   independent verifier they do not establish which answer is correct.

The calibrated policy keeps mechanism 1 active in benchmarks and disables both
model routes. Host decline preserves A0. A host contradiction without a unique
host result abstains. Nothing in this calibration grants production authority.

## Frozen evidence used

| Route | Attempts | Rescues | Damages or accuracy losses | Added tokens | Decision |
|---|---:|---:|---:|---:|---|
| Same-context no-tools review | 30 | 2 | 2 damages, 1 invalid | 793,077 | `STAND_DOWN` |
| Blind rival | 3 | 0 | 1 accuracy loss | 55,407 | `UNCALIBRATED` |
| Deterministic host selection | 6 diagnostic rows | 2 | 0 | 0 | benchmark-active only |

The three blind-rival rows are three configurations of one question, not three
independent questions. They averaged 18,469 added tokens per trigger. This is
far below the configured minimum of 20 auditable observations and supplies no
rescue evidence.

The same-context route has enough rows to evaluate under the caller's HLE
target economics. Its conservative utility lower bound is -36,727 microunits,
so it stands down rather than consuming tokens or risking an answer change.

The host-selection result is classified
`FROZEN_OUTPUT_DIAGNOSTIC_REPLAY_ONLY`. It proves the benchmark wiring and the
mechanical selection rule on those frozen rows. It is not promotion evidence or
evidence of general HLE improvement.

## Calibrated parameters

For the caller-supplied target of 11 to 22 correct on 60 rows inside a 250,000
token benchmark envelope:

- required net rescues: 11;
- target token value per required net rescue: 22,727;
- damage loss: 45,454;
- invalid-outcome loss: 11,364;
- minimum positive-utility margin: 1,137;
- confidence interval mass: 95%;
- minimum auditable observations per model route: 20;
- maximum blind rivals at runtime: **0**;
- maximum host-verified benchmark answer changes per item: **1**;
- production authorization: **false**.

The 250,000-token value is an experiment input, not a hard-coded FOIL product
limit. A different benchmark owner can supply another envelope, which changes
the value weights while retaining the same fail-closed rules.

## What no-tools FOIL can and cannot do on HLE

No-tools model interjection can sometimes push a model into a different
reasoning basin and expose knowledge already present in the model. The frozen
same-context arm did this twice. It also changed two correct answers to wrong
ones and cost roughly 793k extra tokens, so the effect was not safe or economic.

No-tools FOIL cannot fetch a fact absent from the prompt and model state. When a
host check declines on a factual or semantic HLE question, a second model answer
is only another hypothesis. Without retrieval or a deterministic discriminator,
FOIL cannot know that the rival is better. The calibrated action is therefore
to preserve A0 rather than spend tokens on an unadmitted rival.

## Next valid experiment

A future model-interjection experiment must use fresh, arm-blind, host-declined
and base-wrong rows—the cell in which latent knowledge recovery could matter.
It must meet the 20-row evidence minimum, measure rescues, published damages,
invalid outcomes, abstentions, and total tokens, and freeze predictions before
opening gold. Until that evidence exists, blind-rival generation remains off.

## Reproduction

```powershell
python benchmarks/harness/foil_rps_interjection_calibration.py `
  benchmark_runs/2026-08-26/hle_active_20/independent_audit.json `
  benchmark_runs/2026-08-25/rps_v063_active_replay/report.json `
  benchmark_runs/2026-08-25/rps_v063_stage2_small/predictions.json `
  benchmark_runs/2026-08-25/rps_v063_stage2_small/report.json `
  benchmark_runs/2026-08-28/rps_interjection_calibration/report.json `
  --rows 60 --baseline-correct 11 --target-correct 22 `
  --maximum-total-tokens 250000
```

Sealed report SHA-256:
`747ca0c6a39224efbc54d47373229985c4ee8a6a8d45695a5bdc16cb7e160f87`.
