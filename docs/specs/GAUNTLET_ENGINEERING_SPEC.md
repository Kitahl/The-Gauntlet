# Aegis / Gauntlet — Process Assurance Layer specification

## Obligation

Monitor the research process/frame for known hazards that ordinary candidate verification may miss. Aegis does not replace claim-native verification.

## Current workflow

- `frame`: lexical/similarity + tool-loop detection with optional semantic judge.
- `costume`: novelty/survivor lexical candidate + optional semantic judge.
- `refresh`: governing-file/Git HEAD hash drift monitor.
- remaining operations primarily specification-level/manual.

## vNext operation registry

| Operation | Support | Typed basis | Boundary |
|---|---|---|---|
| frame | AUTOMATIC | repeated failure/action events | only represented failure signatures |
| audit | AUTOMATIC | release attempt + obligation state | does not judge semantic truth of receipts |
| costume | ASSISTED | typed novelty claim + Space receipt; language detection assisted | no global novelty proof |
| derive | AUTOMATIC | inherited claim + Mind derivation receipt | requires typed inherited flag |
| self | AUTOMATIC | producer/verifier/provenance metadata | common provenance makes independence unresolved |
| redirect | AUTOMATIC | repeated action + unchanged blocker/progress hashes | requires stable blocker representation |
| refresh | AUTOMATIC | authority snapshots/change events | only registered authorities |
| boundary | AUTOMATIC | handoff + contract binding | only typed handoffs |
| explain | ASSISTED | explanation/artifact semantic comparison | hashes alone cannot prove semantic consistency |
| oob | AUTOMATIC | release + named coverage probe | never proves all unknown failure classes exhausted |

## vNext workflow

1. Receive structured events and receipts.
2. Determine operation monitorability from registry.
3. Run the smallest triggered monitor.
4. Return scoped `CLEARED/ISSUE/UNKNOWN/UNAVAILABLE`.
5. Write Gauntlet receipt with support mode and limitation.
6. Feed verdict back to Soul as an assurance obligation.
7. Preserve existing `gauntlet_boundary.py` and `gauntlet_monitor.py` as compatibility detectors while migrating their observations into typed events.

## Runtime

`tools/gauntlet_runtime.py` plus existing boundary/monitor/hook tools.

## Required hazard tests

Inject: repeated failure, release with missing receipt, inherited quantity without derivation, shared producer/verifier, unchanged blocker loop, authority drift, handoff without contract, missing OOB probe, unavailable semantic judge.
