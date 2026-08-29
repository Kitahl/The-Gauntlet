# Gauntlet Fast Build — Current Handoff Ledger

**Handoff ID:** `GAUNTLET-FAST-HANDOFF-001`  
**Ledger version:** `2.0`  
**Repository:** `Kitahl/The-Gauntlet`  
**Producer branch:** `work/native-hermes-fastpath`  
**Completed milestone:** `FAST-P7`  
**Validated implementation head:** `9747572e8ca13622b72d8cd3d995fece90e19173`  
**Validated implementation tree:** `0b194a94abf0e9791afeb604c84141325381788f`  
**Successful run:** `33271699059`  
**Next milestone:** `FAST-P8` — user-facing alpha CLI and boot qualification  
**Pinned upstream:** `NousResearch/hermes-agent@5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

This version replaces the stale Phase-4-era working copy. Its previous detailed text remains
available in Git history at blob `40ed3881d19e5d5e7314425c24d6e5965c38a1e4`.

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

`FAST-P7` is not `NATIVE-600`, `NATIVE-700`, or native-final completion.

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
| `FAST-P8` | `NEXT` | not started |

The older Phase-1–4 commit identifiers are historical because the producer history was later
repaired to replace the copied upstream tree with the pinned gitlink. Current authority comes
from exact live Git objects and successful checkpoint-native runs.

## Frozen authority path

```text
runtime model/tool execution
→ operational ToolObservation
→ claim-native Gauntlet module
→ canonical Receipt
→ Soul release gate
```

The runtime, provider, plugin, tool, session database, memory, skill system, and FAST-P7 FOIL
route cannot create canonical evidence authority.

## FAST-P7 result

FAST-P7 adds a live runtime tool-capability snapshot and calls the existing FOIL
`RuntimePolicyV2` through a read-only Gauntlet-side adapter before the first model request.
The output is a bounded, task-bound, content-hashed route instruction.

Every accepted route records:

```text
schema: gauntlet.foil-route.v1
mode: SHADOW
authority_ceiling: ADAPTATION_ONLY
execution_authorized: false
toolset_narrowing_applied: false
profile_used: false
private_profile_data_transmitted: false
```

The route cannot create a receipt, change a verdict, clear an obligation, execute a tool,
release a task, or bypass claim-native verification or Soul.

Changed paths are recorded in:

```text
docs/engineering/HERMES_FAST_P7_CHECKPOINT.json
docs/engineering/PHASE7_FOIL_ADVISORY_ROUTE.md
```

The successful checkpoint reported:

```json
{
  "canonical_receipts_created": 0,
  "canonical_task_unchanged": true,
  "capability_bundle_complete": false,
  "missing_requirements": 2,
  "model_round_trips": 3,
  "profile_data_transmitted": false,
  "release_gate_verdict": "UNKNOWN",
  "route_authority_ceiling": "ADAPTATION_ONLY",
  "route_injected_before_first_model_request": true,
  "route_mode": "SHADOW",
  "toolset_narrowing_applied": false,
  "unresolved_not_accepted": true
}
```

The incomplete capability bundle is expected for the bounded fixture, which exposes only the
read-only Gauntlet status tools. Missing search requirements remain explicit instead of being
silently treated as satisfied.

Run `33271617165` first failed before runtime execution because the verifier was launched from
`.github/` without the repository root on `sys.path`. The workflow-only repair supplied
`PYTHONPATH=.`; exact-head run `33271699059` then passed.

## Limits

FAST-P7 does not establish routing efficacy, cost reduction, verified-completion improvement,
profile-based complements, automatic tool narrowing, autonomous replanning, task release,
overlay admission, or native-runtime completion.

## Continue instruction

Proceed with `FAST-P8` only:

1. expose one user-facing `gauntlet` command;
2. preserve the isolated worker and FAST-P7 route;
3. keep task identity explicit through `GAUNTLET_TASK_ID`;
4. keep runtime output operational and non-authoritative;
5. preserve claim-native receipt production and Soul release authority;
6. run the bounded eight-item boot qualification;
7. publish an exact checkpoint receipt;
8. do not merge `main`;
9. do not call the pinned-runtime alpha native-final.
