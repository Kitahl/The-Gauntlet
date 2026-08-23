# FOIL vNext6 Composable Policy — Post-Freeze Candidate Specification

Candidate identifier: `FOIL_vNEXT6_COMPOSABLE_POLICY_V1`

Status: **post-freeze experimental candidate; not the active FOIL skill and not part of the frozen vNext5 benchmark.**

Frozen parent:

- `VNEXT_SPEC_SHA = d320943d3fd34b3891054acf9e95d70c02531220`
- Frozen V1 files under `experiments/foil_vnext/` are imported and left unchanged.

## 1. Purpose

The frozen V1 controller establishes the epistemic core:

1. classify the task regime;
2. track load-bearing uncertainty;
3. select claim-native verifier obligations;
4. gate profile influence;
5. allocate fixed external budgets; and
6. stop when a viable candidate exists, decisive uncertainty is resolved, and mandatory verifiers are complete.

Its remaining operational gap is that broad actions such as `reason_closed_book`,
`discover_candidates`, and `mix_tools_and_reasoning` do not select among known
reasoning/agent strategies. vNext6 closes only that gap.

The design objective is not to stack every published method. It is to select the
**smallest eligible next operator** and then return control to FOIL after the
operator changes task or evidence state.

## 2. Preserved FOIL invariants

vNext6 preserves the frozen V1 invariants and adds no persistent benchmark
memory, prompt evolution, workflow search, model-weight update, or private
chain-of-thought receipt.

In particular:

- current task evidence and hard obligations override profile evidence;
- relevance is not competence;
- assisted success is not independent capability;
- confidence cannot discharge decisive uncertainty;
- same-model agreement, critique, reflection, or Mastermind diagnosis is not independent verification;
- mandatory claim-native checks cannot be optimized away;
- no operator may increase the runner-supplied budget;
- once V1's release condition is satisfied, vNext6 emits `STOP` and appends no generic final review.

## 3. Two-level controller

### Level A — frozen epistemic controller

`experiments.foil_vnext.runtime_policy.RuntimePolicy` remains authoritative for:

- `TaskRegime`;
- load-bearing uncertainty;
- mandatory verifier schedule;
- profile influence;
- discovery-versus-verification mode;
- the V1 stop condition.

### Level B — composable strategy controller

`ComposableRuntimePolicy` selects exactly one next operator. After that operator
runs, the caller updates public task/evidence state and invokes the policy
again.

This one-step design avoids:

- automatic method stacking;
- hidden multi-pass cost;
- causal ambiguity about which component acted;
- Reflexion or critique loops with no new evidence;
- Mastermind becoming a universal final pass.

## 4. Operator library

| Operator | Prior-art lineage | Eligible use | Epistemic limit |
| --- | --- | --- | --- |
| `DIRECT` | strong direct baseline | low-complexity candidate generation with no hard tool route | generates a candidate only |
| `DECOMPOSE` | CoT / least-to-most | multi-hop, high-complexity, technical, or transformation tasks | internal heuristic; not verification |
| `REACT` | ReAct | discovery requiring sequential interaction with tools or an external environment | raw observations do not yet discharge the claim |
| `EXACT_EXECUTION` | PAL / PoT / CodeSteer-like routing | exact calculation or executable behavior | may discharge only through admitted exact/execution evidence |
| `CLAIM_NATIVE_VERIFY` | CoVe + CRITIC | viable candidate plus a mandatory claim-matched verifier | may discharge only when the verifier result entails the atomic claim |
| `BOUNDED_CHALLENGER_SEARCH` | self-consistency / Tree of Thoughts | at least two genuinely plausible disagreeing candidates and an available two-branch budget | agreement or branch ranking is not proof |
| `EVIDENCE_TRIGGERED_REFLECTION` | Reflexion | demonstrated failure, a specific correction target, no prior reflection on the task, and revision budget | produces a revised candidate; does not verify it |
| `INDEPENDENT_REVIEW` | cross-family/independent verifier | high-impact unresolved claim when the native verifier is unavailable or inconclusive and an independent review slot exists | counts only when claim-matched evidence is returned |
| `MASTERMIND_CAUSAL_AUDIT` | Mastermind | high-impact causal/process defect after at least two route failures and no cheaper mandatory verifier | diagnosis only; maximum three loops; not verification |
| `STOP` | FOIL release rule | V1 release condition satisfied | no extra pass |
| `BLOCKED` | FOIL unresolved-state law | mandatory verifier unavailable/exhausted or no distinct evidence-bearing action remains | preserves uncertainty rather than fabricating closure |

