# FOIL vNext7 — Mastermind Causal/Mechanical Audit

Date: 2026-08-23

Candidate: `FOIL_vNEXT7_EVIDENCE_TYPED_POLICY_V1`

Parent: `feature/foil-vnext6-composable-controller`

Authority: Mastermind is used as a `PRE_REVIEW_ONLY` causal/mechanical
discipline. This document does not claim answer authority or behavioral
superiority.

## Admission law used

Every repair must satisfy the Mastermind mechanism-admission pattern:

1. causal adequacy;
2. identifier independence;
3. representation transformation/semantic robustness;
4. negative control;
5. cross-domain transfer;
6. compression into an existing mechanism where possible;
7. explicit ablation;
8. regression protection.

No benchmark-item rule is admitted.

---

# DEFECT 0 — Parent validation receipt had drifted from the current code

## Earliest causal defect

The current `experiments/foil_vnext6/execution_contract.py` uses the newer typed
API:

- `request_id`;
- `EvidenceVerdict`;
- `ClaimResolution`;
- `task_instance_id`;
- `admitted_claim_resolutions`.

But the inherited `tests/test_foil_vnext6_execution_contract.py` still used the
older API:

- `entails_claim`;
- `resolved_claim_ids`;
- no `task_instance_id`;
- `admitted_resolved_claim_ids`.

Therefore the earlier `41/41 PASS` statement in the execution audit cannot be
treated as evidence about the current branch state after that API change.

## Smallest repair

Realign the inherited execution-contract tests to the current API before adding
vNext7 tests.

The historical receipt is retained as historical evidence about the code it ran
against; it is not silently reinterpreted as a receipt for later code.

## Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | PASS | Removes a concrete false-green path: test code no longer matches implementation. |
| Identifier independence | PASS | Pure API/receipt consistency. |
| Negative control | PASS | No production routing behavior changes. |
| Cross-domain transfer | PASS | Applies to every typed execution path. |
| Existing-mechanism compression | PASS | Repair the tests; no new runtime mechanism. |
| Ablation | PASS-STRUCTURAL | Reverting restores stale-test mismatch. |
| Regression | PENDING-CI | Must be rerun by repository-compatible CI. |

---

# LOOP 1 — Evidence-bearing decisions did not always have executable targets

## Earliest causal defect

vNext6 requires explicit `target_claim_ids` for evidence-bearing requests.

Two paths can violate that contract.

### A. Regime-level verifier without atomic uncertainty

Frozen V1 can require:

- `CURRENT_SOURCE` because the regime is freshness-sensitive;
- `OUTPUT_CONTRACT` because an output contract is required.

These can exist with no unresolved `LoadBearingUncertainty`, leaving the runner
without a canonical claim ID even though the verifier is mandatory.

### B. Residual independent review loses verifier identity

After a native verifier completes but a decisive uncertainty remains, vNext6 can
select `INDEPENDENT_REVIEW` with `required_verifier=None`.

The runtime says the operation may discharge the uncertainty, but the execution
validator refuses claim resolution without a required verifier.

That is a policy/execution contradiction.

## Smallest mechanism

Add explicit `VerificationTarget` objects.

- Atomic uncertainties reuse their stable claim label/ID.
- Regime/output obligations receive a synthetic public target
  `O:<verifier>`.
- Independent-review escalation derives and preserves the native verifier from
  the frozen claim-kind mapping.

The vNext7 `build_request()` obtains targets directly from the controller.

## Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | PASS-SPEC | Directly closes the missing-target and missing-verifier contradictions. |
| Identifier independence | PASS | Targets are claim/verifier scoped, not task IDs. |
| Representation transformation | PASS-SPEC | Works for source, current-source, calculation, execution, examples, logical and output obligations. |
| Negative control | PASS | Non-evidence operators still have zero targets. |
| Cross-domain transfer | PASS-SPEC | Verifier kinds are domain-independent. |
| Existing-mechanism compression | PASS | Extends the existing request contract. |
| Ablation | PASS-STRUCTURAL | Remove target synthesis/preservation and both contradictions return. |
| Regression | TESTED-IN-CANDIDATE | Direct, STOP, Mastermind and branching remain non-verifying. |

---

# LOOP 2 — Discovery/verification separation could force duplicate acquisition

## Earliest causal defect

vNext6 correctly blocks this invalid transition:

`ReAct found source -> therefore claim verified`.

But its execution boundary can encourage a second external call even when ReAct
already captured exactly the material needed by the mandatory verifier.

This creates unnecessary:

- network/tool calls;
- latency;
- source drift between discovery and verification;
- budget exhaustion;
- duplicate side effects for executable environments.

That conflicts with FOIL's minimum-complement objective.

## Smallest mechanism

Separate three operations:

1. **acquisition** — ReAct captures an observation/reference;
2. **qualification** — the verifier checks the already-captured content against
   the exact target;
3. **admission** — the existing vNext6 validator decides whether the state delta
   is allowed.

vNext7 adds:

- `CachedEvidenceHint` to the runtime;
- content-addressed `CachedEvidenceRecord`;
- `QualificationKind`;
- zero-additional-tool-call repricing when every current verifier target is
  covered by eligible cached material.

Important negative control:

A cache hint is not evidence and cannot resolve a claim. The ordinary
claim-native verifier operator still runs and the parent admission validator
still controls closure.

## Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | PASS-SPEC | Removes duplicate acquisition without removing verification. |
| Identifier independence | PASS | Cache keys are target/verifier scoped. |
| Representation transformation | PASS-SPEC | Applies to source, calculation, execution and other captured verifier material. |
| Negative control | PASS-SPEC | Stale, wrong-verifier and non-fresh cached material cannot remove the external call. |
| Cross-domain transfer | PASS-SPEC | Receipt/content-addressed reuse is tool/provider neutral. |
| Existing-mechanism compression | PASS | Reuses vNext6 verifier and validator; no new truth layer. |
| Ablation | PASS-STRUCTURAL | Removing cache reuse restores duplicate acquisition. |
| Regression | TESTED-IN-CANDIDATE | Raw ReAct output remains non-verifying. |

---

# LOOP 3 — Evidence authority could be interpreted as a scalar prestige ladder

## Earliest causal defect

vNext6 names:

`NONE < INTERNAL_HEURISTIC < EXTERNAL_OBSERVATION < CLAIM_NATIVE < INDEPENDENT_REVIEW`

as an authority rank.

The basis-matching checks already prevent many mistakes, but a scalar order is
semantically misleading: an independent reviewer is not intrinsically stronger
than execution, exact calculation, a primary source, or a proof.

A second overreach appeared during vNext7 design: a generic
`MECHANICAL_CHECK` label could be mistaken for permission to certify source
entailment.

## Smallest mechanism

vNext7 keeps compatibility with the parent enum but exposes an explicit
**acceptance relation** instead of relying on prestige semantics:

- claim-native requirement -> claim-native or independent matched evidence;
- independent requirement -> independent matched evidence only.

Verifier/basis compatibility remains mandatory.

Mechanical qualification is allowed only for mechanical bases:

- execution;
- calculation;
- supplied-context consistency;
- output-contract checking.

Source entailment and proof/counterexample interpretation require a
claim-native or independent qualification process, not mere reproducibility.

## Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | PASS-SPEC | Removes independence-as-truth and mechanical-source-certification interpretations. |
| Identifier independence | PASS | Depends on evidence relation, not model/provider. |
| Representation transformation | PASS-SPEC | Basis-specific rule works across evidence types. |
| Negative control | PASS-SPEC | Mechanical source entailment is explicitly rejected. |
| Cross-domain transfer | PASS-SPEC | Evidence basis drives authority. |
| Existing-mechanism compression | PASS | Narrows the parent evidence law rather than adding a critic. |
| Ablation | PASS-STRUCTURAL | Removing the relation/restriction restores the ambiguity. |
| Regression | TESTED-IN-CANDIDATE | Native verifier/basis matching remains inherited from vNext6. |

---

# Method-admission decisions

## Admit as operators or compressed mechanisms

- **CoT / least-to-most** -> conditional `DECOMPOSE`.
- **Self-Discover** -> compress its task-specific structure-selection idea into
  complex decomposition; do not create a permanent extra loop yet.
- **ReAct** -> discovery/environment interaction.
- **PAL / PoT / CodeSteer mechanism** -> exact text-vs-symbolic/executable route.
- **CoVe / CRITIC** -> atomic claim-native verification.
- **Self-consistency / ToT** -> bounded challenger generation only.
- **Reflexion** -> one evidence-triggered targeted revision.
- **Independent review** -> high-impact residual uncertainty with preserved
  verifier.
- **Mastermind** -> late causal/process debugger, max three loops.

## Reject as defaults

- blanket CoT;
- majority vote as evidence;
- generic Self-Refine loops;
- persistent Reflexion memory during frozen evaluation;
- default LATS/full tree search;
- default multi-agent debate;
- Mastermind final-pass ritual.

## Defer pending prospective evidence

- learned adaptive test-time compute allocation;
- larger branch counts;
- learned operator router;
- task-specific persistent reasoning schemas.

The current evidence base is too small to train those without substantial
overfitting risk.

---

# Candidate tests added

vNext7 tests cover:

- atomic verifier targets;
- synthetic current-source target;
- synthetic output-contract target;
- residual independent-review verifier preservation;
- cached source reuse;
- recovery from external-tool budget exhaustion when qualified cached material
  exists;
- stale-cache negative control;
- current-source freshness negative control;
- STOP preservation;
- Mastermind non-authority;
- branching non-authority;
- controller-derived request targets;
- content SHA-256 requirement;
- wrong-basis rejection;
- outside-target rejection;
- independent-authority requirement;
- mechanical-source negative control;
- mechanical exact-calculation positive control;
- cached packet compatibility with the parent verifier admission path.

## Validation status

`PENDING-CI` until the repository-compatible test/lint workflow runs against the
actual branch.

No historical receipt is counted as a vNext7 pass.

---

# Behavioral promotion gate

Even if CI passes, vNext7 remains `STRUCTURALLY_VALIDATED_ONLY`.

Promotion requires prospective same-item equal-budget evidence against at least:

- direct;
- CoT/decomposition;
- ReAct/CoVe where applicable;
- Reflexion after failure;
- bounded challenger;
- frozen V1;
- vNext6;
- vNext7.

Measure accuracy/task success and complete cost, plus false closure,
unnecessary-intervention and unresolved/block rates.
