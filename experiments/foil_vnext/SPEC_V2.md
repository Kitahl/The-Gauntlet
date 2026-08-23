# FOIL vNext Candidate V2 — Evidence-Gated Minimum Complement

Candidate identifier: `FOIL_vNEXT_CANDIDATE_V2`

Status: **experimental / behavioral efficacy open**.

V2 preserves permanent FOIL v0.4.0 and the frozen V1 candidate. It changes only the experimental runtime-policy hypothesis.

## Design target

Choose the smallest task-relevant complement justified by current task evidence and independently supported user evidence. More profile detail, more reasoning, more critique, or more verification is not automatically better.

## Changes from V1

1. **No benchmark-name routing.** `benchmark` is receipt metadata only. Task properties determine regime, so a benchmark label cannot silently select a strategy.
2. **Directional profile evidence.** Profile evidence is explicitly `strength`, `gap`, or `uncertain`.
3. **Task-matched complements.** A profile gap can act only when its concrete complement is required by the current task.
4. **Changed-context evidence required.** Profile-triggered intervention requires at least one transfer confirmation in addition to independent observations.
5. **Strengths do not trigger help.** Strong evidence that the user already supplies a capability suppresses profile intervention rather than manufacturing extra assistance.
6. **Wrong-profile negative control.** A strong profile gap in a capability the task does not require must not alter routing.
7. **Minimal intervention.** At most one targeted profile complement is emitted per decision.
8. **Anti-overthinking.** If a viable answer exists, decisive uncertainties are resolved, and mandatory verifiers are complete, V2 stops and suppresses profile intervention.

## Preserved invariants

- Relevance is not competence.
- Assisted success is not independent capability.
- Current task obligations override profile evidence.
- Stale or weak evidence cannot control routing.
- Confidence does not discharge unresolved decisive uncertainty.
- Verification is claim-native.
- Fixed tool ceilings are never increased by the policy.
- Public traces contain policy state, not private chain-of-thought.
- No benchmark answer memory or self-modification is permitted.

## Runtime objects

`runtime_policy_v2.py` defines:

- `TaskContext`: task properties and explicit requirements;
- `LoadBearingUncertainty`: unresolved decisive claim;
- `ProfileSignal`: profile evidence direction, evidence strength, transfer support, and concrete complement;
- `PolicyDecision`: task regime, verifier schedule, targeted complement, resource allocation, stop state, and public trace.

## Task-regime classification

Runtime classification uses task properties only:

- freshness-sensitive retrieval;
- closed-context multi-hop;
- abstract transformation;
- closed-book technical reasoning;
- external retrieval;
- mixed/tool fallback.

The same task properties must produce the same policy inside and outside a benchmark.

## Claim-native verification

| Claim | Verifier |
| --- | --- |
| external fact | source evidence |
| fresh fact | current source |
| numeric | exact calculation |
| supplied-example rule | consistency against supplied examples |
| executable/code | execution test |
| logical/general | contradiction/counterexample |
| output contract | output-contract check |

## Task complement inference

Current unresolved claims can imply capabilities relevant to the task. Examples:

- external/fresh facts → evidence discipline / tool selection;
- numeric claim → quantitative check;
- executable claim → implementation/execution;
- logical claim → formalization / error detection;
- supplied-example transformation → transfer/adaptation / error detection.

Callers may also supply explicit `required_complements` when the task demand is known directly.

## Profile gate

Profile evidence is first assigned a conservative engineering evidence tier. These thresholds are not psychometric cut scores.

A profile route is allowed only if all are true:

1. evidence tier is at least moderate;
2. evidence direction is `gap`;
3. the gap names a concrete complement;
4. at least one changed-context/transfer confirmation exists;
5. the complement is required by the current task;
6. the task is not already complete.

Therefore these must not route:

- no profile;
- stale profile;
- weak profile;
- strong `strength` evidence;
- strong but irrelevant gap;
- strong gap with no transfer confirmation;
- any profile after the stop condition is satisfied.

## Stop rule

Stop iff:

1. a viable candidate exists;
2. no decisive uncertainty remains;
3. every mandatory verifier is complete.

A profile cannot force an additional review after this condition is reached.

## Evidence boundary

V2 establishes an executable deterministic policy and negative-control invariants. It does **not** establish that profile-driven complements improve human or model performance. The production recommendation remains `VALID_IMPLEMENTATION / BEHAVIORAL_EFFICACY_OPEN` until prospective paired evidence shows benefit at matched total cost.

## Required causal test before promotion

Compare on identical isolated items:

- BASE;
- generic FOIL;
- V2 without profile;
- V2 with correct frozen profile;
- V2 with deliberately wrong/shuffled profile.

A personalization claim requires, at minimum, evidence that correct-profile V2 beats or meaningfully improves upon no-profile V2 and does not behave equivalently to wrong-profile V2. Null and negative results must be retained.
