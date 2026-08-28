# FOIL Smart-Tool Value Update

**Date:** 2026-08-27
**Status:** PARTIAL V1 IMPLEMENTATION / BENCHMARK-ONLY / UNPROMOTED
**Scope:** FOIL only. No Gauntlet or Mastermind code or control-plane merge.
**Supersedes:** the binary `TOOLS_OFF` versus unrestricted `TOOLS_ON` benchmark design.
**Does not supersede:** FOIL's authority boundaries, A0 preservation law, generated-evidence admission rules, or caller-supplied benchmark budgets.

## 0. Implementation boundary (2026-08-28)

The one-tool vertical slice is implemented: strict contracts and receipts,
question-only opportunity discovery, three bounded families, an evidence- and
cost-aware prelaunch gate, caller-supplied token reservations, and active
benchmark `VERIFY` execution through the shared A0-preserving finalizer.
Mechanical extraction remains generated and unadmitted; changing a benchmark
prediction requires an explicit harness opt-in. Retrieval is support-only.

Not implemented in this slice: dependency-complete bundles, tool combinations,
parallel DAG execution, marginal multi-call stopping, learned interaction terms,
production routing, or promotion. The 12-row synthetic integration diagnostic
proves wiring only. The historical HLE replay preserved the 11/59 baseline with
zero rescues and zero damages while executing three zero-token exact checks; it
does not establish HLE efficacy. See
`benchmarks/protocols/FOIL_SMART_TOOL_ACTIVE_VERIFY_V1.md` for the frozen
contract and non-claims.

## 1. Executive decision

FOIL will replace indiscriminate tool access with a **causal, cost-aware, evidence-gated smart-tool controller**.

The controller will:

1. determine which capabilities could causally fill the task's missing information or verification gap;
2. construct the smallest dependency-complete tool bundles that could fill that gap;
3. estimate each bundle's probability of rescue, probability of damage, and full execution cost from frozen receipts rather than model self-confidence;
4. select a bundle only when a conservative lower bound on its expected value is positive;
5. execute independent calls concurrently and dependent calls in order;
6. stop as soon as the marginal value of another tool no longer exceeds its cost;
7. admit tool-derived changes only through FOIL's existing evidence contract.

This is a new FOIL integration, not a claim that its components are new research. It combines established ideas from Causal Minimal Tool Filtering, CAM-DF, CATP-LLM, LLMCompiler, and BATS under FOIL's stricter evidence and authority model.

## 2. Why this update is necessary

### 2.1 Measured problem

The latest small HLE tool experiment reported:

- `FOIL, no tools`: **2.367x** aggregate token multiplier;
- `FOIL + unrestricted tools`: **15.978x** aggregate token multiplier;
- **151 tool calls**;
- four reported rescues, no published answer damages, and one correct A0 withheld;
- benefit concentrated in only two distinct questions repeated across model configurations.

These measurements are diagnostic, not a promotion result. The arms were small and partly confounded, and repeated model configurations are not independent questions. Nevertheless, they establish the engineering failure clearly: unrestricted tool access can find missing facts, but it spends far too many tokens and calls.

### 2.2 Root causes

FOIL currently has pieces of adaptive routing, but it does not yet have a complete smart-tool decision system:

- task policy can identify retrieval-sensitive or verification-sensitive regimes;
- adaptive routing can recommend `DIRECT`, `VERIFY`, or `FULL`;
- tool policy can choose an available provider by priority;
- the benchmark harness has sometimes forced `FULL`, bypassing the intended adaptive decision;
- no component estimates the **incremental correctness value** of a tool or tool bundle;
- no component learns when to stop acquiring tools;
- no component prices complementary tools jointly;
- exposing or repeatedly calling many tools increases prompt, observation, and reasoning tokens.

The problem is therefore not "tools or no tools." The problem is **which minimal evidence-producing bundle is worth buying for this task, and when should FOIL stop?**

## 3. Prior-art basis

The update adopts rather than reinvents the following mechanisms:

1. **Causal Minimal Tool Filtering (CMTF):** represent tools with lightweight precondition/effect contracts and expose only the minimal next-step frontier. Its published synthetic experiment reported roughly 90% lower token usage than exposing all tools. This result is not assumed to transfer numerically to FOIL.
   Source: <https://github.com/R-Suresh/ToolChoiceConfusion>

