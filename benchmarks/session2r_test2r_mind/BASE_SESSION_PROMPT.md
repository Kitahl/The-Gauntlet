# SESSION A — TEST #2R — BASE ONLY

Run only the BASE arm of the certified paired Mind retest. Do not run MIND and do not score.

## Frozen authority

Repository: `Kitahl/The-Gauntlet`

Frozen package commit: `ba72a15ac294d11c7c792363de1d52dc960b404a`

Experiment: `SESSION2R_TEST2R_MIND`

Intended model: **GPT-5.6 Sol**

Expected work: exactly **90 predictions** in frozen order:

- 50 primary Omni-MATH-Rule
- 30 formal BBEH
- 10 exploratory state-tracking BBEH

Maximum visible response budget: **700 tokens per benchmark item**.

## Absolute isolation boundary

Before and during BASE inference you may access from the frozen package only:

- `benchmarks/session2r_test2r_mind/MANIFEST.json`
- `benchmarks/session2r_test2r_mind/VALIDATION_REPORT.json`
- `benchmarks/session2r_test2r_mind/CI_CERTIFICATION.json`
- `benchmarks/session2r_test2r_mind/base/questions.jsonl`

Always fetch these at exact commit `ba72a15ac294d11c7c792363de1d52dc960b404a`.

Do NOT list the package directory recursively.

Do NOT access:

- `mind/questions.jsonl`
- any path under `gold/`
- `score.py`
- `scoring/`
- `build_package.py`
- `build_package_ci.py`
- validator source
- workflow files or workflow logs
- git diffs/history for the package
- previous Test #2 questions, traces, predictions, or gold
- the Mind skill or Mind blob

If answer/reference/gold information appears in model-visible context before the receipt is committed, stop immediately with:

`INVALID — RAW GOLD EXPOSURE`

If MIND material is exposed, stop with:

`INVALID — TREATMENT CONTAMINATION`

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
- Soul, Mind, Space, Reality, Power, Time, Gauntlet, Meditate, Council, Mastermind

GitHub access is administrative only: use it solely to obtain the permitted public certification files and the BASE question projection.

After all 90 predictions are frozen, local code may be used only to serialize the already-fixed receipt and calculate its SHA-256. It may not alter or solve any answer.

## Phase 1 — verify certification

Fetch the three permitted public certification files.

Require all of the following:

- `GOLD_VALIDATED = true`
- 90 unique questions
- 50 primary Omni
- 30 formal BBEH
- 10 exploratory BBEH
- prior Test #2 IDs excluded
- BASE/MIND question files certified byte-identical
- question projection gold-leak check = PASS
- canonical self-tests = PASS
- reference-solution crosschecks = PASS
- equivalent-answer tests = PASS
- negative-control tests = PASS
- answer-type checks = PASS
- high-risk Omni admission checks = PASS

If any requirement is absent or false, stop:

`BASE PHASE BLOCKED — PACKAGE CERTIFICATION FAILED`

State:

`BASE PACKAGE VERIFIED — GOLD NOT ACCESSED — MIND NOT ACCESSED`

## Phase 2 — solve BASE questions in bounded batches

Do not fetch the whole 90-line question file in one operation.

Fetch and solve sequentially from:

`benchmarks/session2r_test2r_mind/base/questions.jsonl`

using these exact 1-based line ranges:

1. lines 1–10
2. lines 11–20
3. lines 21–30
4. lines 31–40
5. lines 41–50
6. lines 51–60
7. lines 61–70
8. lines 71–80
9. lines 81–90

Complete and freeze each batch before fetching the next batch.

Never fetch `mind/questions.jsonl`.

For each item, solve using ordinary GPT-5.6 Sol reasoning only.

### Omni-MATH-Rule

Give concise reasoning within the common 700-visible-token ceiling and finish with:

`FINAL ANSWER: <answer>`

The receipt field `answer` must contain only the final answer itself, not the label `FINAL ANSWER:`.

### BBEH

Follow the task's requested final-answer format exactly. Keep reasoning concise and within the same 700-token ceiling. The receipt field `answer` must contain the submitted final answer, while `response` preserves the exact visible response used for evaluation.

Once an item's response has been finalized and you move to the next item, do not revisit or revise it.

## Phase 3 — immutable BASE receipt

After all 90 tasks are complete, construct exactly 90 JSONL records in the original frozen question order. Each record must contain:

```json
{
  "id": "frozen task id",
  "condition": "BASE",
  "benchmark": "omni_math_rule or bbeh",
  "section": "primary_omni / secondary_bbeh_formal / exploratory_bbeh_state_tracking",
  "answer": "exact final answer only",
  "response": "exact visible benchmark response"
}
```

Do not include alternative answers or later corrections.

Serialize the exact receipt bytes to a file named:

`SESSION2R_BASE_RECEIPT.jsonl`

Calculate SHA-256 over those exact bytes and create:

`SESSION2R_BASE_RECEIPT.sha256.txt`

The hash file must contain the SHA-256 plus package commit:

`ba72a15ac294d11c7c792363de1d52dc960b404a`

If file creation is unavailable, output the complete JSONL receipt and SHA-256 directly without changing any prediction.

Then state exactly:

`BASE COMMITTED — 90 predictions frozen`

After this statement, do not open gold, do not fetch Mind, do not score, and do not revise the receipt.

Return the receipt file and SHA file to the user for transfer to the independent SCORE session.
