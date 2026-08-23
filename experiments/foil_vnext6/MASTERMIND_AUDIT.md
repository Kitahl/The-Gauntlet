# FOIL vNext6 — Three-Loop Mastermind Causal Audit

Date: 2026-08-23

Candidate: `FOIL_vNEXT6_COMPOSABLE_POLICY_V1`

Frozen parent: `d320943d3fd34b3891054acf9e95d70c02531220`

Authority: Mastermind is used as `PRE_REVIEW_ONLY` causal/mechanical discipline.
This report does not claim answer authority or behavioral improvement.

## Audit rules

Each loop must:

1. identify the earliest materially distinct causal defect;
2. add the smallest mechanism that closes it;
3. preserve frozen FOIL invariants;
4. include a negative control;
5. expose an ablation;
6. avoid changing the frozen vNext5 candidate or benchmark;
7. stop after at most three loops.

---

# LOOP 1 — Regime selection did not select an executable strategy

## Earliest causal defect

Frozen V1 correctly chooses task regime, effort mode, verifier obligations, and
stopping, but its broad actions such as `reason_closed_book`,
`discover_candidates`, and `mix_tools_and_reasoning` leave the execution method
underspecified.

As a result, an implementation could:

- apply CoT to every task;
- browse when direct reasoning is enough;
- use generic reflection instead of exact execution;
- run every available method in sequence;
- vary behavior without a receipt-visible policy decision.

## Smallest mechanism added

**One-Operator Strategy Composer**

- preserve V1 as Level A;
- introduce a fixed operator enum as Level B;
- select exactly one next operator;
- require the caller to update state and re-enter the controller;
- retain direct and stop/no-op routes;
- record only operator identity, reason code, authority, verifier, and budget.

Operators are:

- direct;
- decomposition;
- ReAct;
- exact execution;
- claim-native verification;
- bounded challenger search;
- evidence-triggered reflection;
- independent review;
- Mastermind causal audit;
- stop;
- blocked.

## Mastermind admission gates

| Gate | Result | Reason |
| --- | --- | --- |
| A — Causal adequacy | `PASS-SPEC` | Directly closes the missing strategy-selection link between V1 policy and execution. |
| B — Identifier independence | `PASS` | Routes by task/evidence state, not benchmark item IDs. |
| C — Representation transformation | `PASS-SPEC` | Applies to prose, formal, retrieval, code, transformation, and mixed tasks. |
| D — Negative control | `PASS-SPEC` | Simple low-complexity work retains the direct route. |
| E — Cross-domain transfer | `PASS-SPEC` | Operator conditions use epistemic/task structure. |
| F — Existing-mechanism compression | `PASS` | Composes the frozen V1 controller rather than replacing it. |
| G — Ablation | `PASS-STRUCTURAL` | Removing Level B returns broad, underdetermined V1 actions. |
| H — Regression | `PASS` | V1 regime, profile, verifier, budget, and stop decisions remain authoritative. |

---

# LOOP 2 — Added methods could create circular pseudo-evidence

## Earliest causal defect

A strategy library alone does not distinguish candidate-generation signals from
evidence. CoT, self-consistency, Tree of Thoughts, Reflexion, same-model
critique, and Mastermind can all generate persuasive agreement or revision
without adding information independent of the original error.

Without an authority boundary, the new controller could mark an uncertainty
resolved because:

- several sampled paths agree;
- the same model says its answer is correct;
- a reflection changes the prose;
- Mastermind finds a plausible defect;
- a raw tool observation is mistaken for an entailing result.

## Smallest mechanism added

**Evidence-Authority Gate**

Public authority classes:

1. `NONE`
2. `INTERNAL_HEURISTIC`
3. `EXTERNAL_OBSERVATION`
4. `CLAIM_NATIVE`
5. `INDEPENDENT_REVIEW`

Only admitted `CLAIM_NATIVE` or qualified `INDEPENDENT_REVIEW` output may
discharge a load-bearing uncertainty.

The controller explicitly marks these as non-verifying:

- direct reasoning;
- decomposition/CoT;
- branch agreement;
- reflection;
- Mastermind diagnosis.

ReAct discovery is initially only `EXTERNAL_OBSERVATION`; after a viable
candidate exists, V1 schedules the claim-native verifier.

## Mastermind admission gates

| Gate | Result | Reason |
| --- | --- | --- |
| A — Causal adequacy | `PASS-SPEC` | Blocks the precise path from method output to circular verification. |
| B — Identifier independence | `PASS` | Authority depends on evidence relation, not source/model name alone. |
| C — Representation transformation | `PASS-SPEC` | Same boundary applies to facts, code, math, examples, logic, and formatting. |
| D — Negative control | `PASS-SPEC` | Agreement and polished revisions remain non-evidence without a matched verifier. |
| E — Cross-domain transfer | `PASS-SPEC` | Claim-native authority is domain-relative. |
| F — Existing-mechanism compression | `PASS` | Extends FOIL's existing claim/evidence law. |
| G — Ablation | `PASS-STRUCTURAL` | Removing authority classes allows branching/reflection/Mastermind to masquerade as proof. |
| H — Regression | `PASS` | Mandatory V1 verifier selection still controls closure. |

---

# LOOP 3 — Composability could cause method stacking and cost explosion

## Earliest causal defect

Even with typed operators and authority, a controller could call multiple
eligible methods automatically, consume the entire budget, or append a final
Mastermind/critique pass after the answer is already releasable.

