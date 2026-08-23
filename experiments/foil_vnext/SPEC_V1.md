# FOIL vNext Candidate V1 — Frozen Runtime Policy Specification

Candidate identifier: `FOIL_vNEXT_CANDIDATE_V1`

## Purpose

This experimental candidate fills a narrow gap between FOIL's existing profile/task evidence and the solving/research strategy actually selected at runtime. It does **not** redesign Layer 1 or Layer 2, modify permanent FOIL files, add Mastermind, train model weights, or optimize against the five evaluation answers.

The controller is deliberately small and deterministic. The unit of adaptation is the **current task**, not a persistent benchmark-specific prompt or workflow.

## Preserved FOIL invariants

1. Domain/facet relevance is not competence.
2. Assisted success is not independent capability.
3. Current task evidence and hard evidence obligations override stale profile evidence.
4. Weak or stale profile evidence cannot control routing.
5. Uncertainty is represented explicitly; confidence alone does not discharge a decisive uncertainty.
6. Verification is claim-native rather than generic self-critique.
7. More assistance is not automatically better; stop when decisive obligations are discharged.
8. Public traces contain policy state only, not private reasoning or chain-of-thought.
9. The frozen candidate does not learn, self-modify, or accumulate benchmark answer memories during evaluation.

## Runtime state

`runtime_policy.py` defines explicit immutable objects:

- `TaskContext`: task signals, candidate state, confidence, supplied examples, completed verifiers, unresolved load-bearing uncertainties.
- `LoadBearingUncertainty`: a decisive unresolved claim plus claim type and resolved flag.
- `ProfileSignal`: relevance, support, independent-observation count, transfer-confirmation count, staleness.
- `PolicyDecision`: regime, effort mode, verifier schedule, actions, resource allocation, profile influence, stop state, and public trace.

## 1. Task regime

The controller uses the following regimes:

- `external_retrieval`
- `freshness_sensitive_retrieval`
- `closed_book_technical_reasoning`
- `abstract_transformation`
- `closed_context_multi_hop`
- `mixed_tool_task`

Precedence is deterministic: benchmark-family mapping when supplied, otherwise freshness; closed-context multi-hop; abstract transformation; closed-book technical reasoning; external retrieval; mixed fallback.

The benchmark-family mapping is fixed before evaluation exposure:

- BrowseComp -> external retrieval
- FreshQA -> freshness-sensitive retrieval
- GPQA / GPQA-Diamond -> closed-book technical reasoning
- ARC-AGI-2 -> abstract transformation
- HotpotQA -> closed-context multi-hop

This maps known benchmark **families**, not selected item contents.

## 2. Load-bearing uncertainties

Only uncertainties capable of changing the answer are tracked as load-bearing. Each is typed by the claim it affects. The public trace stores only the count of unresolved decisive uncertainties.

High subjective answer confidence does not resolve an uncertainty.

## 3. Adaptive effort allocation

Within any benchmark-fixed external tool ceiling, vNext reallocates effort rather than increasing the ceiling:

- Retrieval with no viable candidate: discovery priority (`search_query_priority=3`, `source_followup_priority=1`).
- Retrieval with a viable candidate and unresolved obligations: decisive verification priority (`1`, `3`).
- Closed-book technical, abstract-transformation, and closed-context tasks: external retrieval disabled unless the task is explicitly classified mixed.
- Mixed/tool tasks: balanced external allocation (`2`, `2`).

`next_external_action()` deterministically prefers search during discovery and source follow-up during verification while obeying the fixed ceiling.

## 4. Claim-matched verifier selection

Uncertainty claim types map to verifiers:

| Claim type | Verifier |
| --- | --- |
| external fact / identity | source evidence |
| current/fresh fact | current source |
| numeric | exact calculation |
| rule over supplied examples | supplied-example consistency |
| executable/code behavior | execution test |
| logical/general claim | contradiction/counterexample |
| output format | output-contract check |

Regime-level hard obligations are added even without an explicit uncertainty:

- freshness-sensitive retrieval always requires a current-source check;
- abstract transformation with supplied examples always requires checking the candidate rule against those examples;
- explicit output contracts always require an output-contract check.

## 5. Profile influence gate

Profile routing is allowed only when relevance, support, and independent evidence all clear fixed thresholds. Stale evidence produces no influence. Weak evidence may be recorded as `low` but cannot alter routing.

Moderate/high profile evidence may add only an optional support action. It cannot change the task regime, remove a verifier, authorize prohibited retrieval, or turn assisted evidence into independent capability.

## 6. Stop / anti-overthinking rule

Stop iff all three are true:

1. a viable answer/candidate exists;
2. no decisive uncertainty remains unresolved;
3. all mandatory verifiers are completed.

When this condition holds the policy emits `STOP` and does not add a generic review/critique pass. When it does not hold, the stop reason is an operational `continue_*` label.

## 7. Regime actions

- External retrieval: discover candidates, then verify the viable candidate.
- Freshness retrieval: prefer current source, then discover/verify.
- Closed-book technical: reason without external retrieval.
- Abstract transformation: induce a candidate rule; once one exists, check it against every supplied example.
- Closed-context multi-hop: decompose over supplied evidence; do not browse merely because browsing is available.
- Mixed/tool: combine tools and reasoning.

## 8. Trace boundary

The receipt-compatible public trace is exactly:

- task regime;
- unresolved load-bearing uncertainty count;
- profile influence (`none|low|moderate|high`);
- primary effort mode (`discovery|reasoning|verification|mixed`);
- short operational stop reason.

No scratchpad, hidden reasoning, private chain-of-thought, benchmark reference answer, or evaluator feedback is stored.

## 9. Freeze/evaluation rule

After this specification and implementation are committed as `VNEXT_SPEC_SHA`, no candidate code, thresholds, mappings, tests, or policy rules may change during the five-item evaluation. Evaluation may instantiate task state and execute the frozen policy, but it may not edit the policy.
