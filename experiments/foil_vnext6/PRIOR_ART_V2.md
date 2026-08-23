# FOIL vNext6 — Strategy Integration Prior-Art Audit

Date: 2026-08-23

Scope: methods that can improve a portable, evidence-governed, black-box
reasoning controller without changing model weights or learning from held-out
benchmark items.

This audit distinguishes:

- a method's published result;
- the mechanism transferred into FOIL;
- what FOIL deliberately does not inherit.

A paper adjacent to a FOIL mechanism is not evidence that the FOIL combination
works.

## 1. Chain-of-Thought

Primary source: <https://arxiv.org/abs/2201.11903>

**Mechanism:** elicit intermediate reasoning steps for complex tasks.

**Transfer:** `DECOMPOSE`, enabled for high-complexity, multi-hop, technical, or
abstract-transformation tasks.

**Not transferred:**

- mandatory step-by-step reasoning on every task;
- recording private chain-of-thought in public receipts;
- treating a plausible derivation as evidence for an external fact.

**Reason:** CoT is useful candidate-generation structure, not an epistemic
arbiter.

## 2. Self-Consistency

Primary source: <https://arxiv.org/abs/2203.11171>

**Mechanism:** sample diverse reasoning paths and aggregate answers.

**Transfer:** only the idea of generating a small challenger set when multiple
plausible candidates genuinely disagree.

**Not transferred:**

- unbounded sampling;
- majority vote as truth;
- branch agreement as resolution of a load-bearing uncertainty.

**FOIL form:** `BOUNDED_CHALLENGER_SEARCH`, width two in the first candidate.

## 3. ReAct

Primary source: <https://arxiv.org/abs/2210.03629>

**Mechanism:** interleave reasoning, action, and environmental observation.

**Transfer:** `REACT` as the execution substrate for external discovery or
sequential tool interaction.

**Not transferred:**

- ReAct as the top-level controller;
- tool use merely because tools exist;
- continuing until a generic step limit after FOIL's release condition holds.

**FOIL difference:** frozen V1 first decides whether external interaction is
allowed/required and whether the next unit should be discovery or verification.

## 4. Tree of Thoughts

Primary source: <https://arxiv.org/abs/2305.10601>

**Mechanism:** branch, evaluate, look ahead, and backtrack over candidate
reasoning states.

**Transfer:** one bounded challenger operation when there are at least two
materially different plausible candidates and branch budget remains.

**Not transferred:**

- generic tree search;
- self-evaluation as verification;
- open-ended lookahead;
- a tree on problems with one obvious claim-native discriminator.

## 5. Reflexion

Primary source: <https://arxiv.org/abs/2303.11366>

**Mechanism:** use outcome feedback to produce verbal reflection retained for
later attempts.

**Transfer:** one task-local `EVIDENCE_TRIGGERED_REFLECTION` after:

1. a failure has actually been demonstrated;
2. the correction target is specific;
3. no reflection has already been used for the task; and
4. revision budget remains.

**Not transferred:**

- automatic reflection after every answer;
- benchmark-item memory;
- private trajectory storage in receipts;
- reflection as independent evidence.

## 6. CRITIC

Primary source: <https://arxiv.org/abs/2305.11738>

**Mechanism:** interact with appropriate external tools to critique and amend an
initial output.

**Transfer:** tool-mediated claim checking inside `CLAIM_NATIVE_VERIFY`.

**Not transferred:**

- a universal critique loop;
- revising from tool output without checking whether it entails the atomic
  claim;
- treating any tool response as authoritative.

## 7. Chain-of-Verification

Primary source: <https://arxiv.org/abs/2309.11495>

**Mechanism:** draft, formulate verification questions, answer them with reduced
conditioning bias, then produce a verified response.

**Transfer:** verification-question planning for the pending atomic claims,
followed by the V1 claim-matched verifier schedule.

**Not transferred:**

- asking generic verification questions when V1 has no unresolved obligation;
- same-model answers standing in for current-source, execution, exact
  calculation, or formal counterexample evidence.

## 8. Intrinsic self-correction limits and key-condition verification

Primary sources:

- <https://arxiv.org/abs/2310.01798>
- <https://arxiv.org/abs/2405.14092>

The first reports that intrinsic self-correction without external feedback can
degrade reasoning. The second reports gains from verifying a task's key
condition rather than asking for undirected reconsideration.

**Transfer:**

