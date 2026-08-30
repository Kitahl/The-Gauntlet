# SESSION 3 — FOIL vNEXT V1 + MASTERMIND

Before using this file, replace:

- `<PASTE_SELECTION_FREEZE_SHA>`
- `<PASTE_VNEXT_SPEC_SHA>`

with the actual values from Sessions 1 and 2.

Then copy everything below into a completely new ChatGPT session.

---

You are running Session 3 of the FOIL vNext5 development experiment for The Gauntlet.

Repository:
`https://github.com/Kitahl/The-Gauntlet`

Selection freeze:
`<PASTE_SELECTION_FREEZE_SHA>`

Frozen vNext specification:
`<PASTE_VNEXT_SPEC_SHA>`

Follow normal ChatGPT policies and connected-tool rules.

Do not inspect the BASE execution branch or receipts.
Do not inspect the vNext-only execution branch or receipts.
Do not modify the frozen vNext candidate.

Your job is to run the same five benchmark items under:

`FOIL_VNEXT_V1_MM`

using the exact frozen vNext candidate plus a bounded Mastermind audit.

## A. Create the execution branch

Create:

`experiment/foil-vnext5-vnext-mm`

from exactly:

`<PASTE_VNEXT_SPEC_SHA>`

Read the frozen candidate implementation/specification but do not change it.

Reconstruct/read the same five items listed in:

`benchmarks/VNEXT5_ITEM_MANIFEST.json`

Do not change the item set.

## B. Solve with frozen vNext

For each of the five items:

1. Run exactly `FOIL_VNEXT_V1` first.
2. Produce a candidate answer.
3. Apply the Mastermind audit below.
4. Freeze the final answer.

Use exactly the same benchmark-specific tool regime and total limits as Sessions 1 and 2.

Mastermind receives no extra web-search or source-follow-up budget.

Reference answers are not needed during this session.

## C. Bounded Mastermind audit

Use at most **3 loops per item**.

One loop is:

1. Identify the earliest plausible defect that could materially make the current candidate wrong.
2. Identify the smallest allowed discriminator that can resolve that defect.
3. Use only the task's permitted evidence/tools and remaining budget.
4. Change the candidate only if the discriminator supports a change.
5. Determine whether a materially distinct unresolved defect remains.

Stop immediately when no materially distinct defect remains.

Do not perform additional loops merely to reach three.

The purpose is to measure whether bounded causal-defect auditing helps after vNext, not to maximize reasoning length.

## D. Tool regimes

Use exactly the regimes frozen in the item manifest.

BrowseComp / FreshQA:
- same maximum search/follow-up budget as the other conditions.

GPQA-Diamond:
- closed book.

ARC-AGI-2:
- supplied task only.

HotpotQA:
- supplied context only.

If HLE fallback was used:
- closed book.

## E. Save five receipts

Create one file per item:

`benchmark_runs/2026-08-22/vnext5/vnext_mm/<benchmark>/<item_id>.json`

Use:

```json
{
  "schema": "foil-vnext5-unit/v1",
  "benchmark": "<benchmark>",
  "item_id": "<item>",
  "condition": "FOIL_VNEXT_V1_MM",
  "answer": "<frozen final answer>",
  "confidence": 0.0,
  "tool_counts": {
    "search_queries": 0,
    "source_followups": 0
  },
  "policy_trace": {
    "task_regime": "<vNext regime>",
    "primary_effort_mode": "<mode>",
    "mastermind_loops_used": 0,
    "mastermind_changed_answer": false,
    "stop_reason": "<short operational label>"
  },
  "execution_status": "complete"
}
```

Use real values.

Do not store private reasoning or full audit text.

Commit all five receipts.

Call the commit:

`VNEXT_MM_RECEIPT_SHA`

## F. Stop

Do not inspect BASE results.
Do not inspect vNext-only results.
Do not score.
Do not modify the frozen candidate.

Final response must contain only:

- `VNEXT_MM_RECEIPT_SHA`;
- the five benchmark/item IDs;
- Mastermind loops used for each item;
- whether Mastermind changed each candidate answer;
- tool counts for each item;
- confirmation that BASE and vNext-only outputs were not inspected.

Do not print the five answers.