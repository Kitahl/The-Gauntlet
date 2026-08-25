# SESSION #3 — TEST #3 — SPACE VS BASE

Run the frozen GitHub package as a **fresh-session comparison of GPT-5.6 Sol BASE versus the frozen Space / Research Discovery skill**.

## Frozen package

Repository: `Kitahl/The-Gauntlet`

Package commit: `6cd91b5c447afc7521e404e6167a729673f5b924`

Development branch: `benchmark/session3-test3-space-package`

Folder: `benchmarks/session3_test3_space/`

Frozen Space blob: `a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

The frozen experiment contains exactly:

- 20 FreshQA tasks total
- 20 AssistantBench validation tasks total
- BASE: 10 FreshQA + 10 AssistantBench = 20
- SPACE: 10 FreshQA + 10 AssistantBench = 20
- 40 unique tasks total
- deterministic seed `2026082503`

Do not regenerate or alter the assignments.

---

# 1. ABSOLUTE GOLD BOUNDARY

Before **both BASE and SPACE prediction receipts are committed**, you may fetch only these four files, always at exact commit `6cd91b5c447afc7521e404e6167a729673f5b924`:

1. `benchmarks/session3_test3_space/MANIFEST.json`
2. `benchmarks/session3_test3_space/assignments.json`
3. `benchmarks/session3_test3_space/questions/freshqa_questions.jsonl`
4. `benchmarks/session3_test3_space/questions/assistantbench_questions.jsonl`

Do **not** list or recursively fetch the package directory.

Before both condition commitments, do not access or inspect:

- any path containing `gold/SEALED_UNTIL_BOTH_ARMS_COMMIT`
- `score.py`
- `requirements-score.txt`
- `scoring/`
- `build_package.py`
- `build_package_ci.py`
- `validate_package.py`
- workflow files or workflow logs
- Git history or commit diffs for this package
- prior Test #3 benchmark traces
- upstream benchmark source datasets or answer files

If any answer key, benchmark gold, gold URL, explanation, scorer output, reference answer, or equivalent answer material enters model-visible context before both arms are committed, stop immediately and report exactly:

`INVALID — RAW GOLD EXPOSURE`

No comparative statistics may then be reported.

---

# 2. MODEL

Intended model: **GPT-5.6 Sol**.

Record the active model identity if available. If materially different, report:

`INVALID CONFIG — intended model GPT-5.6 Sol`

---

# 3. SKILL ISOLATION

Before BASE is committed, do not read, fetch, reconstruct, summarize, or invoke Space.

During inference do not use:

- Mirror / FOIL
- Soul
- Mind
- Reality
- Power
- Time
- Gauntlet
- Meditate
- Council
- Mastermind

BASE uses ordinary GPT-5.6 Sol research behavior.

After BASE commitment, SPACE may use **only** the exact frozen Research Discovery skill blob `a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`.

Do not load Space runtime helpers or another Gauntlet component.

---

# 4. MATCHED WEB BUDGET

Web research is required and available to both conditions.

For **every individual task** in both arms, the hard ceiling is:

- **8 individual search queries**
- **12 source follow-up operations**

Count individual operations, not tool-call envelopes. A batched call containing four searches counts as four searches.

Follow-ups include page opens, clicks, finds, direct source fetches, or equivalent source-reading operations.

Unused budget does not transfer between tasks.

SPACE receives no additional searches, source reads, tools, or compute.

Permitted during inference:

- public web search
- opening public webpages
- official/primary sources
- academic papers
- public GitHub repositories and documentation when relevant

Prohibited during inference:

- searching benchmark task IDs
- searching `FreshQA` or `AssistantBench` together with the task text
- benchmark solution/answer pages
- package gold paths
- upstream benchmark datasets
- external LLM judges
- any other Gauntlet skill

---

# 5. VERIFY QUESTION PACK

Fetch only the four permitted files from exact package commit `6cd91b5c447afc7521e404e6167a729673f5b924`.

Verify from the manifest and assignments:

- 40 total tasks
- 20 BASE assignments
- 20 SPACE assignments
- BASE = 10 FreshQA + 10 AssistantBench
- SPACE = 10 FreshQA + 10 AssistantBench
- seed = `2026082503`
- Space blob SHA = `a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`
- web budget = 8 searches + 12 follow-ups per task

Then state:

`QUESTION PACK VERIFIED — GOLD NOT ACCESSED`

Do not fetch any other package file.

---

# 6. BASE PHASE

Run **all 20 BASE tasks before reading Space**.

Frozen order:

1. 10 BASE FreshQA tasks
2. 10 BASE AssistantBench tasks

For every task:

1. research the underlying real-world question normally;
2. obey the 8-search / 12-follow-up ceiling;
3. answer as directly as the benchmark permits;
4. preserve the evidence URLs actually used;
5. record exact resource counts.

Create one prediction object per task:

```json
{
  "id": "...",
  "condition": "BASE",
  "benchmark": "FreshQA or AssistantBench",
  "answer": "exact submitted benchmark answer",
  "evidence_urls": ["..."],
  "search_queries_used": 0,
  "followups_used": 0,
  "response": "optional visible supporting explanation"
}
```

Do not use benchmark gold or answer-key material as evidence.

## Freeze BASE

After all 20 BASE outputs are complete, freeze the exact prediction block. Hash it with SHA-256 if practical.

State exactly:

`BASE COMMITTED — 20 predictions frozen`

After this line, no BASE answer, evidence list, response, or budget count may be changed.

---

# 7. LOAD SPACE

Only after BASE commitment, fetch the exact Git blob from `Kitahl/The-Gauntlet`:

`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