- no generic self-correction loop;
- identify a load-bearing condition or claim;
- run the smallest discriminator that could change the answer;
- preserve unresolved state when no distinct evidence-bearing action exists.

This is the closest prior-art support for FOIL's load-bearing-uncertainty
controller, but it does not validate FOIL itself.

## 9. CodeSteer

Primary source: <https://openreview.net/forum?id=ezna4V4zHs>

**Mechanism:** select between text reasoning and code/symbolic execution, with
checkers.

**Transfer:** `EXACT_EXECUTION` for numeric or executable obligations.

**Not transferred:**

- the trained CodeSteer guidance model;
- task-specific fine-tuning;
- code generation when a simpler exact calculation or supplied-example check
  suffices.

## 10. Adaptive strategy routing

Primary source: <https://arxiv.org/abs/2505.19435>

Route-to-Reason jointly routes models and reasoning strategies under budget and
reports improved accuracy/cost trade-offs.

**Transfer:**

- treat strategies as a selectable operator library;
- choose by task state rather than use one method globally;
- preserve a direct/no-op route;
- make budget constraints explicit.

**Not transferred:**

- learned model/strategy embeddings;
- training a router on the vNext evaluation set;
- model selection, which is outside this candidate's scope.

## 11. Budget-aware tool use

Primary source: <https://arxiv.org/abs/2511.17006>

Budget-Aware Tool-Use and BATS explicitly track remaining tool resources and
adapt between digging deeper and pivoting.

**Transfer:**

- immutable remaining-budget state;
- explicit per-operator costs;
- no action may increase a ceiling;
- mandatory verification blocks when unaffordable rather than silently
  degrading into self-critique.

**Not transferred:**

- learned scaling policy;
- extra tool calls beyond the surrounding runner's frozen ceiling;
- benchmark-specific budget tuning.

## 12. Cross-family verification

Primary source: <https://openreview.net/forum?id=I0yfD1zLZI>

The study compares self-, same-family, and cross-family verification across a
large model/dataset matrix and reports especially effective cross-family
verification.

**Transfer:** optional `INDEPENDENT_REVIEW` for high-impact residual
uncertainty, only when a genuinely independent reviewer is available and the
result is tied to the claim.

**Not transferred:**

- reviewer agreement as proof;
- a default second-model call;
- independent review before a cheaper claim-native verifier;
- treating post-training/model-family difference as automatic independence for
  every failure mode.

## 13. Prompt/program optimizers

Reviewed in frozen V1:

- DSPy GEPA;
- MIPROv2;
- SIMBA;
- TextGrad and metaTextGrad;
- AgentSquare;
- AFlow;
- Agent Lightning;
- SiriuS.

These can be useful **offline development tools** on clean development data.

They remain excluded from the runtime candidate because they:

- alter prompts, demonstrations, workflow graphs, code, or weights;
- complicate causal attribution;
- risk benchmark-specific adaptation;
- are unnecessary for a deterministic per-task controller.

A later development experiment may optimize the operator policy on a separate,
frozen development suite, then freeze it before evaluation.

## 14. Mastermind

Source boundary: the user-supplied Mastermind package and recorded repository
audits are `PRE_REVIEW_ONLY` process inputs, not answer authority.

**Transfer:**

- identify the earliest causal/process defect;
- require a materially distinct defect per loop;
- apply the smallest supported correction or discriminator;
- cap at three loops;
- return the corrected candidate to ordinary FOIL verification.

**Not transferred:**

- automatic final auditing;
- answer adjudication;
- independent-verifier status;
- additional tool budget;
- self-modification during evaluation.

## 15. Integration conclusion

The best aligned composition is not:

```text
CoT -> ReAct -> Self-Consistency -> Reflexion -> Mastermind -> answer
```

It is a state machine:

```text
frozen FOIL epistemic decision
        |
        v
select one minimum-cost eligible operator
        |
        v
update candidate/evidence/budget state
        |
        v
return to frozen FOIL verifier and stop rules
```

The adopted mechanisms are therefore:

1. adaptive operator routing;
2. conditional decomposition;
3. ReAct for tool-dependent discovery;
4. exact/code execution for exact obligations;
5. CoVe/CRITIC for claim-native verification;
6. bounded challenger generation for genuine ambiguity;
7. evidence-triggered one-shot reflection;
8. optional independent review for high-impact residual uncertainty;
9. late, bounded Mastermind causal audit;
10. explicit no-op, blocking, and budget-preservation paths.

This is an architectural hypothesis. It requires prospective behavioral
comparison before promotion.
