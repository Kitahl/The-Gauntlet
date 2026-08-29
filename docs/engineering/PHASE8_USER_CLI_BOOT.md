# FAST-P8 — User-facing Gauntlet alpha CLI and boot qualification

## Scope

FAST-P8 adds the first single product entry point for the pinned-runtime alpha:

```bash
gauntlet "research this..."
gauntlet chat
```

The command is an editable-install console entry point backed by
`gauntlet_host.cli:main`. It invokes the existing isolated launcher, FAST-P7
advisory FOIL route, observation bridge, and parent-owned Soul finalizer. It
does not add another provider, tool registry, plugin manager, task store, or
release path.

This checkpoint remains an interim pinned-runtime alpha. It is not
`NATIVE-800`, native-final, an integrated overlay admission, or a behavioral
efficacy result.

## Task binding

A one-shot command has two task modes:

1. `--task-id <id>` binds to an existing integrity-valid, active, unreleased
   canonical task.
2. Without `--task-id`, the CLI calls the existing Soul CLI to create a task
   and immediately adds one load-bearing obligation.

The default new-task obligation is `DISCOVERY`, with the prompt as its claim.
The caller can select another existing obligation kind with `--kind` and can
separate the canonical claim from the runtime prompt with `--claim`.

The alpha refuses to run an existing task with no load-bearing obligation.
It never invents a task ID from conversation text. The explicit task ID is
passed into the launcher and then through `GAUNTLET_TASK_ID`.

FAST-P8 is deliberately repository-bound. `--root` must identify the checkout
that contains the active command, Gauntlet authority modules, and pinned
runtime gitlink. This prevents the worker, status adapter, and finalizer from
silently operating against different repositories.

## Command surface

One turn:

```bash
gauntlet \
  --kind DISCOVERY \
  --model <model> \
  --provider <provider> \
  "research this..."
```

Machine-readable finalization:

```bash
gauntlet --json "research this..."
```

Explicit existing task:

```bash
gauntlet --task-id task_example "continue the bounded task"
```

Interactive alpha:

```bash
gauntlet chat
```

The chat surface reuses one explicit task. `/task` displays its identity and
`/quit` exits. A new chat task is created only after the first non-command
prompt.

`python -m gauntlet_host` is an equivalent source-checkout fallback.

## Authority boundary

The CLI may:

- create a canonical task through the existing Soul command;
- add one declared load-bearing obligation;
- start the isolated pinned runtime;
- display operational model output and the Soul-gated finalization state.

The CLI, runtime, model, provider, tool, plugin, session database, FOIL route,
and observation store may not:

- create a canonical receipt;
- change a verdict;
- clear an obligation;
- mark a task released;
- convert worker `OK` into `CLEARED`;
- bypass a claim-native verifier or Soul.

The authority path remains:

```text
runtime tool call
→ ToolObservation
→ claim-native Gauntlet module
→ canonical Receipt
→ Soul release gate
```

An unresolved command intentionally exits with the existing finalizer's
non-zero status and reports the unresolved gate. That is not a runtime crash.

## Eight-item boot qualification

`.github/phase8_verify.py` performs the bounded alpha boot check against a
deterministic local OpenAI-compatible endpoint:

1. `gauntlet` starts.
2. the isolated worker starts;
3. the model responds;
4. a runtime tool executes;
5. `gauntlet_task_status` returns canonical read-only status;
6. an `OBSERVATION_ONLY` tool observation is recorded;
7. the parent-owned Soul gate runs;
8. an unresolved task is not reported `CLEARED`.

The same run also checks:

- `gauntlet chat` starts and exits through `/quit`;
- a new task and one load-bearing obligation are created by the CLI;
- the FAST-P7 route is injected before the first model request;
- canonical claim text is absent from the pre-request route block;
- inherited runtime bypass flags are removed by the launcher;
- no ordinary `~/.hermes` directory is created;
- zero canonical receipts are created;
- the task remains active and unreleased.

## Explicit limitations

FAST-P8 does not establish:

- operation against a paid external provider;
- automatic claim-native module execution;
- autonomous replanning;
- task release;
- dynamic FOIL tool-schema narrowing;
- profile-based complements;
- routing or cost efficacy;
- direct-mode or integrated-overlay parity;
- cross-platform qualification;
- native-runtime completion.

The next action after a successful FAST-P8 checkpoint is not an automatic
merge. The exact producer commit/tree must be considered through the separate
integration checkpoint protocol.
