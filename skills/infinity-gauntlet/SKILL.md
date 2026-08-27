---
name: infinity-gauntlet
description: Process Assurance Framework. Trigger: /gauntlet, a release attempt, repeated failed attempts, ungated kill/finding, last-surviving option, inherited number, stale authority, cross-context handoff, unclear architecture, or an all-green verification claim. Audits the frame and process behind a result, using the smallest triggered assurance schedule rather than ritualizing every check.
---

# Process Assurance Framework

Gauntlet is a narrow assurance layer worn by the Research Orchestrator. It examines represented process hazards that ordinary candidate verification may miss. It never substitutes for proof, source assessment, execution, evaluation, or host adoption.

Runtime automation is external to this skill:

- `.claude/settings.json`
- `.gauntlet.json`
- `tools/gauntlet_boundary.py`
- `tools/gauntlet_monitor.py`
- `tools/gauntlet_hook.py`
- `tools/gauntlet_runtime.py`
- `tools/verify_ledger.py`
- optional `tools/scout.py`, `tools/blackgem_runtime.py`, `tools/snap.py`

See `docs/RUNTIME_SETUP.md` and `docs/specs/GAUNTLET_ENGINEERING_SPEC.md`.

## Ten operations

| operation | trigger | discriminator |
|---|---|---|
| `frame` | repeated failures share a signature | determine whether the same representation or assumption is failing |
| `audit` | release is attempted | inspect current task-scoped load-bearing receipts, excluding Gauntlet's own circular obligation |
| `costume` | novelty or last-survivor claim | require a current source-assessed prior-art receipt |
| `derive` | inherited number or label becomes a premise | require a task-scoped cleared Mind derivation |
| `self` | load-bearing evidence is attached | compare producer, verifier, and provenance; missing provenance is unresolved |
| `redirect` | repeated work may be stagnant | compare frozen blocker and progress hashes |
| `refresh` | governing state may be stale | use the latest registered authority event, so a fresh reread can supersede earlier drift |
| `boundary` | handoff or concurrent ownership transfer | require a non-empty handoff ID and content-bound contract |
| `explain` | explanation and artifact may diverge | compare fully bound claim IDs and hashes; free-text entailment remains assisted |
| `oob` | release is attempted after ordinary checks pass | require a valid, verifier-identified, artifact/scope-bound probe for a named failure class |

## Typed runtime contract

`tools/gauntlet_runtime.py` preserves the ten-operation registry and adds task-scoped minimal planning, frozen coverage/minimality certificates, single-snapshot execution, strict `ASSURANCE_ONLY` authority, and one compact aggregate receipt. Legacy single-operation monitoring remains available for explicit compatibility calls.

The existing Stop-hook recursion guard remains active through `stop_hook_active`; this upgrade does not weaken or replace the hook boundary.

## Minimal assurance planner

Do not run all ten operations by default.

1. Freeze the current task, valid task-scoped load-bearing receipts, typed events, caller budget, and mode.
2. Derive only the hazards whose triggers are present.
3. Rank them deterministically by risk, information value, complete cost units, and stable operation name.
4. Select a budget-feasible prefix and record any uncovered triggered hazard.
5. In `RELEASE_GATE`, stop after the first blocking `ISSUE`; in `DIAGNOSTIC`, execute the whole selected schedule.
6. Emit one compact assurance receipt containing the plan, coverage certificate, minimality certificate, results, and derived cost-unit diagnostics.

Budget exclusion never becomes `CLEARED`. A triggered load-bearing hazard left unevaluated keeps the aggregate result `UNKNOWN`.

The planner borrows only general mechanics:

- FOIL-style task-local gaps and minimum discriminators;
- Foundry-style explicit route availability, AUTO scheduling, and complete-cost comparison;
- Mastermind-style frozen mechanisms, negative controls, coverage/minimality certificates, and no self-promotion.

Gauntlet imports none of those control planes. It does not import `foil_*`, execute Foundry, or advance Mastermind state.

## Tools and token discipline

Typed checks run before semantic tools. The minimal planner scans the task ledger once, reuses that frozen snapshot across selected operations, and emits one aggregate receipt. It does not call a model merely to restate a deterministic issue.

An assisted semantic capability may be proposed only when typed evidence cannot decide the relevant operation. Tool output remains an observation and cannot clear a target-domain obligation.

Reported `cost_units` are deterministic planning units, not measured model tokens, money, CPU, or scientific performance. Token-efficiency and benchmark-score gains require prospective matched evaluation.

## Result semantics

- `ISSUE`: a represented process hazard is established.
- `UNAVAILABLE`: a required method or capability cannot run.
- `UNKNOWN`: evidence is absent, incomplete, unbound, provenance-ambiguous, or excluded by budget.
- `CLEARED`: every selected triggered hazard cleared and no triggered hazard was omitted by the frozen budget.

`CLEARED` applies only to an `ASSURANCE` obligation. It cannot clear proof, discovery, synthesis, engineering, evaluation, review, adaptation, or adversary obligations.

## Output

**PROCESS ASSURANCE**
- Plan: `<plan hash and mode>`
- Fired: `<executed operations>`
- Uncovered: `<triggered operations excluded by budget>`
- Claim/frame: `<target>`
- Evidence inspected: `<task-scoped artifact/receipt/event hashes>`
- Counterevidence: `<strongest live challenger>`
- Result: `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE`
- Consequence: `<what may or may not proceed>`
- Next discriminator: `<only when unresolved>`
- Cost status: `DERIVED_NOT_TOKENS`
- Efficacy status: `NOT_ESTABLISHED` unless prospectively measured

## Next upgrade boundary

After this Gauntlet slice is complete and independently accepted, the next Gem to examine is **Soul / Research Orchestrator**. No Soul behavior is changed by this upgrade.