## 5. Evidence-authority law

Each operator declares a minimum evidence authority:

1. `NONE`
2. `INTERNAL_HEURISTIC`
3. `EXTERNAL_OBSERVATION`
4. `CLAIM_NATIVE`
5. `INDEPENDENT_REVIEW`

Only `CLAIM_NATIVE` or qualified `INDEPENDENT_REVIEW` output may discharge a
load-bearing uncertainty.

The following remain `INTERNAL_HEURISTIC`:

- CoT/decomposition;
- self-consistency;
- Tree-of-Thought-style branching;
- same-model critique;
- Reflexion memory/revision;
- Mastermind causal diagnosis.

They can change the candidate or select the next test, but not establish the
claim by themselves.

## 6. Deterministic precedence

For each invocation:

1. If frozen V1 says stop, emit `STOP`.
2. Before a viable candidate:
   1. exact calculation/execution may construct the candidate;
   2. after repeated high-impact route failures, a bounded Mastermind audit may identify the smallest causal/process defect;
   3. genuine candidate disagreement may trigger one bounded challenger search;
   4. required external discovery uses ReAct;
   5. structurally complex closed tasks use decomposition;
   6. otherwise use the direct route.
3. After a viable candidate:
   1. pending mandatory claim-native verifier;
   2. one evidence-triggered reflection after a demonstrated targeted failure;
   3. optional independent review for high-impact residual uncertainty;
   4. bounded Mastermind audit after cheaper routes fail;
   5. one bounded challenger search if real disagreement remains;
   6. otherwise emit `BLOCKED`, not generic self-critique.

Mandatory verification always outranks reflection, branching, independent
deliberation, and Mastermind.

## 7. Budget contract

The runner supplies immutable remaining counters:

- deliberation units;
- tool calls;
- branch slots;
- revision slots;
- independent reviews;
- Mastermind loops.

Every selected operator has an explicit cost. The returned `budget_after` is
component-wise less than or equal to `budget_before`.

Mastermind is hard-capped at three loops by the runner-supplied remaining budget.

A mandatory action that cannot be afforded is not replaced with a cheaper,
epistemically weaker action. The decision becomes `BLOCKED`.

## 8. Mastermind integration

Mastermind is integrated as a late **causal-defect selector**, not as:

- a default final critic;
- an answer oracle;
- an independent verifier;
- permission to enlarge tool or reasoning budgets;
- a persistent self-modification loop.

Each admitted loop must identify a materially distinct earliest defect and
propose the smallest correction or discriminator. The corrected candidate must
return to the ordinary FOIL verifier schedule.

## 9. Public trace

The vNext6 trace contains only:

- controller version;
- task regime;
- selected strategy operator and public lineage label;
- short reason code;
- minimum evidence authority;
- required verifier, if any;
- whether the operator may discharge load-bearing uncertainty;
- unresolved uncertainty count;
- profile influence;
- remaining budgets;
- V1 stop reason.

It excludes prompts, private reasoning, scratchpads, benchmark answers, gold
answers, evaluator feedback, and persistent task-specific memories.

## 10. Explicit exclusions

This candidate does not:

- modify `skills/foil/SKILL.md`;
- modify frozen `experiments/foil_vnext/` files;
- modify or score the vNext5 benchmark;
- add a permanent FOIL calibration layer;
- optimize prompts or workflow graphs on evaluation items;
- store Reflexion traces between benchmark items;
- use majority vote as evidence;
- treat cross-model agreement as proof without claim-matched support;
- claim behavioral superiority from specification tests.

## 11. Validation boundary

The executable contract suite tests operator eligibility, negative controls,
budget monotonicity, evidence authority, trace privacy, Mastermind limits, and
preservation of the V1 release rule.

Passing these tests establishes implementation consistency only. Behavioral
promotion requires prospective, same-item, equal-budget evaluation against
strong direct, CoT, ReAct/CoVe, Reflexion, and ablated FOIL conditions.
