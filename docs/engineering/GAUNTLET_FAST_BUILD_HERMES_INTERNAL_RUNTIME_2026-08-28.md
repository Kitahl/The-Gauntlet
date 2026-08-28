# GAUNTLET FAST BUILD — HERMES-QUALITY INTERNAL RUNTIME

**Document ID:** `GAUNTLET-FAST-HOST-001-EXEC`  
**Date:** 2026-08-28  
**Repository:** `Kitahl/The-Gauntlet`  
**Branch:** `work/native-hermes-fastpath`  
**Baseline:** `4f088d688fa9e25b4608f44000a5d9812efa45f9`  
**Upstream:** `NousResearch/hermes-agent` `v2026.8.27` / `v0.20.6`  
**Commit:** `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`  
**Mode:** fast implementation; reuse upstream; do not redesign.

## 1. Product decision

1. Vendor the exact pinned Hermes source under `vendor/hermes-agent/`.
2. Run it as a Gauntlet-owned internal subprocess, not as a separately installed product.
3. Keep the vendored tree unchanged except for recorded, reviewed deviations.
4. Use upstream provider, tool, MCP, context, session, skill, memory, retry, and delegation mechanisms.
5. Add only a thin `gauntlet_host/` boundary.
6. Keep existing Gauntlet modules as the sole evidential and release authority.
7. Ship one user-facing command: `gauntlet`.

Do not port Hermes subsystem-by-subsystem. Do not build replacement provider, MCP, tool,
context, session, skill, memory, retry, scheduler, or subagent frameworks during this pass.

## 2. Isolation invariant

Both repositories contain top-level packages such as `tools`. Never import both trees into
one interpreter. Launch the internal worker with:

```text
cwd        = vendor/hermes-agent
PYTHONPATH = vendor/hermes-agent
HERMES_HOME = ~/.gauntlet/runtime
GAUNTLET_TASK_ID = <canonical task id>
```

The parent remains the Gauntlet process. Parent/worker communication is typed JSONL over
stdin/stdout. `gauntlet_host/worker_main.py` may import upstream `run_agent.AIAgent`; the
parent launcher must not.

## 3. Authority invariant

```text
runtime tool execution
→ ToolObservation
→ existing Gauntlet module/verifier
→ canonical Receipt
→ existing Soul release_gate()
```

The worker, model, tool, plugin, skill, memory, session store, scheduler, or subagent may
not directly:

- create a canonical `Receipt`;
- set or change `Verdict`;
- clear an `Obligation`;
- modify sealed authority rules;
- declare tool success to be factual warrant;
- release a task;
- convert memory or a skill into evidence.

Do not change `tools/egrt_types.py` semantics, `tools/soul_runtime.py` release semantics,
FOIL authority ceilings, or the current receipt format during the fast build.

## 4. Required repository additions

```text
vendor/hermes-agent/                 exact upstream snapshot
gauntlet_host/
  __init__.py
  constants.py
  ipc.py
  worker_main.py
  launcher.py
  runtime_profile.py
  gauntlet_plugin.py
  gauntlet_tool.py
  observation_bridge.py
  module_cli.py
  finalizer.py
  session_map.py
third_party/HERMES_LICENSE.txt
third_party/HERMES_SOURCE_LEDGER.md
vendor/HERMES_SNAPSHOT.json
scripts/vendor_hermes.py
```

Existing `tools/` files remain authoritative and import-compatible.

## 5. Runtime profile

Store operational state only under `~/.gauntlet/runtime/`; never reuse `~/.hermes`.
Disable automatic background review for the alpha:

```yaml
auxiliary:
  background_review:
    enabled: false
memory:
  write_approval: true
skills:
  write_approval: true
```

Memory and skills are operational context only. They never clear obligations.

## 6. Four integration seams

### 6.1 Launcher

- start or resume the canonical Gauntlet task;
- build a typed `RuntimeRequest`;
- launch the worker subprocess;
- map task and runtime session IDs;
- receive a structured worker result;
- call the finalizer.

