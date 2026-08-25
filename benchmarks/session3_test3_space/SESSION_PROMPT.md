# SESSION #3 — TEST #3 — SPACE VS BASE

Run the frozen package as a **fresh-session comparison of GPT-5.6 Sol BASE versus the frozen Space / Research Discovery skill**.

## Frozen package reference

Repository: `Kitahl/The-Gauntlet`

Package commit: `__PACKAGE_COMMIT__`

Development branch: `benchmark/session3-test3-space-package`

Test folder: `benchmarks/session3_test3_space/`

Frozen Space blob: `a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

The package contains 40 unique web-research tasks:

- 20 FreshQA tasks total
- 20 AssistantBench validation tasks total
- BASE: 10 FreshQA + 10 AssistantBench
- SPACE: 10 FreshQA + 10 AssistantBench

Do not alter the frozen assignment.

---

# ABSOLUTE GOLD BOUNDARY

Before **both BASE and SPACE prediction receipts are committed**, you may fetch only these four package files at the exact frozen package commit:

- `benchmarks/session3_test3_space/MANIFEST.json`
- `benchmarks/session3_test3_space/assignments.json`
- `benchmarks/session3_test3_space/questions/freshqa_questions.jsonl`
- `benchmarks/session3_test3_space/questions/assistantbench_questions.jsonl`

Do **not** list or recursively fetch the package directory.

Do **not** inspect any path containing:

`gold/SEALED_UNTIL_BOTH_ARMS_COMMIT`

Before both arms commit, also do not inspect:

- `build_package.py`
- `validate_package.py`
- `score.py`
- `requirements-score.txt`
- `scoring/`
- workflow files or workflow logs
- Git history or commit diffs for this package
- prior Test #3 traces

If any benchmark answer, gold URL, explanation, reference answer, scorer output, or other answer-key material enters model-visible context before both arms are committed, stop immediately and report exactly:

`INVALID — RAW GOLD EXPOSURE`

No comparative result may then be reported.

---

# MODEL

Intended model: **GPT-5.6 Sol**.

Record the active model identity if available. If materially different, report:

`INVALID CONFIG — intended model GPT-5.6 Sol`

---

# PROHIBITED COMPONENTS

Before BASE commitment, do not read or reconstruct Space from prior context.

Throughout inference do not use:

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

SPACE may use **only** the exact frozen Space skill after BASE commitment.

---

# TOOL POLICY AND MATCHED BUDGET

Web research is required and available to both conditions.

For **every task in both conditions**, the hard ceiling is:

- **8 individual search queries**
- **12 source follow-up operations**

Count individual operations, not tool-call envelopes. Four search records in one batched call count as four searches.

Follow-ups include page opens, clicks, finds, direct source fetches, or equivalent source-reading operations.

Unused budget does not transfer between tasks.

SPACE gets no additional searches or source reads.

Permitted during inference:

- public web search
- opening public webpages
- primary papers and official sources
- GitHub/repositories when relevant to the task
- public documentation

Prohibited during inference:

- searching benchmark task IDs
- searching `FreshQA` or `AssistantBench` together with task text
- benchmark solutions or answer keys
- package gold paths
- external LLM judges
- other Gauntlet skills

---

# PHASE 1 — VERIFY QUESTION PACK

Fetch only the four permitted files from package commit `__PACKAGE_COMMIT__`.

Verify from the manifest/assignments:

- 40 total tasks
- 20 BASE assignments
- 20 SPACE assignments
- each condition has 10 FreshQA and 10 AssistantBench tasks
- deterministic seed `2026082503`
- frozen Space SHA matches `a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

State:

`QUESTION PACK VERIFIED — GOLD NOT ACCESSED`

Do not fetch any other package file.

---

# PHASE 2 — BASE

Run **all 20 BASE tasks before reading Space**.

Order:

1. 10 BASE FreshQA tasks in frozen condition order
2. 10 BASE AssistantBench tasks in frozen condition order

For each task:

1. research the underlying real-world question normally;
2. obey the 8-search / 12-follow-up ceiling;
3. prefer strong sources where naturally appropriate, but do not apply a memorized Space checklist;
4. return the benchmark answer as directly as possible;
5. preserve the evidence URLs actually used.

Create one prediction record per task:

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

Do not use benchmark gold as evidence.

---

# FREEZE BASE

After all 20 BASE tasks are complete, freeze the exact prediction block.

Hash it with SHA-256 if practical.

State exactly:

`BASE COMMITTED — 20 predictions frozen`

After that statement, no BASE answer, URL list, or budget count may be altered.

---

# PHASE 3 — LOAD SPACE

Only after BASE commitment, fetch the exact Git blob from `Kitahl/The-Gauntlet`:

