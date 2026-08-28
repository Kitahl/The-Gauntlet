---
name: meditate
description: Automatic Decision Preflight Protocol. Grounds consequential or unstable work in typed task state, derives represented pause triggers, and emits a bounded ACT/RELEASE/CONTINUE/SKIP preflight receipt without executing or clearing the target-domain claim.
---

# Decision Preflight Protocol

Use when execution may outrun the represented decision or evidence state.

## Preflight

`STILL → GROUND → ORIENT → WEIGH → RELEASE`

1. **STILL** — stop uncontrolled action expansion for one bounded pass.
2. **GROUND** — bind the current task, preflight obligation, authoritative artifacts,
   facts, assumptions, unknowns, and candidate actions.
3. **ORIENT** — restate goal, success condition, blocker, stakes, and reversibility.
4. **WEIGH** — derive automatic triggers and apply complete quantitative VOC or
   complete ordinal dominance.
5. **RELEASE** — emit `ACT`, `RELEASE`, `CONTINUE`, or `SKIP` as a preflight result.

Do not use Meditate as ceremonial delay. A simple, stable, reversible, well-specified
decision can clear as `SKIP` when no represented trigger is present.

## Automatic triggers

The runtime merges explicit and typed represented signals for:

- high stakes;
- irreversibility;
- stale authority;
- repeated failure;
- decision-sensitive unknowns;
- major disagreement.

Trigger coverage is scoped to typed represented state. Absence of a trigger is not a
claim that no real-world trigger exists.

## Decision rules

Quantitative VOC is used only when every candidate has a complete finite
probability/utility/cost model against one shared finite baseline. Partial quantitative
models remain `UNKNOWN`; they never fall back to ordinal ranks. A positive maximum tie
also remains `UNKNOWN`.

When no quantitative model is declared, complete ordinal ranks may identify one unique
nondominated action as `HEURISTIC`. Ties and incomplete ranks remain `UNKNOWN`.

## Authority boundary

```text
authority = PREFLIGHT_ONLY
execution_authorized = false
target_domain_clearance_authorized = false
```

Meditate can clear only a current task-bound `PREFLIGHT` obligation assigned to
`meditate`. It cannot execute the selected action or substitute for Mind, Space,
Reality, Power, Time, Council, Gauntlet, FOIL, or Black Gem evidence.

## Typed runtime contract

`tools/meditate_runtime.py` validates finite values and strict types, chooses the unique
active task revision for the preflight obligation, derives triggers from typed state and
events, content-binds the task and obligation, persists hashes rather than raw private
text, and emits a typed receipt. `runtime.automatic_preflight` enables automatic CLI
operation. See `docs/specs/MEDITATE_ENGINEERING_SPEC.md`.
