---
name: meditate
description: Preflight — decision-grounding module for Rigilum Instrument 01. Route-invoked step before consequential action, after repeated failure, or when the task frame is unstable. Produces a compact state/goal/evidence/next-action reset rather than an additional opinion.
---

# Preflight

Use when execution is about to outrun the evidence state.

## Preflight sequence

`STILL → GROUND → ORIENT → WEIGH → RELEASE`

1. **STILL** — stop adding new mechanisms for one pass.
2. **GROUND** — identify the actual artifact/state/source currently authoritative.
3. **ORIENT** — restate goal, success condition, constraints, and current blocker.
4. **WEIGH** — separate supported facts, assumptions, unknowns, and irreversible costs.
5. **RELEASE** — choose the single next action with the highest information/progress value.

Do not use this protocol as ceremonial delay. If the task is simple, stable, reversible, and well-specified, skip it.

## Typed runtime contract

`tools/meditate_runtime.py` represents the preflight as a `DecisionState`. Numeric value-of-computation is used only when probabilities, utilities and costs are explicitly supplied and valid. Otherwise the stable meditate runtime uses labeled ordinal dominance or returns `UNKNOWN`; it never invents pseudo-precise values. See `docs/specs/MEDITATE_ENGINEERING_SPEC.md`.

## Compatibility

Public product name: **Preflight**. Stable technical identity: `meditate`. **Decision Preflight Protocol** is the legacy public label retained in historical documentation and receipts.