# FOIL vNext5 — Step-by-Step Runbook

Purpose: collect a small, clean development dataset to improve FOIL without changing the treatment during testing.

## What you will run

You will use **3 new ChatGPT sessions** on the **same 5 benchmark items**:

1. **Session 1 — BASE**: solve the 5 items with normal GPT-5.6 Sol behavior.
2. **Session 2 — FOIL vNext**: first design and freeze an experimental FOIL vNext candidate, then solve the same 5 items with it.
3. **Session 3 — FOIL vNext + Mastermind**: solve the same 5 items with the exact frozen vNext candidate plus a bounded Mastermind audit.

After those three sessions, use a **fourth analysis session** to score the 15 runs, research comparable systems, run Mastermind design loops, and propose FOIL vNext V2.

The five items are development data. They are not held-out validation for the later V2 candidate.

## The five benchmark families

The same one item from each family is used in all three sessions:

1. BrowseComp — obscure open-web discovery.
2. FreshQA — freshness / temporal factual retrieval.
3. GPQA-Diamond — closed-book technical reasoning.
4. ARC-AGI-2 — abstract transformation and generalization.
5. HotpotQA — closed-context multi-hop reasoning.

If HotpotQA cannot be reproducibly fetched from an authoritative source, Session 1 must use text-only HLE as the fallback and record that substitution before reading candidate item content.

## Exact order

### Step 1
Open a completely new ChatGPT session.

Copy the entire contents of:

`experiments/foil_vnext5/01_BASE_PROMPT.md`

Run it.

At the end, copy these values into `experiments/foil_vnext5/PROGRESS.md`:

- `SELECTION_FREEZE_SHA`
- `BASE_RECEIPT_SHA`

Do **not** copy the BASE answers into later prompts.

### Step 2
Open another completely new ChatGPT session.

Before sending the prompt, replace:

`<PASTE_SELECTION_FREEZE_SHA>`

in:

`experiments/foil_vnext5/02_VNEXT_PROMPT.md`

with the actual `SELECTION_FREEZE_SHA` from Session 1.

Paste the whole prompt and run it.

At the end, copy these values into `PROGRESS.md`:

- `VNEXT_SPEC_SHA`
- `VNEXT_RECEIPT_SHA`

Do not give Session 2 the BASE answers.

### Step 3
Open another completely new ChatGPT session.

In:

`experiments/foil_vnext5/03_VNEXT_MM_PROMPT.md`

replace:

- `<PASTE_SELECTION_FREEZE_SHA>`
- `<PASTE_VNEXT_SPEC_SHA>`

with the real values.

Paste the whole prompt and run it.

At the end, record:

- `VNEXT_MM_RECEIPT_SHA`

### Step 4 — analysis only after all 3 conditions are complete
Open a fourth new ChatGPT session.

In:

`experiments/foil_vnext5/04_ANALYSIS_PROMPT.md`

replace all four SHA placeholders from `PROGRESS.md`.

Run it.

This analysis session may inspect all three condition results and benchmark references. It should produce the design evidence for FOIL vNext V2.

## Important rules

- Never change the five selected items between conditions.
- Never change FOIL vNext after `VNEXT_SPEC_SHA` while running Sessions 2 or 3.
- Session 2 must not inspect BASE outputs.
- Session 3 must not inspect BASE or vNext-only outputs.
- Use the same benchmark-specific tool regime in all conditions.
- Do not expose private chain-of-thought. Store only answers, operational traces, counts, decisions, and short failure labels.
- Do not claim general FOIL improvement from five items.

## Expected final data

15 execution receipts total:

- 5 × BASE
- 5 × FOIL_VNEXT_V1
- 5 × FOIL_VNEXT_V1_MM

The analysis session then compares correctness, confidence, cost, routing decisions, and Mastermind intervention effects item-by-item.