Verify the SHA exactly.

Activate only that Space / Research Discovery specification.

Do not fetch `tools/space_runtime.py`, `tools/scout.py`, or another Gauntlet module. This experiment measures the procedural skill itself, not extra runtime capability.

If the exact blob cannot be verified, stop and report:

`SPACE UNAVAILABLE — frozen skill artifact could not be verified`

---

# 8. SPACE PHASE

Run all 20 SPACE tasks in frozen order:

1. 10 SPACE FreshQA tasks
2. 10 SPACE AssistantBench tasks

Use the exact same web tools and hard budget as BASE.

Space may alter **research strategy only**, such as:

- translating project wording into mechanisms/capabilities;
- query reformulation;
- synonym expansion;
- neighboring-field search;
- source hierarchy/prioritization;
- provenance and derivative-source checking;
- primary-source inspection;
- scoped absence/novelty discipline.

It may not receive additional resource budget.

Do not use BASE answers as evidence.

Create prediction objects using the same schema with `condition: "SPACE"`.

## Freeze SPACE

After all 20 SPACE outputs are complete, freeze the exact prediction block and hash it if practical.

State exactly:

`SPACE COMMITTED — 20 predictions frozen`

Neither arm may be revised afterward.

---

# 9. OPEN GOLD AND SCORE

Only after both exact commitment statements may you access, at package commit `6cd91b5c447afc7521e404e6167a729673f5b924`:

- `benchmarks/session3_test3_space/gold/SEALED_UNTIL_BOTH_ARMS_COMMIT/`
- `benchmarks/session3_test3_space/score.py`
- `benchmarks/session3_test3_space/requirements-score.txt`
- `benchmarks/session3_test3_space/scoring/`

Combine the 40 frozen prediction objects into JSONL.

Install scoring-only dependencies only now if needed.

Do not modify predictions during scoring.

---

# 10. ASSISTANTBENCH SCORING

Score AssistantBench using the vendored official BrowserGym AssistantBench evaluator pinned in the manifest.

Report:

| Condition | Mean score | n | Answer rate |
|---|---:|---:|---:|
| BASE | | 10 | |
| SPACE | | 10 | |

Also report difficulty breakdown where available.

Do not manually override an official AssistantBench score.

---

# 11. FRESHQA SCORING

The package contains the frozen FreshQA answer snapshot captured during package generation.

The package scorer first uses conservative normalized exact matching against all accepted answers in the frozen record.

Any non-exact case must be marked:

`REVIEW_REQUIRED`

rather than silently scored incorrect.

