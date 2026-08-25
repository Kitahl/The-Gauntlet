# FOIL RPS v0.6.0 — HLE-Verified Gold hard-two challenge

Status: **FROZEN_HARD_TWO / EXPLORATORY / NOT STAGE A**
Date frozen: 2026-08-25
Seed: `20260825`

## Question

On two unused, text-only, exact-letter HLE-Verified Gold questions chosen before
model calls, does RPS rescue a Terra error without damaging a correct answer,
violating its own control law, or exceeding its token-cost hypothesis?

This is a hostile mechanism challenge, not an estimate of HLE accuracy.

## Source and pin

- Dataset: `skylenage-ai/HLE-Verified`
- Revision: `0bc83643672d4f68a5f89998617a639d85e7318b`
- Subset: Gold only
- Official Gold shard SHA-256 values are pinned in the runner and manifest.
- The five shards must conserve exactly 668 distinct IDs.

The public item artifact omits answer and rationale. Gold is reopened from the
pinned shards only after predictions and receipts are committed.

## Eligibility and selection

Eligible rows must:

1. belong to `Gold subset`;
2. be text-only, with no question or rationale image;
3. use `multipleChoice` with a single capital-letter reference answer;
4. have at most 12,000 question characters;
5. not occur in the 26-ID prior-exposure exclusion set.

The hardness proxy is frozen before calls:

1. sort eligible rows by descending question-character count;
2. break ties by SHA-256 of `seed:HLE_HARD:item_id`;
3. take the first row;
4. take the first subsequent row from a different category.

Question length is only a surface-complexity stress proxy, not a validated item
difficulty model.

## Matrix and isolation

- Models: `gpt-5.6-terra` at Low and High reasoning effort.
- Arms: `BASE` and `RPS_060`.
- Units: 2 questions × 2 model settings × 2 arms = 8.
- Positive controls: 2.
- Hard provider-call cap: 10.
- Every unit uses a fresh isolated Codex context.
- No tools, web, files, profile, external reviewer, other condition output, or retries.
- The provider is not seed-deterministic; one replicate is exploratory only.

## Conditions

`BASE` receives the item and structured output contract only.

`RPS_060` receives the same item plus the pinned FOIL skill and frozen RPS
experiment policy. It must produce only a compact public trace and exact answer;
private chain-of-thought is neither requested nor stored.

## Trace-integrity law

The harness validates semantics in addition to JSON shape:

- BASE must report no RPS activity;
- RPS must be marked eligible and name P1;
- P1 `FAIL` requires conflict, repair, and a rollback hinge;
- repair requires conflict and a hinge;
- answer change requires repair;
- a hinge cannot exist without repair;
- P2 kind and outcome must agree;
- P1 `PASS` must take the fast-accept path with no repair, P2, or tie-break.

Violations remain in the frozen results as typed integrity failures.
Whether a reported tie-break actually compared two live alternatives is not
inferable from the public trace and is therefore not asserted by the harness.

## Scoring and measurements

- Exact normalized single-letter accuracy.
- Same-item BASE/RPS discordance: both correct, BASE-only, RPS-only, both wrong.
- Rescues, damages, and net rescues.
- Conflict count, conflict concentration, repair yield, and damage given repair.
- Input, cached-input, output, and total logical tokens.
- Output-token and total-logical-token multipliers.
- Trace-integrity failures and provider/tool/profile/action conservation.

Total logical tokens are the primary cost signal. Cached input is reported
separately and is not subtracted without an explicit pricing model.

## Typed interpretation

- Any damage or trace-integrity failure is a mechanism warning.
- At least one BASE-wrong → RPS-conflict/repair → RPS-correct row is required to
  demonstrate a rescue in this challenge.
- No rescue means `NO_RESCUE_OBSERVED`, not proof of no benefit.
- Two questions cannot calibrate, promote, establish safety, or estimate HLE
  population efficacy.
- Prediction artifacts must be committed before scoring opens gold.
