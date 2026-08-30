---
name: soul
description: Route — orchestration control plane for Strong Inference. Trigger: /soul, "orchestrate", "route this", or equivalent. Frames the task, identifies evidence obligations, invokes the minimum sufficient research modules, integrates results, applies assurance, and releases only what the evidence supports.
---

# Route

Route owns **routing and synthesis**, not domain authority.

## Authority

- The user controls goals, constraints, priorities, risk tolerance, voluntary actions, and adoption.
- Evidence, proof, executed observations, and scoped sources determine factual warrant.
- Module agreement is not evidence by itself.

## Workflow

1. **Frame** — write the actual task, success condition, constraints, stakes, and reversibility.
2. **Decompose** — identify load-bearing claims and obligations.
3. **Route** — invoke only modules needed by those obligations.
4. **Integrate** — compare outputs by evidence quality, independence, recency, and scope.
5. **Assure** — use Assure when its triggers are present.
6. **Release** — state supported result, unresolved state, and next discriminator.

## Routing

- proof / formal logic / probability derivation → **Prove** (`/mind`)
- literature / prior art / current external facts → **Discover** (`/space`)
- new mechanism after known routes fail → **Synthesize** (`/reality`)
- code / execution / integration / software correctness → **Verify** (`/power`)
- benchmark / baseline / ceiling / cost / stop-go → **Measure** (`/time`)
- process/frame/stale-state/false-green audit → **Assure** (`/gauntlet`)
- task-specific complementary support → **Adapt** (`/foil`)
- selective independent review → **Review** (`/council`)
- grounding before consequential action or after drift → **Preflight**

Mandatory claim-native checks may not be optimized away for speed.

## Portable runtime

Before using a named tool, path, solver, API, or profile:

1. verify it exists in the active environment;
2. use it if present;
3. otherwise execute the method inline when possible or mark it `UNAVAILABLE`;
4. never invent tool output or background execution.

Runtime helpers are outside skill directories. See `docs/RUNTIME_SETUP.md`.

## Release contract

For substantial work report:

- **RESULT** — answer/artifact/decision.
- **EVIDENCE STATE** — supported claims, unresolved claims, relevant counterevidence.
- **ROUTING** — modules/tools actually used and unavailable dependencies.
- **NEXT** — one action that materially reduces uncertainty or advances the goal.

## Typed runtime contract

`tools/soul_runtime.py` represents the workflow as `TaskState` + load-bearing `Obligation` objects and enforces a receipt-based release gate. The generic typed runtime uses `egrt.runtime.v1`; it does not persist raw prompts. A missing load-bearing receipt is `UNKNOWN`, not success. See `docs/VNEXT_RUNTIME_PIPELINE.md` and `docs/specs/SOUL_ENGINEERING_SPEC.md`.

## Compatibility

Public product name: **Route**. Stable technical identity: `soul` / `/soul`. The legacy public label **Research Orchestrator** and the phrase **Process Assurance** remain only as migration vocabulary in older documentation and receipts; Assure is the Strong Inference public name for that control function.
