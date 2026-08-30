# TOKEN-100/600 implementation and qualification report

Date: 2026-08-30

## Outcome

TOKEN-100 low-risk direct savings and TOKEN-600 model-round-trip reductions are **PASS** on the committed Gauntlet implementation.

The parent now obtains one fresh, canonical compact status and one validated FOIL route before the first model call. Hermes receives a bounded volatile capsule, a frozen three-tool refresh manifest, and an explicit isolated lean profile. No extra model call is used for routing, and independent refresh tool calls can execute in one model round trip.

## Exact source

- Gauntlet commit: `7731031845ba5ca583f352a04ca8b8f6c37e0db1`
- Gauntlet tree: `a3cecfb89d0b1129a6046719d735929e7f6a6ee7`
- Pinned Hermes commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- Pinned Hermes tag: `v2026.8.27`
- Branch: `work/hermes-token-lean`

No GitHub push or merge was performed.

## Implementation

- Added a combined parent-side `lean-prefetch` adapter that reads compact canonical status and the full advisory FOIL route in one deterministic subprocess before worker/model construction.
- Added a frozen `gauntlet-status.v1` model-visible manifest with exactly:
  - `gauntlet_task_status_compact`;
  - `gauntlet_obligation_get`;
  - `gauntlet_release_status`.
- Added canonical compact status with bounded identifiers, codebook-indexed repeated verdict/reason values, integrity validation, and no exact obligation claim text.
- Added bounded exact-one-obligation progressive disclosure. The exact claim is available only by explicit obligation identifier.
- Reduced the injected FOIL route to exactly `route_hash`, `route_revision`, `primary_mode`, `selected_capability_ids`, `required_verifier_ids`, `missing_capability_ids`, and `should_stop`.
- Stored the validated full FOIL route as a private, content-addressed operational artifact.
- Added the explicit `gauntlet-lean.v1` profile. Ambient memory, user profile, skills discovery, execution guidance, context files, background review, and other unused prompt/runtime features are disabled for this profile rather than globally.
- Preserved stable system-prompt bytes. Dynamic route/status context is appended only as a volatile current-turn suffix.
- Used Hermes' clean persisted-user-message override and removed only the exact reserved historical lean sidecars on resume, preventing volatile capsule replay while preserving the user transcript and unrelated sidecars.
- Enabled parallel tool guidance so independent compact-status and release refreshes can be emitted together.
- Kept deterministic host routing in the capsule when the current obligation already determines its required module.
- Added a non-destructive, localhost-only two-turn qualification harness and focused regression tests.

## Live qualification

The checked-in localhost-only `phase5-mock` provider fixture observed:

- 2 isolated worker turns;
- 3 provider requests total;
- 1 provider request on the first turn;
- 0 first-turn status-tool calls because the parent-prefetched status was sufficient;
- 2 provider requests on the refresh turn: one batched tool-call request and one final-answer request;
- exactly 3 model-visible Gauntlet tools;
- 0 extra model calls for FOIL;
- stable system-prompt bytes across turns;
- no persisted historical lean capsule in the resumed provider request;
- exact claim text absent from compact context and compact tool results;
- exact-one-obligation detail available through explicit progressive disclosure;
- a content-addressed full FOIL route;
- no canonical receipt created and no canonical state mutation.

Measured capsule sizes in the live task:

- FOIL route capsule: 86 estimated tokens, below the proposed 512-token gate;
- compact canonical status: 186 estimated tokens, below the proposed 1,024-token gate.

The focused 32-obligation fixture also passes the 1,024-token compact-status gate.

Canonical result: `outputs/TOKEN_100_600_QUALIFICATION_2026-08-30.json`.

## Continuity regression

The existing TOKEN-010 localhost-only qualification was rerun against the TOKEN-100/600 commit:

- 10 turns for task A retained every prior task-A canary;
- task B was interleaved at turn 6 with no cross-task leak;
- a newly started parent launcher resumed task A at turn 6;
- one stable task-A binding and one stable runtime session were preserved;
- every turn used a fresh isolated worker process;
- repository and disposable fixture canonical state remained unchanged.

Result: **PASS**.

## Deterministic verification

- `python -m unittest discover -s tests -v`: **482 passed** in 121.723 seconds.
- TOKEN-100/600 focused tests: **4 passed**.
- Touched-file Ruff check: **PASS**.
- Touched-file Ruff format check: **PASS**.
- Compile check for touched host, tests, and verifier: **PASS**.
- Git whitespace check: **PASS**.
- Committed-source two-turn live qualification: **PASS**.
- Committed-source ten-turn TOKEN-010 regression: **PASS**.

## Process assurance

The first resumed live probe exposed a stale Hermes `api_content` sidecar containing the prior volatile capsule. The candidate was not accepted. The implementation was amended to identify and remove only the reserved lean sidecar shape, with a negative-control test proving unrelated sidecars remain intact. The corrected two-turn live gate and the full ten-turn continuity gate then passed.

## Claim boundary

This checkpoint establishes the TOKEN-100 and TOKEN-600 mechanisms and their local deterministic qualification on the pinned Hermes fixture. It does not claim an overall percentage reduction, cost reduction, production-provider equivalence, or quality noninferiority. Those claims remain prohibited until the matched TOKEN-700 qualification is prospectively frozen and passes.
