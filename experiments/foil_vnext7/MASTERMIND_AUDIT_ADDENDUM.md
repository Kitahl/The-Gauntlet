# FOIL vNext7 — Mastermind Audit Addendum

Date: 2026-08-23

Candidate: `FOIL_vNEXT7_EVIDENCE_TYPED_POLICY_V1`

This addendum records defects found after the initial vNext7 causal audit and
before any behavioral promotion claim.

## LOOP 4 — Cache reuse could downgrade an independence requirement

### Defect

The first cache-reuse implementation allowed cached material to reprice any
verification operator, including `INDEPENDENT_REVIEW`, into ordinary
claim-native verification. That could erase the very independence property that
caused the escalation.

### Repair

Cached material can remove repeat acquisition only for ordinary claim-native or
exact-execution verification. A selected independent-review operator is never
downgraded by a generic cache hint.

### Negative control

`test_16_cache_cannot_downgrade_independent_review` supplies matching cached
material during a high-impact residual independent-review route and requires:

- operator remains `INDEPENDENT_REVIEW`;
- minimum authority remains `INDEPENDENT_REVIEW`;
- `reuse_cached_evidence` remains false.

## LOOP 5 — Task-local claim IDs allowed cross-task cache replay

### Defect

Targets such as `C1` are only unique inside a task. A cache indexed by
`(target_id, verifier)` alone could therefore accidentally reuse evidence from a
different task that also happened to contain `C1`.

That is a contamination path and fails Mastermind's identifier-independence and
negative-control requirements.

### Repair

Cache and decision state are now explicitly scoped by `task_instance_id`:

- `EvidenceTypedTaskContext` requires a nonempty task instance ID;
- `CachedEvidenceHint` carries the task instance ID and only affects routing in
  the same task;
- `EvidenceTypedDecision` carries the task scope;
- `CachedEvidenceRecord` carries the task scope;
- cache qualification rejects a different task scope;
- request construction uses the decision's task scope and rejects a conflicting
  caller-supplied scope.

The parent vNext6 request object deliberately does not expose the raw task ID.
Instead, vNext6 includes `task_instance_id` in the canonical request SHA-256.
vNext7 therefore validates request scope by recomputing the expected request
identity under the decision's task scope. This preserves the parent request
schema while keeping the task binding machine-checkable.

### Negative controls

The candidate tests require that:

- same `C1` + same verifier from another task cannot bypass a verifier/tool
  budget block;
- an evidence record from another task is rejected;
- a request cannot override the controller's task scope;
- otherwise-identical decisions in different task scopes produce different
  request IDs.

## LOOP 6 — ReAct discovery was mislabeled as a verification target

### Defect

vNext6 correctly marks `REACT` as non-verifying, but its strategy decision can
carry the verifier whose evidence ReAct is trying to discover. The first vNext7
wrapper converted any non-null `required_verifier` into a
`VerificationTarget`, even when the selected operator could not discharge a
claim.

That blurred the acquisition/verification boundary and gave an executor no
explicit machine-readable target for *which missing information* ReAct should
seek.

### Smallest mechanism

Do not add another reasoning loop. Split targeting by epistemic role:

- `verification_targets` exist only when the selected operator is authorized to
  discharge a load-bearing uncertainty;
- `REACT` receives `discovery_target_ids` instead;
- external/fresh atomic uncertainties reuse their stable claim labels;
- sequential external work with no stable atomic claim receives the synthetic
  target `D:external_observation`;
- the public discovery objective is
  `load_bearing_information_gain_per_cost`.

This compresses the useful mechanism from uncertainty-aware information seeking
and adaptive retrieval control into the existing ReAct operator: choose the
observation/query that most economically discriminates the decisive uncertainty,
and stop when further retrieval has no expected answer-changing/evidence value.

It does **not** add a permanent simulation tree, treat model probabilities as
evidence, or allow ReAct observations to close claims.

### Gates

| Gate | Result | Reason |
| --- | --- | --- |
| Causal adequacy | PASS-SPEC | Separates discovery from claim closure and directly targets the missing information. |
| Identifier independence | PASS | Targets are task-local uncertainty labels or a generic synthetic discovery obligation. |
| Representation transformation | PASS-SPEC | Applies to web retrieval, sequential tools and mixed external environments. |
| Negative control | TESTED-IN-CANDIDATE | ReAct has zero verification targets and remains non-verifying. |
| Cross-domain transfer | PASS-SPEC | Objective is uncertainty/cost based, not domain keyed. |
| Existing-mechanism compression | PASS | Extends ReAct targeting rather than adding a new UoT/DeepControl loop. |
| Ablation | PASS-STRUCTURAL | Removing discovery targeting restores untargeted acquisition/target-role conflation. |
| Regression | PENDING-CI | Must pass the repository validation suite on the final head. |

## Evidence boundary

These repairs establish structural properties only if the repository validation
suite passes. They do not establish behavioral accuracy gains, calibration of
the information-gain objective, or the truth of any cached evidence record.
