# FOIL RPS v0.6.3 Stage-2 blind-rival small protocol

Date: 2026-08-25
Classification: preregistered diagnostic smoke only

## Question

When Stage 1 declines, can a fresh task-only rival provide useful agreement
without incumbent anchoring, and at an acceptable total-token and abstention
cost?

This protocol does not test promotion, calibration, or production authority.

## Frozen inputs

- Reuse the two already-frozen ProcessBench GSM8K questions and their A0
  predictions from `adaptive_two_benchmark`.
- Reuse three configurations: Terra low, Terra high, and Sol low.
- The Stage-2 request file is built from `items.json` only, before A0 predictions
  are opened. It has no incumbent-answer field.
- Gold remains unopened until Stage-2 predictions are committed.

## Stage 1

The host selects from task/source steps before reading A.

- Unique mechanically computed result: host may keep or replace A inside the
  benchmark-only v0.6.3 path.
- `NOT_APPLICABLE` or `UNCERTAIN`: request one blind rival.
- No second rival and no retry after an invalid attempt.

## Stage 2

- B runs in a fresh ephemeral working directory.
- B receives the task and a prescribed reverse-check/forward-earliest method.
- B never receives A, A's prompt receipt, gold, correctness, or error labels.
- The response schema is closed: `answer`, `abstain`, `method_summary`.
- Tools, files, network retrieval, user configuration, and project rules are
  disabled for the call.
- Exact ProcessBench normalization is the only comparator in this pilot.
- Mechanical agreement keeps A as supporting evidence only.
- Disagreement, model abstention, or unsupported output becomes final
  `ABSTAIN`; B is never selected without a deterministic discriminator.

## Receipts

Private ignored row receipts retain both reconstructed A prompt/answer and B
prompt/answer, comparator result, and token counts. Public receipts retain
digests, model route, usage, validity, and the closed B answer.

## Primary metrics

- paired base versus final accuracy;
- rescues and damages;
- Stage-2 trigger and agreement counts;
- abstention rate among Stage-2-triggered units;
- agreement-implies-correct count;
- mean, median, and aggregate total-token multiplier, where Stage-2 tokens are
  added to the already-paid A0 tokens.

## Diagnostic kill conditions

The smoke is killed if any of the following occurs:

1. any correct A is changed to an incorrect non-abstaining answer;
2. triggered abstention rate exceeds **20%**;
3. aggregate total-token multiplier exceeds **1.35x**;
4. any provider/tool count exceeds the frozen cap or any task/answer/receipt
   binding fails.

These thresholds only classify this two-question smoke. Passing cannot promote
the route. With three expected Stage-2 triggers, one abstention already exceeds
the 20% ceiling; the small sample is intentionally unforgiving but not
statistically informative.

## Freeze and scoring

1. Commit runner, core contract, schema, protocol, request file, and manifest.
2. Run at most three blind-rival calls.
3. Persist predictions before printing results.
4. Commit predictions and public receipts before opening gold.
5. Score and independently audit raw rows.

No production activation, profile write, external/free bot, Gauntlet merge, or
Mastermind merge is authorized.