After both arms are frozen and gold is visible, manually adjudicate each `REVIEW_REQUIRED` response against the frozen accepted answers. Preserve the original prediction and record the adjudication/reason separately.

Report:

| Condition | Correct | n | Accuracy | Manual reviews |
|---|---:|---:|---:|---:|
| BASE | | 10 | | |
| SPACE | | 10 | | |

Where sample size permits, also break down by FreshQA metadata such as fact type, hop count, and false-premise status.

---

# 12. RESOURCE ACCOUNTING

For each condition report:

- total search queries;
- total source follow-ups;
- average searches/task;
- average follow-ups/task;
- unique cited source domains;
- number of budget violations.

Any task exceeding either ceiling is marked:

`BUDGET VIOLATION`

Preserve its prediction, but do not present it as a clean matched-budget observation.

---

# 13. FAILURE AUDIT

For every failed task, classify the primary observable research failure where supported:

- query too narrow
- query too broad
- missed synonym
- wrong entity resolution
- missed multi-hop connection
- stopped search too early
- weak source chosen despite available stronger source
- stale source
- unsupported inference
- conflicting evidence mishandled
- false absence/nonexistence claim
- correct source found but answer extracted incorrectly
- answer-format error
- budget exhausted
- other
- unknown

Do not invent a mechanism when uncertain.

For absence claims distinguish:

`NOT FOUND WITHIN SEARCH SCOPE`

from a global claim that something does not exist.

---

# 14. STABILITY AND INTERPRETATION

For FreshQA report:

- first 5 tasks per condition;
- all 10 tasks per condition.

For AssistantBench report:

- first 5 tasks per condition;
- all 10 tasks per condition.

You may also show the descriptive total across the 20 tasks per condition, but label it:

`DESCRIPTIVE CROSS-BENCHMARK TOTAL — NOT AN OFFICIAL BENCHMARK METRIC`

Do not fabricate a single official combined score.

This is a **fresh-session disjoint matched-task exploratory comparison**, not an isolated same-item causal A/B. Report raw results and percentage-point differences. Do not claim general Space efficacy from this sample alone.

---

# 15. VALIDITY AUDIT

Explicitly report:

- fresh session: YES/NO
- exact package commit used: YES/NO
- only four permitted package files accessed before commitments: YES/NO
- gold concealed until BASE commitment: YES/NO
- gold concealed until SPACE commitment: YES/NO
- Space concealed until BASE commitment: YES/NO
- Mirror/FOIL used: MUST BE NO
- other Gauntlet skills used: MUST BE NO
- matched web budgets: YES/NO
- predictions changed after commitment: MUST BE NO
- raw-gold exposure: MUST BE NO
- budget violations
- exclusions
- FreshQA manual-review cases
- scorer uncertainty

If raw gold/reference material appears before both arms commit, the only valid verdict is:

`INVALID / INCONCLUSIVE`

---

# 16. VERDICT

Use exactly one:

`POSITIVE DIRECTION`

`MIXED`

`TIE / NO OBSERVED DIFFERENCE`

`NEGATIVE DIRECTION`

`INVALID / INCONCLUSIVE`

---

# 17. REQUIRED FINAL REPORT

## SESSION / TEST
`Session #3 — Test #3 — Space`

## MODEL
Exact model identity.

## PACKAGE
`6cd91b5c447afc7521e404e6167a729673f5b924`

## FROZEN SPACE
`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

## FRESHQA
BASE and SPACE correct /10, accuracy, delta, manual-review count, metadata breakdown.

## ASSISTANTBENCH
BASE and SPACE mean score, delta, answer rate, difficulty breakdown.

## RESOURCE USE
Searches, follow-ups, and budget violations by condition.

## FAILURES
Every failed task ID with concise failure classification.

## VALIDITY AUDIT
Complete checklist.

## VERDICT
One permitted verdict.

## INTERPRETATION
State only what this 40-task fresh-session experiment actually supports.

---

# EXECUTION RULE

Do not ask me to choose tasks.
Do not regenerate the package.
Do not change assignments.
Do not fetch upstream benchmark datasets directly.
Do not expose gold early.
Do not load Space early.
Do not use Mirror/FOIL.
Run the frozen package exactly as specified.