2. **CAM-DF / CAM-DF-lite:** learn whether to stop acquiring tools by targeting downstream stop-versus-continue payoff, including heterogeneous tool costs. It reported 37% fewer exposed tools with comparable task success in its live evaluation.
   Source: <https://arxiv.org/abs/2607.27083>

3. **CATP-LLM / OpenCATP:** represent multi-tool plans as sequential or non-sequential dependency graphs and optimize task performance against execution cost.
   Source: <https://github.com/duowuyms/OpenCATP-LLM>

4. **LLMCompiler:** identify dependencies, execute independent tool calls concurrently, and avoid repeated sequential reasoning.
   Source: <https://github.com/SqueezeAILab/LLMCompiler>

5. **BATS:** expose live token/tool budgets to the controller and adapt between continuing a promising path and pivoting.
   Source: <https://github.com/google-research/budget-aware-agent>

FOIL adds its own contribution at the integration boundary: conservative posterior utility over **causally sufficient bundles**, strict evidence admission, explicit A0 identity, and no answer-changing authority from unsupported tool output.

## 4. Architecture

```text
task + task digest
        |
        v
deterministic zero-token checks
        |
        +-- sufficient ------------------------------> DIRECT / preserve A0
        |
        v
task-only gap and capability classification
        |
        v
causal frontier from versioned ToolContracts
        |
        v
minimal dependency-complete bundle enumeration
        |
        v
posterior value + damage + cost estimation
        |
        v
conservative expected-utility gate
        |
        +-- no positive bundle ----------------------> DIRECT or ABSTAIN
        |
        v
bounded execution DAG
  | parallel independent calls
  | ordered dependent calls
  | stop/cancel when marginal value is exhausted
        |
        v
normalized evidence envelopes
        |
        v
FOIL evidence-contract admission boundary
        |
        +-- invalid / unresolved --------------------> preserve A0
        |
        +-- valid supporting evidence ---------------> support only
        |
        +-- admitted corrective evidence ------------> candidate may replace A0
```

The task-only frontier is chosen before considering the incumbent answer. This prevents the incumbent from selecting tools that merely confirm itself. After execution begins, routing may use deterministic verifier outcomes and acquired evidence, but never the model's unsupported statement that it is confident or uncertain.

## 5. Tool contract

Every usable tool must have a closed, versioned contract:

```text
ToolContract
  contract_version
  tool_id
  capability
  preconditions
  effects
  required_inputs
  emitted_evidence_class
  dependencies
  incompatible_tools
  side_effect_class       # READ_ONLY | REVERSIBLE | CONSEQUENTIAL
  freshness_policy
  privacy_class
  provider_route
  cost_model_version
  digest
```

Unknown fields, missing fields, digest mismatches, unknown capabilities, and undeclared side effects fail closed. Consequential tools are not candidates in the initial smart-tool controller. They remain behind FOIL's separate authority system.

## 6. Cost model

FOIL must price the complete cost of a proposed bundle, not merely the number of API calls:

```text
ToolCost
  prompt_tokens
  expected_result_tokens
  expected_followup_tokens
  monetary_cost
  expected_latency_ms
  privacy_cost
  failure_probability
  retry_cost
```

For parallel calls, latency uses the dependency graph's critical path, while tokens and money remain additive. Reused or cached evidence receives its actual marginal cost, not the original acquisition cost. Retry costs are bounded and included before execution.

The session's 250,000-token benchmark ceiling remains a **caller-supplied run budget**. It must not become a hard-coded FOIL product default.

## 7. Probability and value estimation

### 7.1 What FOIL estimates

FOIL does not ask the model, "How likely is this tool to help?" Model-verbalized probabilities are not admission evidence.

For task state `x` and bundle `B`, FOIL estimates from frozen, scored receipts:

- `P_rescue(x, B)`: probability that A0 is wrong and the admitted result corrects it;
- `P_damage(x, B)`: probability that A0 is correct and the route publishes an incorrect answer or improperly withholds it;
- `P_valid_evidence(x, B)`: probability that the bundle returns contract-valid, applicable evidence;
- the distribution of total cost `C(x, B)`;
- interaction terms for bundles whose tools are complementary.

### 7.2 Statistical model

Initial estimates use a hierarchical Bayesian model with partial pooling across:

- task class;
- benchmark/domain;
- base-model route;
- tool capability;
- provider route;
- individual tool and tool-pair or dependency-bundle effects.

