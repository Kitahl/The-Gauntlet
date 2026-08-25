# SESSION C — TEST #2R — SCORE ONLY

Score the two immutable receipts from independent BASE and MIND sessions. Perform no new benchmark inference.

## Required user inputs

The user must provide:

- `SESSION2R_BASE_RECEIPT.jsonl`
- `SESSION2R_BASE_RECEIPT.sha256.txt`
- `SESSION2R_MIND_RECEIPT.jsonl`
- `SESSION2R_MIND_RECEIPT.sha256.txt`

If either arm receipt or its committed hash is missing, stop with:

`SCORE PHASE BLOCKED — IMMUTABLE RECEIPTS REQUIRED`

## Frozen authority

Repository: `Kitahl/The-Gauntlet`

Frozen package commit:

`ba72a15ac294d11c7c792363de1d52dc960b404a`

Experiment: `SESSION2R_TEST2R_MIND`

Frozen Mind blob used by the treatment arm:

`8c27111809e390910a74b1380b9fbce12b016999`

Expected paired sample:

- 50 primary Omni-MATH-Rule items
- 30 formal BBEH items
- 10 exploratory state-tracking BBEH items
- 90 identical task IDs per arm

## No new inference

Do not solve any benchmark question in this session.

Do not repair, improve, rewrite, normalize semantically, or regenerate either arm's predictions before scoring.

The two receipts are immutable observations.

## Phase 1 — verify receipt integrity before opening gold

Before accessing sealed gold, fetch only these public files at exact package commit `ba72a15ac294d11c7c792363de1d52dc960b404a`:

- `benchmarks/session2r_test2r_mind/MANIFEST.json`
- `benchmarks/session2r_test2r_mind/VALIDATION_REPORT.json`
- `benchmarks/session2r_test2r_mind/CI_CERTIFICATION.json`
- `benchmarks/session2r_test2r_mind/assignment_manifest.json`

Do not open gold yet.

Verify:

1. `GOLD_VALIDATED = true` in the public certification artifacts.
2. Each receipt contains exactly 90 JSONL predictions.
3. BASE records all have `condition = BASE`.
4. MIND records all have `condition = MIND`.
5. No duplicate IDs exist in either receipt.
6. BASE and MIND ID sequences are identical.
7. Receipt ID sequence matches the frozen `assignment_manifest.json` order exactly.
8. Both receipt hash files identify package commit `ba72a15ac294d11c7c792363de1d52dc960b404a`.
9. MIND hash metadata identifies frozen Mind blob `8c27111809e390910a74b1380b9fbce12b016999`.
10. Recompute SHA-256 over the exact uploaded JSONL bytes for each arm and require equality with the committed SHA files.

If any integrity condition fails, stop:

`INVALID / INCONCLUSIVE — RECEIPT INTEGRITY FAILURE`

State:

`RECEIPTS VERIFIED — 90 PAIRED ITEMS — GOLD STILL SEALED`

## Phase 2 — open only the frozen scoring package

Only after receipt verification may you access, at exact package commit `ba72a15ac294d11c7c792363de1d52dc960b404a`:

- `benchmarks/session2r_test2r_mind/gold/SEALED_UNTIL_BOTH_ARMS_COMMIT/gold.jsonl`
- `benchmarks/session2r_test2r_mind/score.py`
- `benchmarks/session2r_test2r_mind/scoring/omni_grader.py`
- `benchmarks/session2r_test2r_mind/scoring/bbeh_evaluate.py`
- `benchmarks/session2r_test2r_mind/requirements-score.txt`

Do not fetch upstream benchmark datasets or alternative gold.

The gold JSONL has exactly 90 lines. If a connector would truncate the file, fetch it in these exact line ranges and concatenate without modification:

1. 1–10
2. 11–20
3. 21–30
4. 31–40
5. 41–50
6. 51–60
7. 61–70
8. 71–80
9. 81–90

Use only the frozen scorer implementations and compatible dependencies specified by the package.

If the exact frozen scorer cannot be executed, stop and report:

`SCORE PHASE BLOCKED — FROZEN SCORER UNAVAILABLE`

Do not substitute an LLM judge.

## Phase 3 — run paired scoring

Run the frozen `score.py` against the exact BASE and MIND receipt bytes.

The primary endpoint is the 50 paired Omni-MATH-Rule items.

For each section report:

### Primary — Omni-MATH-Rule, n=50 per arm

- BASE correct / 50
- MIND correct / 50
- accuracy for each
- absolute percentage-point delta
- Wilson 95% interval for each arm
- both correct
- both wrong
- BASE wrong / MIND right
- BASE right / MIND wrong
- exact two-sided McNemar p-value
- difficulty breakdown
- domain breakdown

