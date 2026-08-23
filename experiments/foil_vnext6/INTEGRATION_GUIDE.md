# FOIL vNext6 — Operator Integration Guide

Candidate: `FOIL_vNEXT6_COMPOSABLE_POLICY_V1`

Status: experimental, post-freeze, not the active public FOIL skill.

## 1. Integration rule

FOIL is the controller. CoT, ReAct, exact execution, CoVe/CRITIC, bounded
branching, Reflexion, independent review, and Mastermind are conditional
operators.

Do not build a fixed chain such as:

```text
CoT -> ReAct -> vote -> reflect -> Mastermind -> answer
```

Use one operator at a time:

```text
state
  -> frozen FOIL epistemic decision
  -> one vNext6 operator
  -> validated outcome
  -> admitted state delta
  -> state
```

## 2. End-to-end sequence

### Step A — create the frozen V1 task state

Populate `TaskContext` with only current task facts:

- task regime signals;
- whether a viable candidate exists;
- unresolved load-bearing uncertainties and claim kinds;
- completed claim-native verifiers;
- output contract requirements.

Load a `ProfileSignal` only when evidence supports it. Profile evidence cannot
remove a mandatory verifier.

### Step B — select one operator

Call:

```python
strategy = ComposableRuntimePolicy().decide(
    StrategyTaskContext(task_context, ...),
    StrategyBudget(...),
    profile_signal,
)
```

The decision contains:

- task regime;
- selected operator;
- public mechanism-family label;
- required verifier;
- minimum evidence authority;
- explicit cost;
- remaining budget;
- stop or blocked state.

### Step C — build a typed request

For evidence-bearing operators, provide the atomic target claim IDs:

```python
request = build_request(
    strategy,
    target_claim_ids=("C1", "C3"),
    tool_effect=ToolEffect.READ_ONLY,
)
```

For a side-effecting tool:

```python
request = build_request(
    strategy,
    tool_effect=ToolEffect.SIDE_EFFECTING,
    idempotency_key="stable-operation-key",
)
```

A retry additionally requires proof that the prior postcondition was checked.

### Step D — execute only the selected operator

The executor may use implementation-specific prompts or tools, but must obey the
operator's scope.

| Operator | Executor obligation |
| --- | --- |
| `DIRECT` | Produce one candidate without claiming verification. |
| `DECOMPOSE` | Decompose/solve; do not expose private scratchpad in receipts. |
| `REACT` | Interleave reasoning and observations; return discoveries as observations, not verified claims. |
| `EXACT_EXECUTION` | Run the exact calculation or executable check named by the verifier. |
| `CLAIM_NATIVE_VERIFY` | Test the named atomic claim with the named verifier. |
| `BOUNDED_CHALLENGER_SEARCH` | Produce materially distinct challengers within branch budget; do not use vote as proof. |
| `EVIDENCE_TRIGGERED_REFLECTION` | Revise only the demonstrated failure target; do not mark the revision correct. |
| `INDEPENDENT_REVIEW` | Review the exact claim and return claim-matched evidence, not agreement alone. |
| `MASTERMIND_CAUSAL_AUDIT` | Return one materially distinct earliest defect and smallest correction/discriminator. |
| `STOP` | Do nothing further. |
| `BLOCKED` | Preserve the unresolved state. |

### Step E — return a typed outcome

An evidence packet must identify:

- evidence ID;
- target claim ID;
- authority;
- verifier;
- evidence basis;
- reference/receipt;
- whether the evidence entails the claim;
- staleness;
- freshness check when applicable.

Example:

```python
packet = EvidencePacket(
    evidence_id="E-17",
    claim_id="C1",
    authority=EvidenceAuthority.CLAIM_NATIVE,
    verifier=VerifierKind.CURRENT_SOURCE,
    basis=EvidenceBasis.OFFICIAL_SOURCE,
    reference="receipt://source/17",
    entails_claim=True,
    freshness_checked=True,
)

outcome = OperatorOutcome(
    operator=strategy.operator,
    status=OutcomeStatus.COMPLETED,
    evidence=(packet,),
    completed_verifiers=frozenset({VerifierKind.CURRENT_SOURCE}),
    resolved_claim_ids=("C1",),
)
```

### Step F — validate before updating FOIL state

```python
validation = validate_outcome(strategy, request, outcome)
if not validation.valid:
    # Preserve the candidate/evidence receipt, but do not update claim status.
    ...
```

Only fields in:

- `admitted_resolved_claim_ids`; and
- `admitted_completed_verifiers`

may update the frozen V1 task state.

### Step G — re-enter the controller

After applying only admitted deltas, call the controller again. The next result
may:

- select a different operator;
- continue discovery;
- require another verifier;
- emit `STOP`;
- emit `BLOCKED`.

No operator may append itself automatically.

## 3. How the methods work together

### CoT / least-to-most

Use as `DECOMPOSE` when the task has multiple dependent subproblems or high
structural complexity. Its output is a candidate or subproblem structure, not
evidence.

### ReAct

Use during external discovery or sequential environment interaction. ReAct may
find a candidate and references. The candidate must then return to FOIL's
claim-native verifier schedule.

### CoVe and CRITIC

Use through `CLAIM_NATIVE_VERIFY` after a viable candidate exists. Verification
questions are derived from atomic load-bearing claims, and external tools are
selected by claim type.

### Self-consistency and Tree of Thoughts

Use only as a bounded challenger generator when multiple plausible candidates
materially disagree. Branch agreement is an internal heuristic. A verifier still
settles the claim.

### Reflexion

Use once after demonstrated failure with a specific target. A successful
reflection produces a revised candidate, which must be reverified.

### Independent review

Use for high-impact residual uncertainty when native evidence is unavailable or
inconclusive. Independence is necessary but insufficient; the review must return
claim-matched admissible evidence.

### Mastermind

Use after cheaper routes fail on a high-impact causal/process defect. Mastermind
returns a defect ID and smallest correction/discriminator. It cannot resolve the
answer claim. The corrected route returns to FOIL verification.

## 4. Side-effecting tools

For actions such as sending, deleting, purchasing, deploying, changing state, or
writing to an external system:

1. assign a stable idempotency key;
2. execute once;
3. verify the postcondition;
4. record a state fingerprint when available;
5. before retrying, check whether the first action already took effect;
6. admit completion only after the postcondition is verified.

Transport success, HTTP success, or an agent's statement that the action worked
is not enough.

## 5. High-stakes guideline verification

An official guideline can be represented as:

```python
basis=EvidenceBasis.OFFICIAL_GUIDELINE
```

It must still:

- be current when the claim is current;
- entail the exact atomic claim;
- match the selected source verifier;
- remain within the guideline's scope and population;
- not be treated as a universal rule outside its context.

Domain-specific guideline compilation belongs in a separate verified package,
not the universal controller.

## 6. Public receipt boundary

Public traces contain only policy and evidence metadata. Never write:

- private chain-of-thought;
- hidden scratchpads;
- benchmark gold;
- raw sensitive prompts;
- unredacted personal data;
- unsupported confidence narratives.

Store evidence references and minimal state transitions instead.

## 7. Promotion gate

Do not promote vNext6 into active FOIL from structural tests alone.

Required prospective comparison:

- strong direct baseline;
- CoT/decomposition;
- ReAct or CoVe/CRITIC baseline where applicable;
- Reflexion after failure;
- frozen V1;
- vNext6 without execution admission;
- full vNext6 with execution admission.

Use same items, isolated sessions, matched complete cost, frozen routing rules,
pre-registered exclusions, task-regime stratification, and negative controls.
