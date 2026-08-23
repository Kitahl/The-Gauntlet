# Research Orchestrator — engineering specification

## Obligation

Own task framing, obligation decomposition, routing, integration and release gating. Soul owns **control**, not domain truth.

## Current workflow

1. Read request/artifacts.
2. Restate task, success condition, constraints and stakes.
3. Select specialist skills by obligation.
4. Integrate outputs by evidence quality/scope.
5. Invoke Gauntlet when triggers are present.
6. Release supported result plus unresolved state.

## vNext typed workflow

1. `start_task(goal)` creates a `TaskState` and stores only `goal_hash` generically.
2. Create explicit `Obligation` objects with `kind`, `claim`, `load_bearing`, and `required_module`.
3. Optionally call Meditate when preflight triggers are explicitly represented.
4. Allow FOIL to adapt routing, never receipt authority.
5. Route each obligation to the mapped module.
6. Collect content-addressed receipts.
7. Add assurance/review obligations when needed.
8. Call `release_gate(task_id)`.
9. Release only if every load-bearing obligation has an appropriate `CLEARED` receipt. Otherwise report `ISSUE`, `UNKNOWN`, or `UNAVAILABLE` by obligation.

## State

`TaskState`, `Obligation`, active-task pointer, receipt index.

## Runtime

`tools/soul_runtime.py`

## Failure modes

- routing by topic instead of obligation;
- self-certification by the orchestrator;
- missing load-bearing receipt;
- tool failure converted to factual falsehood;
- FOIL/reviewer agreement mistaken for verification.

## Mechanical tests

- required module mapping;
- missing receipt blocks release;
- wrong-module receipt does not satisfy obligation;
- explicit `ISSUE` dominates success;
- `UNKNOWN` and `UNAVAILABLE` remain distinct.
