# Gauntlet automatic assurance — integration specification

## Purpose

This specification restores Gauntlet's automatic watchdog role while retaining the typed monitors, frozen snapshots, authority boundaries, and efficiency instrumentation introduced by Gauntlet vNext.

The correction is not a return to an unstructured "run everything" prompt. It is an automatic controller over the ten canonical typed operations.

## Production default

```text
mode = AUTOMATIC_FULL
```

At a release attempt the controller:

1. loads one integrity-valid task, event, and receipt snapshot;
2. computes operation applicability from the complete represented snapshot;
3. executes every applicable canonical operation;
4. treats configured cost/operation ceilings as advisory telemetry rather than permission to remove release checks;
5. continues after an `ISSUE` so one release attempt can expose all represented blockers;
6. checks the internal RuntimeStore receipt-to-event chain;
7. writes one aggregate `ASSURANCE_ONLY` receipt.

This restores automatic breadth at the release boundary. It does not remove the low-level selective planner, which remains useful for research comparisons and incremental monitoring.

## Experimental modes

```text
SELECTIVE_EXPERIMENTAL
FAST_BLOCK_EXPERIMENTAL
```

Only these modes may:

- omit a triggered operation because of a structural budget;
- stop after the first issue;
- claim avoided structural cost units.

Their receipts explicitly state:

```text
coverage_reduction_experimental = true
```

They are not the default release authority.

## Applicability versus omission

An operation is *not applicable* only when its defining process condition is absent from the represented state. Examples:

- no handoff → `boundary` is not applicable;
- no novelty claim → `costume` is not applicable;
- no inherited claim → `derive` is not applicable.

This is different from selecting an applicable operation and then dropping it for cost. Production automatic mode permits the first and forbids the second.

## Runtime event-chain guard

The controller checks that each persisted task receipt has the expected typed records used by the assurance monitors:

- `receipt.written` with the receipt ID and content hash;
- `obligation.state` with obligation and verdict;
- enough `evidence.attached` records for persisted evidence envelopes;
- unique non-empty event IDs/types/content hashes.

A gap produces:

```text
runtime_event_coverage_status = UNKNOWN_RUNTIME_EVENT_CHAIN
```

and prevents aggregate `CLEARED` unless a stronger `ISSUE` already applies.

This establishes only internal RuntimeStore-chain completeness. It does not prove that the external world represented every possible hazard. The receipt therefore states:

```text
coverage_scope = RUNTIME_STORE_REPRESENTED_HAZARDS
```

## Authority

Automaticity changes scheduling, not authority.

```text
authority = ASSURANCE_ONLY
target_domain_clearance_authorized = false
```

Gauntlet cannot clear proof, discovery, synthesis, engineering, evaluation, review, adaptation, preflight, or adversarial obligations.

## Tool integration

Typed deterministic checks remain first. When an applicable operation requires an unavailable semantic capability, the result is `UNAVAILABLE`; Soul may automatically route the corresponding claim-native work. Gauntlet never fabricates a tool result and never adopts a candidate.

## Cost interpretation

`cost_units` are retained for ordering and diagnostics but are labelled:

```text
UNCALIBRATED_ORDERING_PROXY
```

Production automatic mode does not use them to remove applicable release checks. Selective experimental modes may use them only under a frozen benchmark policy.

## Acceptance properties

- all ten canonical operations remain registered;
- production full mode selects all applicable operations even when advisory budget values are small;
- production full mode executes all selected operations after an issue;
- selective reduction requires an explicitly experimental mode;
- broken receipt/event linkage prevents a false green;
- the aggregate receipt remains `ASSURANCE_ONLY`;
- one snapshot and one aggregate receipt are used per run;
- no `foil_*`, Foundry, or Mastermind runtime is imported.

## Efficacy boundary

Mechanical acceptance does not establish that the controller improves whole-task outcomes. A future evaluation should compare:

```text
FULL_AUTOMATIC
SELECTIVE_EXPERIMENTAL
NO_GAUNTLET
ORACLE_ANALYSIS
```

with held-out hazard families, per-class escapes, false blocks, whole fix-to-green cost, real tokens/tool calls/latency/money, and downstream task success at equal complete cost.