### 6.2 Worker

- put `vendor/hermes-agent` first on `sys.path`;
- set `HERMES_HOME` and `GAUNTLET_TASK_ID`;
- load the Gauntlet-owned runtime profile;
- register the Gauntlet plugin through the upstream plugin mechanism;
- instantiate upstream `AIAgent` without forking it;
- return `worker.final` JSONL.

### 6.3 Plugin and module adapter

Minimum tools:

```text
gauntlet_task_status
gauntlet_release_status
gauntlet_route
gauntlet_verify
```

Invoke current Gauntlet modules in separate subprocesses by exact file/module command.
Never import both top-level `tools` packages into the worker interpreter. Observe upstream
`pre_tool_call`, `post_tool_call`, `on_session_start`, and `on_session_end` hooks. Record
hashes, status, task, session, and timestamps only; never a verdict.

### 6.4 Finalizer

After every completed worker task, call existing `Soul release_gate(task_id)`. Return the
worker answer when cleared. Otherwise return the answer plus canonical unresolved status
and a nonzero exit code. Do not build an autonomous replan loop until the alpha works.

## 7. FOIL alpha

FOIL remains a semantic router, not a second agent and not an authority source. Map runtime
tools to semantic capabilities, obtain an advisory route, and inject the public routing
trace. Dynamic schema/tool restriction is optional after the core loop works.

Minimum output:

```text
primary_effort_mode
targeted_complement
required_verifiers
should_stop
```

## 8. Phased implementation

| Phase | Deliverable | Stop gate |
|---:|---|---|
| 1 | source pin, MIT notice, manifest, deterministic vendoring command, handoff ledger | provenance committed |
| 2 | materialized `vendor/hermes-agent/` and independent digest verification | exact tree committed |
| 3 | constants, typed JSONL IPC, isolated worker bootstrap | worker imports upstream safely |
| 4 | launcher, runtime profile, runtime home, session mapping | one upstream turn returns |
| 5 | status/release plugin tools and subprocess module adapter | canonical status callable |
| 6 | tool observation bridge and Soul finalizer | no false `CLEARED` path |
| 7 | FOIL advisory route and `gauntlet` CLI | one product entry point |
| 8 | eight-item manual boot verification and Codex transfer | alpha handoff complete |

Commit each phase narrowly. Never merge `main` from the fast-build branch.

## 9. Explicitly deferred

No new REST/ACP API, desktop UI, messaging gateway, provider framework, MCP stack, database
abstraction, context compressor, skill engine, browser engine, subagent framework, broad
scheduler parity, procedure self-evolution, generalized statistical certification, or full
Soul replanner.

Do not delete existing Gauntlet or upstream tests. Do not spend the fast window writing a
new broad suite. Run only bounded compile/dry-run checks during construction, then perform
the manual alpha boot verification.

## 10. Manual alpha verification

```text
1. gauntlet starts
2. internal worker starts
3. model responds
4. one runtime tool executes
5. gauntlet_task_status executes
6. a runtime observation is recorded
7. Soul release_gate executes
8. unresolved state is not reported CLEARED
```

## 11. Definition of alpha done

The alpha is complete only when the Gauntlet command starts one internal worker using the
vendored source; upstream provider, tool, context, and session mechanisms function; state
is under `~/.gauntlet/runtime`; task identity and canonical status are visible to the
worker; tool results remain observations; current modules/verifiers remain available;
Soul remains the final release gate; FOIL exposes at least an advisory route; background
skill/memory promotion is disabled; attribution is present; and no separately installed
Hermes runtime is required.

## 12. Codex continuation rule

Read `docs/engineering/GAUNTLET_FAST_BUILD_HANDOFF.md` first. Continue only the phase marked
`NEXT`, record exact commands and commit SHA, update the ledger, and stop before the next
phase. Do not redesign the architecture or merge `main`.
