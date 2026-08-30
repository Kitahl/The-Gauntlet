# SESSION 2 — FOIL vNEXT V1

Before using this file, replace:

`<PASTE_SELECTION_FREEZE_SHA>`

with the actual value from Session 1.

Then copy everything below into a completely new ChatGPT session.

---

You are running Session 2 of the FOIL vNext5 development experiment for The Gauntlet.

Repository:
`https://github.com/Kitahl/The-Gauntlet`

Selection freeze:
`<PASTE_SELECTION_FREEZE_SHA>`

Follow normal ChatGPT policies and connected-tool rules.

Do not inspect the BASE execution branch or BASE receipts.

Your job is to:

1. study current FOIL and relevant prior art;
2. design the smallest useful experimental FOIL vNext runtime-policy upgrade;
3. implement and test it under an experimental path;
4. freeze it before reading the five benchmark question contents;
5. run the same five items with the frozen vNext candidate;
6. save five vNext receipts;
7. stop without scoring.

## A. Create the vNext design branch

Create:

`experiment/foil-vnext5-vnext-spec`

from exactly:

`<PASTE_SELECTION_FREEZE_SHA>`

Do not reconstruct or read the five selected question contents yet.

## B. Inspect current FOIL

At minimum inspect:

- `tools/foil_profile.py`
- `tools/foil_hook.py`
- `tools/foil_assessment.py`
- `tools/foil_layer2.py`
- `tools/foil_calibration.py`
- `tools/foil_domains.py`
- `docs/FOIL_ONBOARDING.md`
- `docs/FOIL_DEEP_CALIBRATION.md`
- `research/FOIL_PERSONALIZATION_BASIS.md`
- `validation/FOIL_LAYER2_MASTERMIND_AUDIT.md`
- current benchmark receipts and `docs/BENCHMARKS.md`

Do not redesign the personalization/calibration layers merely because they exist.

Focus on the runtime-policy gap between task/profile evidence and the actual strategy used on a current task.

## C. Inspect relevant external code

Use current web/GitHub research and inspect executable repositories for mechanisms relevant to FOIL.

At minimum check:

- DSPy: GEPA, MIPROv2, SIMBA
- TextGrad
- metaTextGrad
- AgentSquare
- AFlow
- Agent Lightning
- Reflexion
- SiriuS

Search for newer directly relevant systems if useful.

For each useful system record briefly:

- what it optimizes;
- whether it changes prompts, workflow, tools, memory, or model weights;
- feedback signal used;
- relevant repository/file/class/function;
- license;
- mechanism that may transfer to FOIL;
- reason not to copy it if its objective conflicts with FOIL.

FOIL's goal is not benchmark maximization alone. Preserve its evidence, uncertainty, assistance, transfer, and personalization boundaries.

## D. Design FOIL_VNEXT_CANDIDATE_V1

The candidate should be the smallest coherent runtime controller justified by existing evidence.

Prioritize these mechanisms:

1. **Task regime**
   Classify the task into a small actionable regime such as external retrieval, freshness retrieval, closed-book technical reasoning, abstract transformation, closed-context multi-hop, or mixed/tool task.

2. **Load-bearing uncertainties**
   Track only uncertainties that can materially change the answer.

3. **Adaptive effort allocation**
   If no viable candidate exists, favor discovery. Once a viable candidate exists, shift to decisive verification. Do not verify mechanically.

4. **Verifier selection**
   Match the check to the claim: current source, calculation, example consistency, execution, contradiction/counterexample, or output-format check.

5. **Profile influence gate**
   Weak, stale, or merely relevant profile evidence must not dominate current-task evidence.

6. **Stop policy**
   Stop once load-bearing uncertainties are resolved sufficiently for the task. Avoid critique or extra tool use merely because they are available.

7. **Operational trace**
   Record selected regime, effort mode, profile influence, uncertainty count, and stop reason.

Do not add Mastermind to V1. Mastermind is Session 3.

## E. Implement experimentally

Do not replace production FOIL files.

Create:

- `experiments/foil_vnext_candidate_v1/SPEC.md`
- `experiments/foil_vnext_candidate_v1/runtime_policy.py`
- `experiments/foil_vnext_candidate_v1/trace_schema.json`
- `tests/test_foil_vnext_candidate_v1.py`
- `research/FOIL_VNEXT_V1_PRIOR_ART_NOTE.md`

The runtime policy should use explicit state/objects where practical rather than being only prose.

Add tests for at least:

- retrieval with no candidate -> discovery priority;
- retrieval with candidate -> decisive verification;
- freshness task -> current-source preference;
- closed-book task -> no unnecessary retrieval;
- abstract transformation -> candidate rule checked against examples;
- closed-context multi-hop -> reason over supplied evidence;
- weak profile evidence -> little/no profile influence;
- unresolved decisive uncertainty -> verification required;
- decisive uncertainties resolved -> stop.

Run the relevant tests.

Commit the candidate before reading any of the five selected question contents.

Call that commit:

`VNEXT_SPEC_SHA`

The candidate is now frozen for Sessions 2 and 3.

## F. Execute the five items

Create:

`experiment/foil-vnext5-vnext`

from exactly `VNEXT_SPEC_SHA`.

Now reconstruct/read the five items in:

`benchmarks/VNEXT5_ITEM_MANIFEST.json`

Run all five under exactly:

`FOIL_VNEXT_V1`

Use the same tool regime and limits specified in the manifest/Session 1.

Do not use Mastermind.
Do not change the candidate between items.
Reference answers are not needed during this session.

## G. Save five receipts

Create one file per item:

`benchmark_runs/2026-08-22/vnext5/vnext/<benchmark>/<item_id>.json`

Use:

```json
{
  "schema": "foil-vnext5-unit/v1",
  "benchmark": "<benchmark>",
  "item_id": "<item>",
  "condition": "FOIL_VNEXT_V1",
  "answer": "<frozen answer>",
  "confidence": 0.0,
  "tool_counts": {
    "search_queries": 0,
    "source_followups": 0
  },
  "policy_trace": {
    "task_regime": "<regime>",
    "load_bearing_uncertainty_count": 0,
    "profile_influence": "none|low|moderate|high",
    "primary_effort_mode": "discovery|reasoning|verification|mixed",
    "stop_reason": "<short operational label>"
  },
  "execution_status": "complete"
}
```

Use real values. Do not store private reasoning.

Commit all five receipts.

Call the commit:

`VNEXT_RECEIPT_SHA`

## H. Stop

Do not inspect BASE receipts.
Do not score.
Do not run Mastermind.
Do not change `VNEXT_SPEC_SHA`.

Final response must contain only:

- `VNEXT_SPEC_SHA`;
- `VNEXT_RECEIPT_SHA`;
- the five benchmark/item IDs;
- selected task regime for each item;
- tool counts for each item;
- confirmation that the candidate was frozen before the five question contents were read.

Do not print the five answers.