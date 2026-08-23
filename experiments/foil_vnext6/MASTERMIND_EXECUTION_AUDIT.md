# FOIL vNext6 — Three-Loop Mastermind Execution-Boundary Audit

Date: 2026-08-23

Target: typed integration between the vNext6 strategy selector and actual
reasoning/tool executors.

Authority: `PRE_REVIEW_ONLY`. This is a structural causal audit, not behavioral
or answer authority.

## LOOP 1 — Selection was not execution

### Earliest causal defect

The strategy controller returned an operator enum, reason code, verifier, and
budget, but no typed request contract told an executor:

- which atomic claims were targeted;
- whether the tool was read-only or side-effecting;
- what authority was required;
- what retry semantics applied.

A correct policy decision could therefore be executed by an incompatible prompt
or tool call without a machine-detectable mismatch.

### Smallest mechanism

Add `OperatorRequest` and `build_request()`:

- bind the request to the controller version and operator;
- bind evidence-bearing work to explicit claim IDs;
- carry the required verifier and minimum authority;
- type tool effects;
- require idempotency for side effects;
- require verify-before-retry on repeated side effects.

### Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | `PASS-SPEC` | Closes the policy-to-executor semantic gap. |
| Identifier independence | `PASS` | Uses generic claim IDs and operator metadata. |
| Negative control | `PASS-SPEC` | Direct and read-only work require no side-effect machinery. |
| Existing-mechanism compression | `PASS` | Extends vNext6 rather than adding another controller. |
| Ablation | `PASS-STRUCTURAL` | Without the request, executor scope and claim targets are unaudited. |

## LOOP 2 — Outcomes could self-attest success

### Earliest causal defect

An executor could return `resolved=True` or `verifier completed` without proving:

- that evidence targeted the same claim;
- that the verifier matched;
- that the evidence basis was appropriate;
- that the source entailed the claim;
- that the source was fresh and non-stale;
- that the authority threshold was met.

This would let CoT, ReAct discovery, reflection, branching, or Mastermind
self-promote into evidence.

### Smallest mechanism

Add `EvidencePacket`, `OperatorOutcome`, and `validate_outcome()`:

- claim ID, evidence ID, verifier, authority, basis, reference, entailment,
  staleness, and freshness are explicit;
- only claim-native or qualified independent evidence packets can enter the
  admission path;
- verifier-to-basis compatibility is checked;
- current-source evidence requires freshness confirmation;
- non-verifying operators cannot resolve claims or complete verifiers;
- only admitted claim IDs and verifiers may update frozen V1 state.

### Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | `PASS-SPEC` | Blocks self-attested claim closure. |
| Representation transformation | `PASS-SPEC` | Applies to sources, calculations, execution, proof, supplied context, and output contracts. |
| Negative control | `PASS-SPEC` | A polished revision or agent agreement remains non-evidence. |
| Cross-domain transfer | `PASS-SPEC` | Evidence basis changes by verifier, not by hard-coded task ID. |
| Ablation | `PASS-STRUCTURAL` | Removing packet matching admits stale, wrong-verifier, or non-entailing evidence. |

## LOOP 3 — Tool calls were treated as atomic

### Earliest causal defect

A side-effecting tool can time out after dispatch, partially update state, or
become visible later. Treating a returned status as atomic success can produce:

- duplicate sends or writes;
- repeated deletion/deployment;
- incorrect completion receipts;
- retries that compound partial effects;
- evidence based on stale state snapshots.

### Smallest mechanism

Add tool-effect and postcondition controls:

- `ToolEffect.SIDE_EFFECTING` requires an idempotency key;
- retries require prior postcondition checking;
- completed side effects require `postcondition_verified=True`;
- outcomes may carry an observed-state fingerprint;
- stale evidence cannot resolve claims;
- outcomes are classified as progressed, stalled, or blocked from concrete
  state deltas.

### Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | `PASS-SPEC` | Directly addresses non-atomic tool failures and duplicate actions. |
| Negative control | `PASS-SPEC` | Read-only reasoning/search avoids side-effect overhead. |
| Cross-domain transfer | `PASS-SPEC` | Applies to email, deployment, storage, purchases, calendar changes, and other external mutations. |
| Existing-mechanism compression | `PASS` | Strengthens the operator receipt rather than adding a new reasoning method. |
| Ablation | `PASS-STRUCTURAL` | Removing postcondition/idempotency checks allows false completion and unsafe retry. |

## Defects caught during implementation

1. **ReAct authority leak:** discovery evidence could be represented by a
   claim-native packet. The validator now rejects verifier authority from the
   `REACT` operator; discovery must return to a separate verifier operation.
2. **Freshness omission:** a `CURRENT_SOURCE` packet could otherwise use an
   official source without proving recency. `freshness_checked=True` is
   mandatory.
3. **Basis mismatch:** a calculation could otherwise be submitted as source
   evidence. Every verifier has an allowed evidence-basis set.
4. **Terminal mutation:** `STOP`/`BLOCKED` outcomes could otherwise report state
   changes. Terminal operators now reject candidate, evidence, verifier,
   resolution, defect, and postcondition deltas.
5. **Mastermind self-closure:** a completed Mastermind outcome without a
   distinct defect ID is rejected, and Mastermind cannot resolve claims.

## Validation

- combined repository-compatible unit tests: **41/41 PASS**;
- execution trace schema validation: **PASS**;
- policy trace schema regression: **PASS**;
- seeded evidence-admission fuzzing: **50,000 cases PASS**;
- non-verifying-operator forged-resolution attacks: **PASS**;
- side-effecting unsafe-retry attacks: **PASS**;
- Python compilation: **PASS**;
- Ruff: **NOT MEASURED** in the isolated runtime.

## What remains unproven

- that live executors faithfully emit the typed outcome;
- that references/receipts themselves are authentic;
- that an entailment flag is correctly assigned without an independent checker;
- that postcondition checkers are complete;
- that official guidelines are correctly scoped;
- that progress classification improves accuracy/cost;
- that vNext6 outperforms established baselines behaviorally.
