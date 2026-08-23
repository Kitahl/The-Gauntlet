# SESSION 1 — BASE CONTROL

Copy everything below into a completely new ChatGPT session.

---

You are running Session 1 of the FOIL vNext5 development experiment for The Gauntlet.

Repository:
`https://github.com/Kitahl/The-Gauntlet`

Starting branch:
`benchmark/paired-diverse-suite`

Follow normal ChatGPT policies and connected-tool rules.

Your job is to:

1. freeze one deterministic five-item benchmark set;
2. commit that frozen item manifest;
3. run those five items under BASE only;
4. save five BASE receipts;
5. stop without scoring.

Do not design or apply FOIL vNext in this session.

## A. Freeze the five-item set

Create branch:

`experiment/foil-vnext5-selection`

from the exact current head of:

`benchmark/paired-diverse-suite`

Use:

- selection seed: `20260902`
- replacement seed: `20260903`

Select exactly one eligible item from each benchmark family:

1. BrowseComp
2. FreshQA
3. GPQA-Diamond
4. ARC-AGI-2
5. HotpotQA

If HotpotQA cannot be reproducibly obtained from an authoritative public source, use a fresh text-only HLE item as the fallback. Record the substitution before inspecting candidate item content.

Selection requirements:

- selection must be deterministic;
- do not choose items based on whether they appear easy or favorable to any condition;
- exclude items previously used by The Gauntlet benchmark pilots;
- for BrowseComp, also exclude all historically sampled rows and all rows already selected for the current BrowseComp-40 prospective experiment;
- for GPQA-Diamond, exclude rows already sampled by the prior GPQA pilot;
- use a fresh ARC-AGI-2 public evaluation task;
- pin the FreshQA source revision/snapshot used;
- pin source revision/hash information where practical.

Create:

`benchmarks/VNEXT5_ITEM_MANIFEST.json`

with this shape:

```json
{
  "schema": "foil-vnext5-item-manifest/v1",
  "selection_seed": 20260902,
  "replacement_seed": 20260903,
  "items": [
    {
      "benchmark": "...",
      "item_id": "...",
      "source": "...",
      "source_revision_or_hash": "...",
      "regime": "...",
      "budget": {},
      "selection_reason": "deterministic eligible sample"
    }
  ]
}
```

Do not include reference answers in this manifest.

Commit the manifest before solving any of the five tasks.

Call that commit:

`SELECTION_FREEZE_SHA`

## B. Run BASE

Create branch:

`experiment/foil-vnext5-base`

from exactly `SELECTION_FREEZE_SHA`.

Run all five selected items in this session under BASE.

BASE means:

- normal competent GPT-5.6 Sol behavior;
- no FOIL procedure;
- no FOIL profile;
- no FOIL vNext;
- no Mastermind procedure.

Normal reasoning is allowed.

### Tool regimes

BrowseComp:
- public web allowed;
- maximum 12 search queries;
- maximum 12 source follow-ups.

FreshQA:
- public web allowed;
- maximum 12 search queries;
- maximum 12 source follow-ups.

GPQA-Diamond:
- closed book;
- no web search.

ARC-AGI-2:
- supplied task examples only;
- no web search.

HotpotQA:
- supplied benchmark context only;
- no general web search.

If HLE fallback is used:
- closed book;
- no web search.

Reference answers are not needed during this session. Keep scoring for the later analysis session.

## C. Save five receipts

For each item create:

`benchmark_runs/2026-08-22/vnext5/base/<benchmark>/<item_id>.json`

Use:

```json
{
  "schema": "foil-vnext5-unit/v1",
  "benchmark": "<benchmark>",
  "item_id": "<item id>",
  "condition": "BASE",
  "answer": "<frozen answer>",
  "confidence": 0.0,
  "tool_counts": {
    "search_queries": 0,
    "source_followups": 0
  },
  "execution_status": "complete"
}
```

Set real confidence and tool counts.

Do not store private reasoning.

Once an answer is written to its receipt, treat it as frozen for this experiment.

Commit all five receipts.

Call that commit:

`BASE_RECEIPT_SHA`

## D. Stop

Do not score.
Do not design vNext.
Do not modify production FOIL.

Your final response must contain only:

- the five benchmark/item IDs;
- `SELECTION_FREEZE_SHA`;
- `BASE_RECEIPT_SHA`;
- tool counts for each item;
- confirmation that all five BASE executions completed.

Do not print the five answers in the final response.