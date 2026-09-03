# Gauntlet Fast Build — Current Handoff Ledger

**Handoff ID:** `GAUNTLET-FAST-HANDOFF-001`  
**Ledger version:** `3.0`  
**Repository:** `Kitahl/The-Gauntlet`  
**Producer branch:** `work/native-hermes-fastpath`  
**Completed milestone:** `FAST-P8`  
**Validated implementation head:** `6990322a815e46b200d7572544a106607c74343a`  
**Validated implementation tree:** `3aba1c6263eaca953d92c6f71f2f5b4f9c7996d6`  
**Implementation commit:** `554ee851996cd363c2e52a6294c3bf478f10a41f`  
**Successful run / job:** `33273140981` / `99155128215`  
**Fast-build state:** `ALPHA_CHECKPOINT_COMPLETE`  
**Next action:** exact-checkpoint consumer admission or rejection; no automatic merge  
**Pinned upstream:** `NousResearch/hermes-agent@5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

This ledger supersedes version `2.0`. FAST-P8 completes the bounded pinned-runtime
fast-build sequence. It does not complete the separate Gauntlet Native Runtime program,
establish overlay compatibility, or authorize a merge to `main`.

## Milestone namespace

```text
FAST-P1  provenance and source pin
FAST-P2  exact source materialization / gitlink representation
FAST-P3  JSONL IPC and isolated worker bootstrap
FAST-P4  launcher, runtime profile, one upstream turn
FAST-P5  read-only Gauntlet status bridge
FAST-P6  observation bridge and Soul finalizer
FAST-P7  advisory FOIL route
FAST-P8  user-facing alpha CLI and boot qualification
```

`FAST-P8` is not `NATIVE-800`, native-final, or a release-candidate promotion.

## Current checkpoint ledger

| Milestone | State | Current evidence |
|---|---|---|
| `FAST-P1` | `COMPLETE_HISTORICAL` | original implementation `60bb6f22d7c13a25fee204fbc17798c6c55cb19f` |
| `FAST-P2` | `COMPLETE` | exact upstream pin retained as a mode-`160000` gitlink |
| `FAST-P3` | `COMPLETE_HISTORICAL` | successful run `33225470731` |
| `FAST-P4` | `COMPLETE_HISTORICAL` | successful run `33226703542` |
| `FAST-P5` | `COMPLETE` | head `dda78eabc216749cb1a3010d8e533428b78721d0`; tree `0ad6d8641561de46bd729a5115500d4fd7bb0483`; run `33230839031` |
| `FAST-P6` | `COMPLETE` | head `249753738f193d1f82e7e12afe907c4841827f80`; tree `10eeeeef9f85ca91e766e5be388a176943decf5d`; run `33266521662` |
| `FAST-P7` | `COMPLETE` | head `9747572e8ca13622b72d8cd3d995fece90e19173`; tree `0b194a94abf0e9791afeb604c84141325381788f`; run `33271699059` |
| `FAST-P8` | `COMPLETE` | head `6990322a815e46b200d7572544a106607c74343a`; tree `3aba1c6263eaca953d92c6f71f2f5b4f9c7996d6`; run `33273140981` |

The Phase-1–4 commit identifiers remain historical because the producer history was later
repaired to replace the copied upstream tree with the pinned gitlink. Current checkpoint
authority comes from exact live Git objects and checkpoint-native runs.

## Frozen authority path

```text
runtime model/tool execution
→ operational ToolObservation
→ claim-native Gauntlet module
→ canonical Receipt
→ Soul release gate
```

The model, provider, tool, plugin, runtime session database, FAST-P7 route, memory, and skill
surfaces cannot create canonical evidence authority. FAST-P8 adds only bounded task setup:
it may ask existing Soul code to create a task and one declared load-bearing obligation.

## FAST-P8 result

FAST-P8 exposes one installed product command:

```bash
gauntlet "research this..."
gauntlet chat
```

`python -m gauntlet_host` is the source-checkout fallback. The console command invokes the
existing isolated launcher, FAST-P7 route wrapper, status plugin, observation bridge, and
parent-owned Soul finalizer.

For a new one-shot task, the CLI:

1. calls the existing Soul task-start command;
2. immediately adds one declared load-bearing obligation;
3. verifies that the task is integrity-valid, active, unreleased, and non-empty;
4. passes the exact task ID through the existing launcher and `GAUNTLET_TASK_ID`;
5. runs the isolated worker;
6. reports the worker answer only together with the Soul-gated finalization state.

An existing task is accepted only through explicit `--task-id`; task identity is never inferred
from conversation text. The default new obligation kind is `DISCOVERY`. `--kind` and `--claim`
allow the caller to declare a different existing obligation kind and separate the canonical
claim from the runtime prompt.

The successful checkpoint reported:

```json
{
  "boot_checks": {
    "1_gauntlet_starts": true,
    "2_worker_starts": true,
    "3_model_responds": true,
    "4_runtime_tool_executes": true,
    "5_gauntlet_task_status_works": true,
    "6_runtime_observation_recorded": true,
    "7_soul_gate_runs": true,
    "8_unresolved_not_cleared": true
  },
  "boot_checks_passed": 8,
  "canonical_receipts_created": 0,
  "chat_entry_point_started": true,
  "foil_route_preserved": true,
  "load_bearing_obligation_created": true,
  "model_round_trips": 3,
  "ordinary_hermes_home_created": false,
  "release_gate_verdict": "UNKNOWN",
  "runtime_observations": 1,
  "task_created_by_cli": true,
  "unresolved_not_accepted": true
}
```

The fixture deliberately had no claim-native Space receipt. The worker completed, but Soul
returned `UNKNOWN`, the task remained active and unreleased, and the CLI exited non-zero rather
than treating operational success as evidential clearance.

## Changed paths

```text
.github/phase8_verify.py
.github/workflows/fastpath-checkpoint.yml
docs/engineering/PHASE8_USER_CLI_BOOT.md
gauntlet_host/__main__.py
gauntlet_host/cli.py
pyproject.toml
```

The checkpoint receipt is published at:

```text
docs/engineering/HERMES_FAST_P8_CHECKPOINT.json
```

## Repair history

Run `33273066412` reached the installed `gauntlet` command but failed on a harness-only assertion:
`argparse` wrapped the help description across a line, while the check compared raw whitespace.
The repair normalized rendered help whitespace without changing the CLI, runtime, task binding,
authority boundary, or boot criteria. Exact-head run `33273140981` then passed all checks.

## Limits

FAST-P8 does not establish:

```text
external-provider operation
automatic claim-native module execution
autonomous replanning
task release
dynamic FOIL tool-schema narrowing
profile-based complements
routing efficacy
cost, latency, or token improvement
direct-mode or integrated-overlay parity
Windows qualification
native-runtime completion
```

The alpha still requires the pinned runtime and its isolated dependencies. It remains an
`INTERIM_ALPHA` checkpoint until the integration consumer independently freezes the exact
commit/tree, classifies paths, runs checkpoint-native and integrated authority tests, and
records `ADMITTED` or `REJECTED`.

## Continue instruction

The fast-build implementation sequence stops here. Continue through the separate integration
protocol only:

1. preserve `work/native-hermes-fastpath` as the producer lane;
2. freeze the exact FAST-P8 implementation commit and tree;
3. verify the checkpoint receipt content hash;
4. classify every changed path;
5. rerun H1 checkpoint-native tests;
6. import only the exact admitted delta into `integration/vnext-native-stack`;
7. run H2 integrated authority, direct-mode, rollback, and compatibility tests;
8. admit or reject the checkpoint explicitly;
9. keep native/fastpath mode `OFF` by default;
10. do not merge `main` or call the pinned-runtime alpha native-final.
