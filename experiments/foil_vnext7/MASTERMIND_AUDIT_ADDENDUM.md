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

### Negative controls

The candidate tests require that:

- same `C1` + same verifier from another task cannot bypass a verifier/tool
  budget block;
- an evidence record from another task is rejected;
- a request cannot override the controller's task scope.

## Evidence boundary

These repairs establish structural isolation properties only if the repository
validation suite passes. They do not establish behavioral accuracy gains or the
truth of any cached evidence record.
