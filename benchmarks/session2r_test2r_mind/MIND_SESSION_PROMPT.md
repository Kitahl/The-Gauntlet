# SESSION B — TEST #2R — MIND ONLY

Run only the MIND arm of the certified paired Mind retest. This must be a fresh conversation independent of Session A. Do not access BASE material and do not score.

## Frozen authority

Repository: `Kitahl/The-Gauntlet`

Frozen package commit: `ba72a15ac294d11c7c792363de1d52dc960b404a`

Experiment: `SESSION2R_TEST2R_MIND`

Intended model: **GPT-5.6 Sol**

Frozen Mind blob SHA:

`8c27111809e390910a74b1380b9fbce12b016999`

Expected work: exactly **90 predictions** in frozen order:

- 50 primary Omni-MATH-Rule
- 30 formal BBEH
- 10 exploratory state-tracking BBEH

Maximum visible response budget: **700 tokens per benchmark item**, identical to BASE.

## Absolute isolation boundary

Before and during MIND inference you may access from the frozen package only:

- `benchmarks/session2r_test2r_mind/MANIFEST.json`
- `benchmarks/session2r_test2r_mind/VALIDATION_REPORT.json`
- `benchmarks/session2r_test2r_mind/CI_CERTIFICATION.json`
- `benchmarks/session2r_test2r_mind/mind/questions.jsonl`

Always fetch package files at exact commit `ba72a15ac294d11c7c792363de1d52dc960b404a`.

In addition, before opening any MIND question, fetch and verify the exact frozen Mind blob SHA:

`8c27111809e390910a74b1380b9fbce12b016999`

from `Kitahl/The-Gauntlet`.

Do NOT list the package directory recursively.

Do NOT access:

- `base/questions.jsonl`
- any BASE receipt, BASE answer, BASE reasoning, or BASE hash
- any path under `gold/`
- `score.py`
- `scoring/`
- package builder/validator source
- workflow files or workflow logs
- git diffs/history for the package
- previous Test #2 questions, traces, predictions, or gold
- any Gauntlet skill other than the exact frozen Mind blob

If answer/reference/gold information appears in model-visible context before the receipt is committed, stop immediately with:

`INVALID — RAW GOLD EXPOSURE`

If BASE material appears, stop with:

`INVALID — ARM CONTAMINATION`

## Tool policy

Benchmark solving is closed-book.

During inference do NOT use:

- web search
- calculator
- Python for solving
- Wolfram
- symbolic algebra
- Z3 / theorem prover
- external retrieval
- external LLM judge
- Mirror / FOIL
- Soul, Space, Reality, Power, Time, Gauntlet, Meditate, Council, Mastermind

Only the exact frozen Mind specification may be activated.

GitHub access is administrative only: certification files, the exact Mind blob, and the MIND question projection.

After all 90 predictions are frozen, local code may be used only to serialize the already-fixed receipt and calculate SHA-256. It may not alter or solve answers.

## Phase 1 — verify certification and load Mind

Fetch the three permitted public certification files.

Require:

- `GOLD_VALIDATED = true`
- 90 unique questions
- 50 primary Omni
- 30 formal BBEH
- 10 exploratory BBEH
- prior Test #2 IDs excluded
- BASE/MIND projections certified byte-identical
- question projection gold-leak check = PASS
- canonical self-tests = PASS
- reference-solution crosschecks = PASS
- equivalent-answer tests = PASS
- negative-control tests = PASS
- answer-type checks = PASS
- high-risk Omni admission checks = PASS

If any requirement fails, stop:

`MIND PHASE BLOCKED — PACKAGE CERTIFICATION FAILED`

Now fetch the exact Mind blob `8c27111809e390910a74b1380b9fbce12b016999` and verify that exact SHA before any question is fetched.

Activate only that specification.

If it cannot be fetched exactly, stop:

`MIND PHASE BLOCKED — FROZEN MIND UNAVAILABLE`

State:

`MIND PACKAGE VERIFIED — MIND LOADED — GOLD NOT ACCESSED — BASE NOT ACCESSED`

## Phase 2 — solve MIND questions in bounded batches

Do not fetch the whole 90-line file in one operation.

Fetch and solve sequentially from:

`benchmarks/session2r_test2r_mind/mind/questions.jsonl`

using these exact 1-based ranges:

1. lines 1–10
2. lines 11–20
3. lines 21–30
4. lines 31–40
5. lines 41–50
6. lines 51–60
7. lines 61–70
8. lines 71–80
9. lines 81–90

Complete and freeze each batch before fetching the next.

Never fetch the BASE question projection.

Apply the frozen Mind procedure to every item while obeying the same 700-visible-token ceiling as BASE. Mind may change the reasoning procedure; it does not receive extra tools or output budget.

### Omni-MATH-Rule

Use concise Mind-guided reasoning and finish with:

`FINAL ANSWER: <answer>`

The receipt `answer` field contains only the final answer itself.

### BBEH

Apply Mind while following the task's requested final-answer format exactly. The receipt `answer` contains the submitted final answer; `response` contains the exact visible response used for evaluation.

Once an item is finalized and you move to the next item, do not revisit it.

## Phase 3 — immutable MIND receipt

After all 90 tasks, construct exactly 90 JSONL records in frozen order:

```json
{
  "id": "frozen task id",
  "condition": "MIND",
  "benchmark": "omni_math_rule or bbeh",
  "section": "primary_omni / secondary_bbeh_formal / exploratory_bbeh_state_tracking",
  "answer": "exact final answer only",
  "response": "exact visible benchmark response"
}
```

Serialize exact bytes to:

`SESSION2R_MIND_RECEIPT.jsonl`

Calculate SHA-256 and create:

`SESSION2R_MIND_RECEIPT.sha256.txt`

The hash file must include the SHA-256, package commit `ba72a15ac294d11c7c792363de1d52dc960b404a`, and Mind blob `8c27111809e390910a74b1380b9fbce12b016999`.

If file creation is unavailable, output the complete JSONL and SHA-256 directly without changing predictions.

Then state exactly:

`MIND COMMITTED — 90 predictions frozen`

After that statement, do not access gold or BASE, do not score, and do not revise the receipt.

Return the receipt and SHA files to the user for transfer to the independent SCORE session.