This supports small-data cold starts without pretending that a handful of observations is certainty. Estimates carry posterior intervals, evidence counts, provenance, freshness, and route applicability. Incomparable benchmark splits are never silently pooled.

Bundle effects are learned directly when data exists. FOIL must not assume tool independence and multiply individual success probabilities. An unseen combination inherits a pessimistic prior and stays unadmitted until it earns evidence.

### 7.3 Conservative utility

For a feasible bundle `B`, define:

```text
U_LCB(B | x) =
    rescue_value * LCB(P_rescue)
  - damage_loss * UCB(P_damage)
  - token_price * E[token_cost]
  - money_price * E[monetary_cost]
  - latency_price * E[latency]
  - privacy_price * privacy_cost
  - failure_loss * UCB(P_failure)
```

FOIL selects the causally sufficient bundle with the greatest `U_LCB`. It executes only when:

```text
U_LCB(best_bundle | x) > 0
```

and the improvement over stopping exceeds a configured minimum margin. Otherwise it stands down or abstains according to the existing answer policy.

After each completed observation, FOIL recomputes the marginal continuation value. It stops when the conservative expected gain from every remaining dependency-complete continuation is no greater than its remaining cost.

## 8. Combination search

The controller must choose bundles, not isolated tools.

1. CMTF-style contracts create the causal next-step frontier.
2. Dependency closure expands a candidate into the tools required to make its output usable.
3. Dominated bundles are removed: if bundle A costs no more and has at least as much conservative value as bundle B, B is discarded.
4. A bounded A-star or branch-and-bound search finds high-value feasible bundles without enumerating the full power set.
5. Independent nodes are grouped for parallel execution; dependent nodes remain ordered.
6. Only the selected frontier is exposed to the model, reducing tool-description tokens and tool-choice confusion.

The search objective includes learned bundle interactions. This allows two tools that are useless alone but decisive together to be selected correctly.

## 9. Evidence and authority

Tool output is an observation, not truth.

- Every result records tool, version, provider, input digest, output digest, timestamp, cost, and failure state.
- Retrieved factual evidence must retain source and freshness provenance.
- Parser, schema, citation, and applicability failures produce `INVALID` or `UNRESOLVED`, never a clean pass.
- An invalid, unadmitted, or over-budget candidate cannot replace A0.
- A0 text and digest remain preserved in the execution record.
- Supporting evidence may increase confidence without granting answer-changing authority.
- Corrective publication requires the pre-existing generated-evidence admission contract.
- No hidden gold answer, correctness label, or benchmark annotation may enter the controller before predictions are frozen.

This preserves the improvement obtained in the earlier safety work: FOIL may explore aggressively, but unsupported exploration cannot damage the published answer.

## 10. Runtime policy

```text
DIRECT
  deterministic checks or prior evidence resolve the task;
  no external tool call.

VERIFY
  one minimal, high-value read-only bundle;
  bounded evidence extraction;
  stop immediately when sufficient.

FULL
  multiple dependency-complete bundles or iterative acquisition;
  allowed only when conservative expected value remains positive;
  still bounded by caller budget and authority rules.
```

Adaptive routing must execute in benchmarks; it must not remain shadow-only while a forced `FULL` route runs anyway. Shadow mode remains available only for comparing a new, unadmitted estimator against the active controller.

## 11. Expected token performance

The current unrestricted-tools measurement is `15.978x`, or `14.978x` extra overhead beyond DIRECT.

If a CMTF-like reduction removed 90% of that extra overhead, the arithmetic lower estimate would be:

```text
1 + 0.10 * 14.978 = 2.498x
```

That is an optimistic transfer estimate, not a forecast. The initial engineering targets are:

| Workload | Initial target | Status |
|---|---:|---|
| Tool-heavy HLE-style tasks | 2.5x-4.0x | hypothesis |
| Mixed workload, 10% tool-trigger rate | 1.15x-1.30x | derived scenario |
| Mixed workload, 20% tool-trigger rate | 1.30x-1.60x | derived scenario |
| Universal 1.10x target | not credible for tool-heavy tasks | rejected as universal gate |

Percentages from different papers must not be multiplied together. Parallelism primarily reduces latency; it reduces tokens only when it also avoids repeated planning, prompt replay, or unnecessary observations.

## 12. Implementation plan

### P0 — Contracts and receipts