`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

Verify the SHA exactly.

Activate only that Space / Research Discovery specification.

Do not fetch `tools/space_runtime.py`, `tools/scout.py`, or another Gauntlet skill. This test measures the procedural skill, not extra runtime capability.

If the exact blob cannot be verified, stop and report:

`SPACE UNAVAILABLE — frozen skill artifact could not be verified`

---

# PHASE 4 — SPACE

Run all 20 SPACE tasks in frozen order:

1. 10 SPACE FreshQA tasks
2. 10 SPACE AssistantBench tasks

Use the same web tools and exact same per-task budget as BASE.

Space may change **research strategy only**, including query reformulation, mechanism/capability translation, synonym expansion, source prioritization, neighboring-field search, provenance checking, and scope discipline.

It may not receive extra searches or source reads.

Do not use BASE answers as evidence.

Create prediction records in the same schema with `condition: "SPACE"`.

---

# FREEZE SPACE

After all 20 SPACE tasks are complete, freeze the exact prediction block and hash it if practical.

State exactly:

`SPACE COMMITTED — 20 predictions frozen`

Neither condition may be revised afterward.

---

# PHASE 5 — GOLD MAY NOW BE OPENED

Only after both exact commitment statements may you access:

`benchmarks/session3_test3_space/gold/SEALED_UNTIL_BOTH_ARMS_COMMIT/`

You may now also access:

- `score.py`
- `requirements-score.txt`
- `scoring/`

at package commit `__PACKAGE_COMMIT__`.

Combine the 40 frozen predictions into JSONL.

Install scoring-only dependencies only now if necessary.

Run the package scorer.

---

# ASSISTANTBENCH SCORING

AssistantBench must be scored with the vendored official BrowserGym AssistantBench evaluator pinned in the package manifest.

Report separately:

| Condition | Mean score | n | Answer rate |
|---|---:|---:|---:|
| BASE | | 10 | |
| SPACE | | 10 | |

Also report difficulty breakdown where available.

Do not manually override official AssistantBench scores.

---

# FRESHQA SCORING

The package contains the frozen FreshQA answer set captured at package-build time.

The scorer first performs conservative normalized exact matching against all supplied acceptable answers.

For any non-exact result it must return:

`REVIEW_REQUIRED`

rather than silently marking a semantic variant wrong.

After both arms are committed and gold is visible, adjudicate each `REVIEW_REQUIRED` item against the frozen answer set. Record the adjudication explicitly as correct or incorrect and preserve the reason.

Do not change the original prediction.

Report:

| Condition | Correct | n | Accuracy | Manual reviews |
|---|---:|---:|---:|---:|
| BASE | | 10 | | |
| SPACE | | 10 | | |

Also report results by available FreshQA metadata such as fact type, hop count, and false-premise status.

---

# RESOURCE ACCOUNTING

For each condition report:

- total search queries
- total source follow-ups
- average searches per task
- average follow-ups per task
- unique cited source domains
- budget violations

Any task exceeding either resource ceiling is marked:

`BUDGET VIOLATION`

Preserve its prediction but do not silently treat it as a clean matched-budget observation.

---

# FAILURE AUDIT

For every failed task, classify the primary observable research failure when possible:

- query too narrow
- query too broad
- missed synonym
- wrong entity resolution
- missed multi-hop connection
- stopped search too early
- weak source selected over available primary source
- stale source
- unsupported inference
- conflicting evidence mishandled
- false absence / nonexistence claim
- correct source found but answer extracted incorrectly
- answer formatting error
- budget exhausted
- other
- unknown

Do not force an attribution when evidence is insufficient.

---

# ABSENCE-CLAIM AUDIT

If either condition claims that something does not exist or cannot be found, distinguish:

`NOT FOUND WITHIN SEARCH SCOPE`

from a global nonexistence claim.

An unsupported global absence claim is a research failure even if the final answer happens to match by luck.

---

# STABILITY VIEWS

For each benchmark report:

- first 5 tasks per condition
- all 10 tasks per condition

Also give the descriptive 20-task condition total, but label it:

`DESCRIPTIVE CROSS-BENCHMARK TOTAL — NOT AN OFFICIAL BENCHMARK METRIC`

Do not combine the two benchmark native metrics into a fabricated official score.

---

# STATISTICAL INTERPRETATION

This is a fresh-session, disjoint matched-task exploratory comparison, not an isolated same-item causal A/B.

Report raw scores and percentage-point differences. Use uncertainty descriptively. Do not make a general efficacy claim from 10 tasks per benchmark per condition.

---

# VALIDITY AUDIT

Explicitly report:

- fresh session: YES/NO
- exact package commit used: YES/NO
- only permitted question files accessed before commitments: YES/NO
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
- scorer uncertainty / FreshQA review cases

If raw gold appears early, the only valid verdict is:

`INVALID / INCONCLUSIVE`

---

# VERDICT

Use exactly one:

`POSITIVE DIRECTION`

`MIXED`

`TIE / NO OBSERVED DIFFERENCE`

`NEGATIVE DIRECTION`

`INVALID / INCONCLUSIVE`

---

# REQUIRED FINAL REPORT

## SESSION / TEST
`Session #3 — Test #3 — Space`

## MODEL
Exact model identity.

## PACKAGE
`__PACKAGE_COMMIT__`

## FROZEN SPACE
`a1d91b1d49ac6667f53ed7dfba14d8acb7fe849d`

## FRESHQA
BASE and SPACE correct /10, accuracy, delta, review count, metadata breakdown.

## ASSISTANTBENCH
BASE and SPACE mean score /10, delta, answer rate, difficulty breakdown.

## RESOURCE USE
Searches and follow-ups by condition.

## FAILURES
Every failed task ID and concise failure classification.

## VALIDITY AUDIT
Complete checklist.

## VERDICT
One permitted verdict.

## INTERPRETATION
State only what this 40-task fresh-session experiment supports.

Do not claim general Space efficacy from this experiment alone.

---

# EXECUTION RULE

Do not ask me to choose questions.
Do not regenerate the package.
Do not change assignments.
Do not fetch benchmark source datasets directly.
Do not expose gold early.
Do not load Space early.
Do not use Mirror/FOIL.
Run the frozen package exactly as specified.
