# FOIL vNext7 — Evidence-Typed Composable Controller

Candidate: `FOIL_vNEXT7_EVIDENCE_TYPED_POLICY_V1`

Status: **post-freeze experimental candidate**. It does not modify the frozen
vNext5 benchmark or the active public FOIL skill.

Parent:

- frozen epistemic policy: `experiments/foil_vnext/`
- composable operator policy: `experiments/foil_vnext6/`
- vNext7 adds an evidence-target and cached-qualification layer only.

## 1. Goal

FOIL is not trying to be the longest reasoning loop. Its goal is to supply the
**smallest task-relevant complement that can change the answer or establish the
claim**, while:

- preserving uncertainty when evidence is insufficient;
- separating candidate generation from verification;
- tracking complete cost;
- avoiding benchmark/task-specific memory;
- keeping personalization provisional and evidence-conditioned;
- stopping once the frozen release condition is satisfied.

The external methods are therefore operators under FOIL, not a fixed chain.

## 2. Method composition

| Family | vNext7 role | Default? | Epistemic status |
| --- | --- | --- | --- |
| Direct answer | `DIRECT` | yes for simple work | candidate only |
| CoT / least-to-most | `DECOMPOSE` | conditional | internal heuristic |
| Self-Discover-style structure selection | compressed inside complex decomposition; no separate permanent loop | conditional | internal heuristic |
| ReAct | `REACT` | only for sequential discovery/environment interaction | external observation, not claim closure |
| PAL / PoT / CodeSteer-style symbolic routing | `EXACT_EXECUTION` | when exact calculation/execution is the matched route | claim-native only after admitted execution/calculation evidence |
| CoVe / CRITIC | `CLAIM_NATIVE_VERIFY` | when a mandatory verifier is pending | claim-native verifier |
| Self-consistency / ToT | `BOUNDED_CHALLENGER_SEARCH` | only on genuine candidate disagreement | challenger generation, never vote-as-proof |
| Reflexion | `EVIDENCE_TRIGGERED_REFLECTION` | only after demonstrated targeted failure; once | candidate revision only |
| Independent review | `INDEPENDENT_REVIEW` | high-impact residual uncertainty | must preserve the native verifier and return matched evidence |
| Mastermind | `MASTERMIND_CAUSAL_AUDIT` | late, after repeated causal/process route failure | diagnosis only |
| LATS / large tree search | not a default operator | no | defer until matched-budget evidence justifies it |
| generic Self-Refine / repeated same-model critique | rejected as a default loop | no | weakly independent or circular |
| multi-agent majority/debate | rejected as default evidence | no | agreement is not proof |
| learned adaptive test-time allocator | not frozen into vNext7 | no | promising future calibration layer, needs prospective data |

This preserves the useful parts of the methods without turning FOIL into:

`CoT -> ReAct -> vote -> reflect -> debate -> Mastermind -> answer`.

## 3. Runtime sequence

```text
task + provisional profile
        |
        v
frozen FOIL epistemic policy
(regime, decisive uncertainty, native verifier, stop)
        |
        v
vNext6 one-operator composer
        |
        v
vNext7 target/receipt layer
(explicit verifier targets, cache eligibility)
        |
        v
execute exactly one operator
        |
        v
typed outcome + evidence qualification
        |
        v
admit only verifier-matched state deltas
        |
        +----> frozen STOP => release
        |
        +----> unresolved => re-enter controller
```

No operator appends itself automatically.

## 4. vNext7 repairs

### 4.1 Explicit verification targets

vNext6 evidence-bearing requests required atomic claim IDs, but the frozen policy
can create a hard verifier obligation that is not attached to an unresolved
`LoadBearingUncertainty`, for example:

- FreshQA/current-source regime obligation;
- output-contract checking.

vNext7 always produces a stable target for an evidence-bearing verifier.

- atomic claim: reuse its stable label/claim ID;
- regime/output obligation with no atomic claim: synthesize
  `O:<verifier>` such as `O:current_source`.

The execution request is built from controller targets rather than relying on an
executor to invent them.

### 4.2 Preserve verifier identity on independent review

vNext6 can reach:

- native verifier completed;
- decisive uncertainty remains;
- high-impact independent review is available.

In that residual path the vNext6 strategy can select `INDEPENDENT_REVIEW` while
`required_verifier` is `None`. That creates a contradiction: the strategy says
the review may discharge uncertainty, but the execution validator requires a
concrete verifier for claim resolution.

vNext7 derives the residual verifier from the frozen uncertainty kind and carries
it into the independent-review decision. Independence never substitutes for the
claim-native evidence type.

### 4.3 Re-use captured evidence without re-running acquisition