- Add strict `ToolContract`, `ToolCost`, `ToolReceipt`, `EvidenceEnvelope`, and `BundlePlan` schemas.
- Inventory existing FOIL tools and assign explicit capabilities, effects, costs, side-effect classes, and dependencies.
- Fail closed on unknown contract fields and cost-conservation failures.
- Preserve existing A0 and authority invariants.

### P1 — Causal frontier

- Add task-only capability and gap classification.
- Build the minimal causal frontier from tool preconditions and effects.
- Expose only frontier tools to the model.
- Add positive controls proving the frontier changes when task requirements change and does not change when hidden gold changes.

### P2 — Cost and posterior estimator

- Reconstruct training rows from frozen benchmark receipts.
- Fit rescue, damage, evidence-validity, and cost posteriors.
- Add minimum-evidence, freshness, lower-bound, and applicability gates.
- Add calibration and risk-coverage reporting; never report a point estimate without its support and interval.

### P3 — Bundle compiler

- Build dependency-complete bundle enumeration.
- Add dominance pruning and bounded A-star/branch-and-bound search.
- Represent interaction effects explicitly; unseen interactions receive pessimistic priors.
- Produce a deterministic, hashable plan before execution.

### P4 — Executor integration

- Connect the smart-tool decision to `DIRECT / VERIFY / FULL` execution.
- Parallelize independent read-only nodes.
- Recompute marginal continuation value after each completed dependency layer.
- Stop or cancel pending work when further acquisition is no longer worthwhile.
- Enforce bounded retries and exact token/tool/money conservation.

### P5 — Offline replay

- Replay old no-tool and tool-enabled receipts without new provider calls.
- Compare unrestricted tools, fixed-k, score threshold, score-per-cost, CAM-DF-lite-style stopping, and the bundle controller.
- Report counterfactual selected calls, known rescues retained, known damages avoided, and estimated cost.
- Treat replay as policy development evidence, not live efficacy evidence.

### P6 — Small matched live benchmark

- Use the same questions across all arms and model configurations.
- Include known DIRECT misses and known tool-necessary cases.
- Freeze the protocol and predictions before opening gold.
- Respect the caller's run-specific token ceiling.
- Report per-question tool frontier, chosen bundle, calls, token flow, evidence status, and final publication decision.

### P7 — Promotion

Promotion requires all of the following:

- no invalid-evidence replacement of A0;
- no unauthorized consequential action;
- exact cost and denominator conservation;
- materially fewer calls and tokens than unrestricted tools;
- retention of demonstrated tool rescues on distinct questions;
- damage/rescue ratio within the existing FOIL authority gate;
- calibration evidence applicable to the promoted task and tool routes;
- no benchmark-only or hidden-gold feature available at runtime.

## 13. Required tests

1. strict contract parsing, missing/unknown fields, digest mismatch, and version mismatch;
2. precondition/effect frontier correctness and causal minimality;
3. task-only selection independence from A0 and hidden gold;
4. dependency closure, cycles, incompatible tools, and dominated bundles;
5. bundle synergy where neither individual tool is sufficient;
6. no independence assumption for unseen combinations;
7. posterior monotonicity, interval widening under sparse evidence, and freshness decay with a synthetic clock;
8. exact token, monetary, latency, retry, and tool-call conservation;
9. parallel critical-path latency versus additive token cost;
10. marginal stopping and bounded cancellation;
11. provider failure, malformed evidence, stale evidence, and citation failure;
12. invalid evidence cannot replace A0;
13. A0 identity and generated origin remain visible;
14. no call occurs on `DIRECT`;
15. benchmark budget is caller supplied and not a product constant;
16. deterministic selection, report hashing, and replay reproducibility.

## 14. Reporting contract

Every smart-tool report must include:

- task and A0 digests;
- selected route and reason code;
- candidate frontier and excluded-tool reasons;
- every considered bundle and conservative utility components;
- selected execution DAG;
- calls attempted, completed, failed, cancelled, and reused;
- tokens in/out by model call and tool-result context;
- tool cost, latency, and retry receipts;
- evidence admission status;
- rescue, damage, withholding, abstention, and final-answer identity;
- explicit `MEASURED`, `DERIVED`, `JUDGMENT`, and `NOT_MEASURED` labels;
- non-claims appropriate to sample size and benchmark provenance.

## 15. Final rule

FOIL does not use a tool because it is relevant, available, or recommended by the model. FOIL uses the smallest causally sufficient bundle only when a conservative, evidence-backed estimate says that its expected correctness gain exceeds its complete cost and risk. It stops the moment that statement is no longer true.
