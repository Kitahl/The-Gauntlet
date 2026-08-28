# Decision Preflight / Meditate — automatic engineering specification

## Obligation

Meditate prevents execution from outrunning the represented decision and evidence
state. It is a bounded metareasoning controller, not an extra opinion and not a target-
domain verifier.

Its authority is exactly:

```text
authority = PREFLIGHT_ONLY
execution_authorized = false
target_domain_clearance_authorized = false
```

A clearing Meditate receipt can satisfy only a task-bound `PREFLIGHT` obligation whose
required module is `meditate`. It cannot establish that the selected action is correct,
execute the action, or clear a proof, discovery, implementation, evaluation, review, or
assurance obligation.

## Workflow

`STILL → GROUND → ORIENT → WEIGH → RELEASE`

1. **STILL** — prevent uncontrolled action expansion for one bounded control pass.
2. **GROUND** — bind the current task, preflight obligation, authoritative artifacts,
   facts, assumptions, unknowns, and candidate action set.
3. **ORIENT** — represent the goal, success condition, blocker, stakes, reversibility,
   and current best expected utility when a quantitative model exists.
4. **WEIGH** — derive automatic triggers and apply either complete quantitative
   value-of-computation or complete ordinal dominance.
5. **RELEASE** — emit `ACT`, `RELEASE`, `CONTINUE`, or `SKIP` as a preflight result.
   No result authorizes execution.

## Typed state

`DecisionState` contains:

- `decision_id` and optional `task_id`;
- goal and success condition;
- authoritative artifact descriptors;
- supported facts;
- assumptions;
- decision-sensitive unknowns;
- candidate actions;
- current blocker;
- one shared `current_best_eu` baseline for quantitative comparison;
- explicit preflight trigger flags.

Candidate action identifiers must be unique. Ranks are integers in `[0, 5]`. Boolean
fields are strict booleans. Every numeric probability, utility, cost, expectation, and
VOC result must be finite.

Caller-owned lists and mappings are copied through canonical serialization before
assessment and content binding, so later source mutation cannot change the persisted
preflight product.

## Automatic triggers

A preflight is triggered when any represented source indicates:

- high stakes;
- an irreversible candidate or explicit irreversibility;
- authority change newer than the latest authority snapshot;
- repeated failure, defined as either a repeated failure signature or three recent
  represented failures;
- a decision-sensitive unknown;
- major reviewer or Council disagreement.

Triggers are merged monotonically across explicit state, task metadata, obligation
metadata, candidate reversibility, unknown annotations, and typed task events. A later
minor disagreement cannot erase an earlier major disagreement.

The trigger claim is deliberately scoped:

```text
trigger_scope = TYPED_REPRESENTED_STATE_ONLY
trigger_completeness_established = false
```

Meditate does not claim that every real-world reason to pause was represented.

## Quantitative decision rule

Quantitative mode is used only when all candidates have:

- one finite non-negative cost;
- at least one finite outcome;
- outcome probabilities in `[0, 1]` summing to one;
- a shared finite `current_best_eu` baseline.

For candidate `a`:

```text
VOC(a) = E[best EU after observing O_a] - current_best_eu - C(a)
```

Rules:

- unique maximum positive VOC → `ACT`;
- maximum VOC `<= 0` → `RELEASE`;
- multiple candidates tied for positive maximum VOC → `UNKNOWN`;
- any partially declared quantitative model → `UNKNOWN` and no ordinal fallback;
- non-finite intermediate or final arithmetic → reject the model.

The tie rule is deterministic and input-order invariant.

## Ordinal decision rule

Ordinal mode is used only when no quantitative model is declared and every candidate
has all four ranks:

- information gain;
- progress;
- risk reduction;
- cost.

A candidate dominates another only when it is no worse on all benefit ranks and cost,
and strictly better on at least one dimension. A unique nondominated candidate yields a
`HEURISTIC` `ACT` result. Multiple nondominated candidates remain `UNKNOWN`. All-zero
benefit ranks yield `RELEASE` as a heuristic preflight result.

Ordinal output is never reclassified as factual evidence.

## Task and obligation binding

For an authoritative clearing receipt:

- the obligation must exist on one current active unreleased task;
- the obligation kind must be `PREFLIGHT`;
- its required module must be `meditate` or unspecified;
- the receipt carries the resolved `task_id`;
- the state record and evidence carry the task content hash and obligation binding hash.

When the same obligation is present in predecessor and successor revisions, Meditate
selects the unique active unreleased revision. Multiple active matches, multiple closed
matches without a unique current task, missing content, inactive tasks, and released
tasks fail closed.

An unbound result that would otherwise be `CLEARED` is demoted to `UNKNOWN` with
`mode = UNBOUND_PREFLIGHT`.

## Privacy and persistence

The persisted Meditate state contains:

- hashes of goal, success condition, artifacts, facts, assumptions, unknowns, action
  labels, action models, blocker, task, and obligation binding;
- structural action identifiers and model-presence flags;
- represented triggers and the bounded result;
- explicit authority and non-execution fields.

It does not persist raw goal text, raw success-condition text, or raw action labels.
Receipt notes contain only the bounded decision result.

## Automatic runtime

`tools/meditate_runtime.py` provides:

- `derive_triggers`;
- `recommend`;
- `run_preflight`;
- `run_automatic_preflight`;
- a CLI with `--automatic` and project configuration support through
  `runtime.automatic_preflight`.

Automatic operation means trigger derivation and bound preflight evaluation occur once
a typed `DecisionState` and candidate action set exist. Meditate does not invent actions
from raw prompts or execute the recommended action.

## Required negative controls

Mechanical tests must include:

- strict booleans and finite numeric validation;
- duplicate action rejection;
- partial quantitative-model rejection;
- quantitative tie and input-order invariance;
- non-finite VOC intermediate rejection;
- automatic irreversible, stale-authority, repeated-failure, unknown, and disagreement
  triggers;
- later minor disagreement not erasing earlier major disagreement;
- task-trigger bypass prevention;
- wrong-kind and wrong-module rejection;
- inactive/released/ambiguous task rejection;
- active successor selection;
- unbound-clear demotion;
- raw-text persistence checks;
- task and obligation content binding.

## Evidence boundary

Mechanical validation can establish schema, finite arithmetic, deterministic selection,
represented trigger derivation, authority separation, task binding, and privacy. It does
not establish calibrated utilities, complete action generation, globally optimal
metareasoning, complete trigger recall, lower production cost, or improved task outcomes.
Those require prospective matched evaluation.
