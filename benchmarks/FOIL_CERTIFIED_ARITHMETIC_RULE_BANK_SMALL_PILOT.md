# FOIL certified arithmetic rule-bank small pilot

Status: **frozen synthetic integration protocol; no calibration or promotion**

## Purpose

Exercise the new default-off arithmetic rule bank across distinct mechanical
shapes without claiming production efficacy. The scanner receives only a task,
an A0 answer, and their content digests. No gold answer, correctness label, or
expected scanner result crosses the discovery boundary.

## Frozen cases

| Case | Scorer-side class | Intended rule |
|---|---|---|
| "v2-correct" / "v2-defect" | correct / defect | "certified-v2" |
| "power-correct" / "power-defect" | correct / defect | "numeric-power-equality-v1" |
| "raw-correct" / "raw-defect" | correct / defect | "raw-numeric-equality-v1" |
| "trace-correct" / "trace-defect" | correct / defect | "trace-constraint-consistency-v1" |
| "prose-unsupported" | unsupported | free prose equality |
| "unit-unsupported" | unsupported | semantic unit statement |
| "percent-unsupported" | unsupported | percentage notation |
| "rounded-unsupported" | unsupported | approximate/non-assertive equality |

The exact strings and expected outcomes are versioned in
"benchmarks/harness/foil_certified_rule_bank_pilot.py". Cases are not replaced
or tuned based on scanner output.

## Invariants

- The route is disabled by default and every default-off call abstains.
- Enabled benchmark evaluation is explicitly unadmitted and compiles only in
  the local benchmark path.
- "GENERATED_UNADMITTED" remains visible.
- A0 text and digest are preserved exactly.
- Provider, model, bot, token, profile-write, action, execution-authority,
  answer-mutation, and promotion counts are zero.
- All attempted cases appear in raw rows and conservation holds.
- Report hashing is deterministic.

## Interpretation

This pilot may prove only that the frozen plumbing and rule contracts behave on
these synthetic examples. It does not estimate false-fire probability, natural
error recall, extraction recall, real-claim coverage, frontier-model behavior,
or production value. No outcome can admit or promote the route. The existing
ProcessBench P0.5 rows remain development-contaminated and cannot serve as a
fresh per-split certificate.