### Secondary — formal BBEH, n=30 per arm

- BASE correct / 30
- MIND correct / 30
- accuracy and delta
- paired discordance counts
- exact two-sided McNemar p-value
- results for each of the ten formal families

### Exploratory — state-tracking BBEH, n=10 per arm

- BASE correct / 10
- MIND correct / 10
- paired discordance counts
- family breakdown

Label this section:

`EXPLORATORY — NOT PRIMARY EFFICACY ENDPOINT`

Do not combine all 90 tasks into an official benchmark score. A descriptive overall correct count may be shown only if labeled:

`DESCRIPTIVE CROSS-BENCHMARK TOTAL — NOT AN OFFICIAL BENCHMARK METRIC`

## Phase 4 — scorer audit

Report every scorer exception or unresolved case.

Because the Omni package was pre-certified to simple mechanically gradeable answer forms, do not casually override a frozen scorer failure with subjective judgment.

If a genuine scorer defect is discovered after receipts are frozen:

- preserve the raw prediction;
- preserve the frozen gold;
- mark the item `SCORER REVIEW REQUIRED`;
- report primary results both with the item excluded and under any defensible deterministic adjudication;
- do not silently change the main result.

## Phase 5 — observable cost

Use only receipt-visible response text.

Report for each arm:

- total visible response characters
- mean visible response characters per item
- median visible response characters per item

If reliable visible token counts are directly available, report them too. Do not estimate or reveal private chain-of-thought.

## Phase 6 — discordant-pair audit

For every paired disagreement, compare only the visible responses and classify the observable failure where supported:

- missing edge case
- missing solution branch
- endpoint error
- invalid inference
- arithmetic error
- algebra error
- combinatorial count error
- incorrect assumption
- contradiction missed
- counterexample missed
- state-tracking error
- temporal/order error
- answer-format error
- scorer issue
- unknown

Do not infer hidden reasoning.

## Validity audit

Report explicitly:

- package commit exactly matched: YES/NO
- `GOLD_VALIDATED = true`: YES/NO
- independent CI certification passed: YES/NO
- completely new Test #2R questions: YES/NO according to package certification
- prior Test #2 IDs excluded: YES/NO
- BASE receipt hash verified: YES/NO
- MIND receipt hash verified: YES/NO
- both receipts contain exactly 90 predictions: YES/NO
- paired ID/order identity: YES/NO
- BASE and MIND were run in independent sessions: YES/NO based on supplied receipts/session records
- BASE did not access MIND material: YES/NO/UNKNOWN
- MIND did not access BASE material: YES/NO/UNKNOWN
- gold concealed during both inference sessions: YES/NO/UNKNOWN
- frozen Mind blob matched: YES/NO
- same 700-visible-token ceiling specified: YES/NO
- Mirror/FOIL used: YES/NO/UNKNOWN
- other Gauntlet modules used: YES/NO/UNKNOWN
- external solving tools used during inference: YES/NO/UNKNOWN
- scorer exceptions/review cases: list

If a load-bearing validity field is NO, use `INVALID / INCONCLUSIVE`.

## Verdict

Use exactly one:

`POSITIVE DIRECTION`

`MIXED`

`TIE / NO OBSERVED DIFFERENCE`

`NEGATIVE DIRECTION`

`INVALID / INCONCLUSIVE`

Prioritize the paired 50-item Omni result. Secondary or exploratory BBEH cannot override a negative primary Omni result.

## Required final report

### SESSION / TEST
`Session #2R — Test #2R — Mind`

### PACKAGE
`ba72a15ac294d11c7c792363de1d52dc960b404a`

### FROZEN MIND
`8c27111809e390910a74b1380b9fbce12b016999`

### GOLD CERTIFICATION
Summarize the public certification gates without reproducing gold.

### PRIMARY — OMNI-MATH-RULE
Full paired results and exact McNemar.

### SECONDARY — FORMAL BBEH
Full paired and family results.

### EXPLORATORY — STATE TRACKING
Separate results.

### COST
Observable response-cost comparison.

### DISCORDANT PAIRS
Every disagreement and supported classification.

### VALIDITY AUDIT
Complete checklist.

### VERDICT
One permitted verdict.

### INTERPRETATION
State narrowly whether this experiment supports the claim that explicit activation of the frozen Mind procedure improves GPT-5.6 Sol on this pre-certified formal-reasoning sample.

Do not generalize beyond this model, skill blob, benchmark population, and protocol.