That would violate FOIL's minimum-complement goal and erase causal attribution.

## Smallest mechanism added

**Budgeted Escalation and No-Op Contract**

- runner supplies immutable remaining counters;
- every operator has an explicit cost;
- returned budget is component-wise non-increasing;
- one operator is selected per invocation;
- mandatory verification outranks optional methods;
- optional branching requires real disagreement and two branch slots;
- Reflexion requires demonstrated, targeted failure and is limited to one task-local attempt;
- independent review is high-impact and optional;
- Mastermind requires high impact, a causal/process defect, at least two route failures, and remaining loop budget;
- Mastermind is hard-capped at three loops by a monotone remaining-budget counter;
- V1 `STOP` prevents every extra pass;
- if no distinct evidence-bearing action remains, emit `BLOCKED`.

## Mastermind admission gates

| Gate | Result | Reason |
| --- | --- | --- |
| A — Causal adequacy | `PASS-SPEC` | Directly blocks automatic stacking, hidden cost, and gratuitous final audits. |
| B — Identifier independence | `PASS` | Costs and gates are general runtime state. |
| C — Representation transformation | `PASS-SPEC` | Same budget law applies across task regimes. |
| D — Negative control | `PASS-SPEC` | Direct and stop/no-op paths remain executable. |
| E — Cross-domain transfer | `PASS-SPEC` | Escalation depends on uncertainty, evidence, impact, and remaining resources. |
| F — Existing-mechanism compression | `PASS` | Extends V1 fixed ceilings and release rule. |
| G — Ablation | `PASS-STRUCTURAL` | Removing one-step selection or monotone budgets restores stacking/cost ambiguity. |
| H — Regression | `PASS` | No mandatory V1 obligation can be skipped for cost; no ceiling is increased. |

---

# Defects found during implementation

## D1 — External-fact discovery could miss ReAct

The initial implementation routed to ReAct only when an explicit
`requires_external_retrieval` or sequential-interaction flag was present. A
task-local external-fact uncertainty could therefore request
`SOURCE_EVIDENCE` while the broad regime remained mixed and fall through to
direct reasoning.

**Correction:** pending `SOURCE_EVIDENCE` or `CURRENT_SOURCE` now independently
activates the ReAct discovery route before a viable candidate exists.

## D2 — Verification before candidate generation

A naive priority order would run every pending verifier before a candidate
exists, including supplied-example checks for abstract transformation.

**Correction:** candidate generation precedes candidate verification. Exact
calculation/execution is the only exception because it may itself construct the
candidate.

## D3 — Mandatory verifier fallback risk

A budget-aware controller could be tempted to substitute generic self-critique
when a required source/execution/calculation call is unaffordable.

**Correction:** mandatory verifier unavailability or budget exhaustion emits
`BLOCKED`; it never degrades silently to a weaker operator.

## D4 — Test suite was not discoverable by repository CI

The first uploaded contract suite used pytest-style free functions and imported
`pytest`. The repository workflow installs no pytest dependency and runs
`python -m unittest discover -s tests -v`. The file would therefore fail at
import or contribute no discovered tests, despite passing in a separate local
pytest environment.

**Correction:** converted the suite to `unittest.TestCase` methods, removed the
pytest dependency, reran the exact repository discovery command, and retained
all 24 contract cases.

# Mechanical validation

Local executable checks:

- repository-compatible `unittest` discovery: **24/24 PASS**;
- targeted pytest execution before the CI-compatibility conversion: **24/24
  PASS**;
- Python compilation: **PASS**;
- public trace validation against `trace_schema.json`: **PASS**;
- the local environment did not provide an importable `ruff` module, so lint is
  **NOT MEASURED** locally and is left to repository CI.

The contract suite covers:

- V1 stop preservation;
- direct negative control;
- conditional decomposition;
- ReAct discovery;
- exact/executable routing;
- CoVe/CRITIC-style claim-native verification;
- output-contract checking;
- bounded challenger eligibility;
- branching non-authority;
- failure-gated one-shot reflection;
- Mastermind late routing and three-loop cap;
- mandatory-verifier precedence;
- independent-review fallback;
- block-on-unavailable/budget-exhausted verification;
- profile inability to remove freshness obligations;
- unresolved-state preservation;
- budget monotonicity;
- receipt privacy.

# Supported claims

- The candidate is implemented as a separate post-freeze module.
- Frozen V1 remains imported and authoritative.
- The three design defects and one CI-discovery defect above are represented by
  explicit mechanisms or executable contract tests.
- The local targeted test suite passed 24/24.
- The controller has direct, stop, and blocked paths.
- CoT, branching, reflection, and Mastermind are explicitly non-verifying.
- Mastermind is not automatic and is capped at three loops.
- Budgets cannot increase through the public API.

# Further evidence required

- Behavioral evidence that an LLM faithfully executes the selected operator.
- Same-item equal-budget comparison against direct, CoT, ReAct/CoVe, Reflexion,
  frozen V1, and vNext6.
- Calibration of operator routing thresholds.
- Cost/accuracy curves using actual tokens, latency, and tool calls.
- Evidence that bounded branching adds value beyond a single challenger.
- Evidence that one-shot reflection improves after verified failure.
- Evidence that independent review adds value under matched budgets.
- Evidence that Mastermind escalation helps rather than overthinks.
- Transfer beyond the task families used to design the controller.
