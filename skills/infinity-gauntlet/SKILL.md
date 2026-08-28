---
name: infinity-gauntlet
description: Process Assurance Framework. Trigger: /gauntlet, release attempts, repeated failures, ungated findings, last-surviving options, inherited values, stale authority, handoffs, unclear architecture, or all-green claims. Runs automatically and preserves full applicable release assurance; selective reduction is experimental only.
---

# Process Assurance Framework

Gauntlet is the automatic process-assurance layer worn by the Research Orchestrator. It examines represented process hazards that ordinary candidate verification may miss. It never substitutes for proof, source assessment, execution, evaluation, or host adoption.

Runtime automation is external to this skill:

- `.claude/settings.json`
- `.gauntlet.json`
- `tools/gauntlet_boundary.py`
- `tools/gauntlet_monitor.py`
- `tools/gauntlet_hook.py`
- `tools/gauntlet_runtime.py`
- `tools/gauntlet_automatic.py`
- `tools/verify_ledger.py`
- optional `tools/scout.py`, `tools/blackgem_runtime.py`, `tools/snap.py`

See `docs/RUNTIME_SETUP.md`, `docs/specs/GAUNTLET_ENGINEERING_SPEC.md`, and `docs/specs/GAUNTLET_AUTOMATIC_SPEC.md`.

## Ten operations

| operation | trigger | discriminator |
|---|---|---|
| `frame` | repeated failures share a signature | determine whether the same representation or assumption is failing |
| `audit` | release is attempted | inspect current task-scoped load-bearing receipts, excluding Gauntlet's own circular obligation |
| `costume` | novelty or last-survivor claim | require a current source-assessed prior-art receipt |
| `derive` | inherited number or label becomes a premise | require a task-scoped cleared Mind derivation |
| `self` | load-bearing evidence is attached | compare producer, verifier, and provenance; missing provenance is unresolved |
| `redirect` | repeated work may be stagnant | compare frozen blocker and progress hashes |
| `refresh` | governing state may be stale | require a current registered authority state and content-bound reconciliation where applicable |
| `boundary` | handoff or concurrent ownership transfer | require a non-empty handoff ID and content-bound contract |
| `explain` | explanation and artifact may diverge | compare fully bound claim IDs and hashes; free-text entailment remains assisted |
| `oob` | release is attempted after ordinary checks pass | require a valid, verifier-identified, artifact/scope-bound probe for a named failure class |

## Typed runtime contract — automatic default

`tools/gauntlet_runtime.py` remains the low-level registry and monitor implementation. `tools/gauntlet_automatic.py` is the default controller.

At release, `AUTOMATIC_FULL`:

1. freezes one task-scoped event/receipt snapshot;
2. determines which canonical operations are currently applicable;
3. executes **every applicable operation**, not a budget-reduced prefix;
4. ignores structural budgets as advisory rather than silently omitting release checks;
5. runs the complete applicable sweep even after the first issue so one repair cycle can expose all represented blockers;
6. verifies the internal RuntimeStore receipt→event chain used by the monitors;
7. emits one compact `ASSURANCE_ONLY` receipt.

Selective, budget-constrained, or early-stop execution remains available only through explicitly named `*_EXPERIMENTAL` policies. Those modes cannot be confused with the production automatic path.

The existing Stop-hook recursion guard remains active through `stop_hook_active`; this upgrade does not weaken or replace the hook boundary.

## Automaticity without silent capability loss

Gauntlet remains automatic. No human must choose individual checks at release. The controller uses triggers to determine applicability and ordering, but the production release mode does not use those triggers to discard applicable checks.

If the persisted receipt/event chain is incomplete, the result is `UNKNOWN`; a broken event chain cannot manufacture a green assurance receipt. This check is scoped to `RUNTIME_STORE_REPRESENTED_HAZARDS`. It does not claim that every possible real-world hazard was represented.

The controller borrows only general mechanics:

- FOIL-style task-local discriminators and explicit uncertainty;
- Foundry-style route availability and cost accounting;
- Mastermind-style frozen state, negative controls, and no self-promotion.

Gauntlet imports none of those control planes. It does not import `foil_*`, execute Foundry, or advance Mastermind state.

## Tools and token discipline

Typed checks run before semantic tools. The automatic controller scans the task ledger once, reuses that frozen snapshot, and emits one aggregate receipt. It does not call a model merely to restate a deterministic issue.

An assisted semantic capability may be routed automatically when typed evidence cannot decide the relevant operation, but tool output remains an observation and cannot clear a target-domain obligation.

Reported `cost_units` are an `UNCALIBRATED_ORDERING_PROXY`, not measured model tokens, money, CPU, latency, or scientific performance. Token-efficiency and benchmark-score gains require prospective matched evaluation.

## Result semantics

- `ISSUE`: a represented process hazard is established.
- `UNAVAILABLE`: a required method or capability cannot run.
- `UNKNOWN`: evidence is absent, incomplete, unbound, provenance-ambiguous, or the RuntimeStore event chain is incomplete.
- `CLEARED`: every applicable operation cleared and the represented runtime event chain is internally complete.

`CLEARED` applies only to an `ASSURANCE` obligation. It cannot clear proof, discovery, synthesis, engineering, evaluation, review, adaptation, or adversary obligations.

## Output

**PROCESS ASSURANCE**
- Plan: `<plan hash and automatic mode>`
- Applicable: `<all applicable canonical operations>`
- Executed: `<all applicable operations in production full mode>`
- Deferred: `<experimental modes only>`
- Claim/frame: `<target>`
- Evidence inspected: `<task-scoped artifact/receipt/event hashes>`
- Counterevidence: `<strongest live challenger>`
- Runtime event coverage: `ESTABLISHED_RUNTIME_EVENT_CHAIN | UNKNOWN_RUNTIME_EVENT_CHAIN`
- Result: `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE`
- Consequence: `<what may or may not proceed>`
- Next discriminator: `<only when unresolved>`
- Cost status: `UNCALIBRATED_ORDERING_PROXY`
- Efficacy status: `NOT_ESTABLISHED` unless prospectively measured

## Portable runtime

Before using a named tool, path, solver, API, or profile:

1. verify it exists in the active environment;
2. use it if present;
3. otherwise route to an explicitly available equivalent or report `UNAVAILABLE`;
4. never invent tool output or background execution.
