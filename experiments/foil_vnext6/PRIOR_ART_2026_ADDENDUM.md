# FOIL vNext6 — 2026 Continuation Audit

Date reviewed: 2026-08-23

Scope: post-V1 work published or materially revised in 2026 that could change the
vNext6 operator set or its execution boundary.

This addendum distinguishes:

- what a source reports;
- what mechanism is transferred into FOIL;
- what is deliberately excluded;
- whether the transfer changes the operator library or only strengthens the
  execution/admission contract.

A related paper is not evidence that FOIL itself works.

## 1. Budget-Aware Value Tree

Primary source: <https://arxiv.org/abs/2603.12634>

The paper proposes training-free budget-aware tree search with step-level
relative-progress scoring and budget-conditioned exploration/exploitation.

### Transfer to FOIL

- classify every operator outcome as `PROGRESSED`, `STALLED`, or `BLOCKED`;
- count concrete state deltas rather than trusting absolute same-model quality
  scores;
- preserve explicit remaining budgets;
- make repeated work auditable before allowing further escalation.

### Not transferred

- a generic value tree on every task;
- same-model value estimates as evidence;
- broad tree search when a claim-native discriminator exists;
- the paper's convergence claim as a guarantee for FOIL.

The transferred mechanism is therefore **progress admission**, not BAVT itself.

## 2. VerifiAgent

Primary source: <https://arxiv.org/abs/2504.00406>

VerifiAgent combines meta-verification with adaptive selection of reasoning-type
appropriate tools.

### Transfer status

This supports, but does not materially extend, frozen V1's existing
claim-kind-to-verifier mapping and vNext6's `CLAIM_NATIVE_VERIFY` /
`EXACT_EXECUTION` routes.

No new universal verifier agent is added. FOIL keeps verification decomposed by
claim and authority because one verifier should not self-certify its own routing
and evidence admission.

## 3. GLEAN

Primary source: <https://openreview.net/forum?id=FP23eFYhAy>

GLEAN compiles expert guidelines into verification signals, accumulates evidence
along trajectories, calibrates uncertainty, and actively expands verification
for uncertain high-stakes cases.

### Transfer to FOIL

- add `OFFICIAL_GUIDELINE` as a first-class evidence basis;
- require guideline evidence to be bound to the exact claim and verifier;
- preserve freshness checks for current guidelines;
- allow uncertainty to trigger additional evidence acquisition through the
  existing controller.

### Not transferred

- clinical correctness claims outside the paper's evaluated scope;
- the calibrated Bayesian model as a universal FOIL confidence model;
- step-wise guideline ratings without a validated domain protocol;
- automatic high-stakes deployment.

A future domain package may compile an official protocol into atomic FOIL
obligations. The universal controller does not hard-code clinical rules.

## 4. VERITAS — faithful agentic search

Primary source: <https://openreview.net/forum?id=mZ0gGlXelF>

VERITAS evaluates and trains for faithfulness across think-search,
information-think, and think-answer transitions.

### Transfer to FOIL

- bind external evidence to an atomic claim ID;
- require an explicit entailment flag and matching verifier;
- separate search observations from admitted claim-native evidence;
- preserve source/state freshness and traceability;
- expose only minimal public receipts rather than private chain-of-thought.

### Not transferred

- RL training;
- LLM-judge faithfulness scores as final authority;
- storage or publication of hidden reasoning traces;
- episode-level correctness as sufficient evidence.

FOIL's implementation uses **evidence-to-claim traceability**, not
chain-of-thought surveillance.

## 5. Verified tool calls under non-atomic failures

Primary source: <https://arxiv.org/abs/2608.02645>

The paper studies tool calls that can partially succeed, time out after dispatch,
or become visible later, and proposes postcondition checks, verify-before-retry,
and idempotency keys.

### Transfer to FOIL

For side-effecting tool use:

- require an idempotency key before execution;
- require prior postcondition checking before a retry;
- require a verified postcondition before a completed outcome is admitted;
- optionally record an observed-state fingerprint.

### Not transferred

- an assumption that every wrapper postcondition is correct;
- treating tool transport success as task success;
- automatic retry loops;
- side-effecting behavior in closed-book benchmark conditions.

This is a runtime integrity rule, not a reasoning strategy.

## 6. CORVUS

Primary source: <https://arxiv.org/abs/2607.22711>

CORVUS decouples stale file observations from the action history and injects
current synchronized state, reducing context and redundant reads in coding
agents.

### Transfer to FOIL

- evidence packets carry a `stale` state;
- stale evidence cannot discharge a claim;
- side-effect outcomes may record a state fingerprint;
- current-source verification remains distinct from old observations.

### Not transferred

- a coding-specific synchronized registry in the universal controller;
- automatic replacement of historical evidence;
- deleting provenance merely because current state changed.

FOIL should preserve the historical receipt while marking whether it remains
applicable to current state.

## 7. RACER — selective reasoning for LLM judges

Primary source: <https://openreview.net/forum?id=G3Nm8GYBHd>

RACER reports that explicit reasoning helps structured verification tasks more
than simple judgments and proposes a robust cost-aware router.

### Transfer status

This supports vNext6's existing direct/no-op route and selective activation of
reasoning operators. No learned distributionally robust router is transferred
because:

- vNext6 has no clean training set for that policy;
- its current objective includes evidence authority, not only judgment
  accuracy/cost;
- the frozen evaluation must not tune routing after item exposure.

A learned router remains a possible later development experiment on separate
training and validation data.

## 8. Cross-family verification

Primary source: <https://openreview.net/forum?id=I0yfD1zLZI>

The study compares self-, same-family, and cross-family verification over a
large solver/verifier matrix and reports especially effective cross-family
verification in several reasoning domains.

### Transfer refinement

`INDEPENDENT_REVIEW` remains optional and high-impact. Its output is not admitted
by model-family difference alone. It must still provide:

- the target claim ID;
- a matching verifier;
- a compatible evidence basis;
- entailment of the exact claim;
- non-stale evidence.

Cross-family review improves independence; it does not eliminate the need for
claim-native evidence.

## 9. MetaForge

Primary source: <https://arxiv.org/abs/2606.01801>

MetaForge learns when to answer directly, retrieve/adapt tools, or forge new
ones, with an invocation-cost penalty.

### Transfer status

The `Decide -> Retrieve -> Adapt` distinction is consistent with vNext6's
operator router and typed request. Runtime `Forge` and tool-library recycling
remain excluded because they would:

- self-modify during evaluation;
- expand the attack surface;
- complicate causal attribution;
- risk task- or benchmark-specific accumulation.

Tool creation may be studied offline under a separate frozen development and
security process.

## 10. Resulting architecture change

The continuation audit does **not** add another top-level reasoning operator.
Instead it closes the missing execution/evidence boundary:

```text
FOIL policy decision
  -> typed operator request
  -> method/tool execution
  -> typed outcome
  -> evidence and postcondition admission
  -> progress classification
  -> update only admitted state
  -> return to FOIL policy
```

The new contract adds:

1. atomic target claim IDs;
2. verifier-matched evidence packets;
3. evidence-basis typing, including official guidelines;
4. entailment, freshness, and staleness checks;
5. explicit distinction between search observations and admitted verification;
6. side-effect idempotency and verify-before-retry;
7. postcondition verification;
8. progress/stall classification;
9. minimal public traces without chain-of-thought.

This remains an implementation hypothesis. Behavioral and operational promotion
requires prospective evaluation and fault injection.