vNext6 intentionally prevents ReAct from self-promoting discovery into verified
evidence. That boundary is preserved.

However, forcing a second *external acquisition* is unnecessary when ReAct
already captured the exact source/execution material. vNext7 separates:

1. acquisition;
2. local claim-native qualification;
3. admission.

A cached hint can make the next verifier operation cost zero additional external
tool calls, but:

- the raw observation is still not evidence;
- the cached content needs a content SHA-256;
- the exact target/verifier must match;
- stale material is rejected;
- current-source material needs freshness checking;
- a qualification receipt and explicit verdict are required;
- the parent vNext6 admission validator still decides whether the claim/verifier
  update is admitted.

This is evidence reuse, not verification bypass.

### 4.4 Authority is a requirement relation, not a prestige ladder

vNext7 exposes an acceptance relation:

- a claim-native requirement accepts claim-native or genuinely independent
  claim-matched evidence;
- an independent-review requirement accepts only independent evidence.

`INDEPENDENT_REVIEW` is not treated as universally "stronger" than execution,
calculation, source evidence, or proof. The verifier/basis relation remains
mandatory.

Mechanical qualification is restricted to mechanical bases:

- execution;
- calculation;
- supplied-context consistency;
- output-contract checking.

It cannot mechanically certify source entailment merely by being reproducible.

## 5. How each method helps FOIL

### CoT / least-to-most

Use for dependent closed-book subproblems. Do not use as a universal prefix.
Self-Discover's useful mechanism is absorbed here: choose a task-specific
reasoning structure when decomposition itself is nontrivial, rather than adding
another permanent controller.

### ReAct

Use to acquire observations from an external environment. ReAct is discovery,
not truth. Its useful output is a candidate plus captured references/receipts.

### Exact execution / CodeSteer-style routing

When the uncertainty is numerical or executable, prefer an exact route to more
language-only deliberation. vNext7 keeps this as a claim-matched operator rather
than a generic "use code" rule.

### CoVe / CRITIC

These supply the strongest general improvement to FOIL's epistemic goal:
verification questions come from atomic load-bearing targets, and the verifier is
selected by claim type.

### Challenger search

Self-consistency/ToT are useful when there is genuine candidate ambiguity.
vNext7 keeps only a bounded challenger mechanism. Branch agreement cannot close
a claim; the native verifier adjudicates.

### Reflexion

Reflection is useful only after a demonstrated failure exposes a specific repair
target. It remains one-shot and must return to verification.

### Mastermind

Mastermind is not an answer critic. It is a causal/process debugger used after
cheaper routes repeatedly fail. It finds the earliest distinct defect and
smallest repair/discriminator, then returns control to ordinary FOIL
verification.

## 6. Mechanisms deliberately not added

### Full LATS/tree search by default

It can increase search power, but it also increases cost, method stacking, and
causal ambiguity. A future operator is justified only if prospective
equal-budget evidence shows a regime where it beats bounded challenger search.

### Generic Self-Refine

Repeated same-model criticism can change prose without adding evidence. Keep
revision tied to demonstrated failure.

### Majority vote as truth

Multiple branches or agents can share the same false premise. Agreement is a
routing signal, not a verifier.

### Learned test-time compute allocation now

Recent work on adaptive test-time allocation is relevant to FOIL's future cost
policy, but learning a routing classifier from the current tiny benchmark history
would risk overfitting. vNext7 records explicit operator costs and decisions so a
prospective training set can be built later.

## 7. Promotion experiment

Do not promote this candidate from structural tests alone.

The prospective comparison should use the same underlying model, same items,
isolated sessions, and complete matched costs:

1. direct;
2. CoT / least-to-most;
3. ReAct where tools are applicable;
4. CoVe/CRITIC verifier baseline;
5. Reflexion after demonstrated failure;
6. bounded ToT/self-consistency challenger;
7. frozen FOIL V1;
8. vNext6;
9. vNext7.

Primary outputs:

- accuracy / task success;
- paired discordance;
- tool calls;
- inference tokens;
- latency;
- unnecessary-intervention rate;
- verifier completion rate;
- blocked/unresolved rate;
- answer reversal after verification;
- false closure rate.

Stratify by task regime. Do not pool incomparable tool-eligible and closed-book
tasks without reporting the strata.

## 8. Evidence boundary

Passing unit tests proves only that the implementation encodes these contracts.

It does **not** prove:

- vNext7 improves model behavior;
- cached qualification labels are correct;
- references are authentic;
- the routing thresholds are optimal;
- Self-Discover, challenger search, reflection, independent review, or Mastermind
  add positive value under matched budgets.

Those are prospective behavioral questions.
