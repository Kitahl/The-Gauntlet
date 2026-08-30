# TOKEN-200 / TOKEN-300 / TOKEN-500 implementation report

Date: 2026-08-30
Branch: `work/hermes-token-lean`
Implementation commit: `ca4a14988a526b1a49cd2a93b46ce533329cb79d`
Implementation tree: `68184b47035bd7181bbbc96348d0732c7d8ef82c`
Pinned Hermes: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`)

## Scope and authority

This stage implements the token-efficiency-only requirements for:

- TOKEN-200: deterministic capability compilation and exact active tool surface;
- TOKEN-300: request-only sparse context selection through the pinned Hermes context-engine seam; and
- TOKEN-500: bounded just-in-time skill, memory, and profile snippets with provenance and task/profile isolation.

The implementation does not change canonical Gauntlet adjudication, release authority, receipts, obligation state, or the pinned Hermes source. Selected context is explicitly non-authoritative.

## Implementation

### TOKEN-200 — capability compiler

- Defines frozen `CapabilitySpec` records for compact canonical status, exact obligation disclosure, and canonical release refresh.
- Probes fresh live tool availability before `AIAgent` construction.
- Validates each live tool schema against its content-addressed capability specification.
- Compiles and installs one exact custom toolset, `gauntlet-active-v1`, with a content-addressed active-manifest hash.
- Fails closed on missing capabilities, schema drift, or requested extra toolsets.
- Ignores unauthorized extra tools in the live registry instead of widening the active surface.

### TOKEN-300 — sparse request context

- Registers `gauntlet-sparse` through the existing pinned Hermes context-engine plugin seam.
- Preserves the stable system/developer prefix, current user turn, active tool-call/result closure, and three recent closed history units.
- Adds bounded lexical top-k retrieval for older relevant history units.
- Activates sparse selection only after the configured history threshold or when validated JIT context is present.
- Delegates compaction to pinned Hermes `ContextCompressor` and forwards runtime telemetry/cancellation attributes.
- Selects request-visible messages without modifying the durable session transcript.

### TOKEN-500 — bounded JIT context

- Accepts only selected `skill`, `memory`, or `profile` snippets.
- Requires source provenance, content hash integrity, `CONTEXT_ONLY` authority, session binding, and runtime-profile binding.
- Enforces per-snippet, count, and aggregate character limits.
- Rejects reserved-marker collisions and binding mismatches.
- Injects only selected snippets into the current provider request; unselected material and ambient skill/memory/profile discovery remain absent.

## Verification

All checks ran locally with the repository's pinned environment and localhost-only provider fixtures.

| Gate | Result |
| --- | --- |
| Stage-focused tests | 9 passed |
| Full unit suite | 487 passed in 115.368 seconds |
| Ruff formatting and lint on changed files | PASS |
| Python compilation and `git diff --check` | PASS |
| TOKEN-010 ten-turn continuity regression | PASS: 10 task-A turns, no cross-task leak, fresh-parent resume exercised |
| TOKEN-200/300/500 committed-source live gate | PASS |
| TOKEN-100/600 committed-source compatibility gate | PASS |

The TOKEN-200/300/500 live gate observed:

- one provider request;
- 12 input messages / 18,598 input characters;
- 11 selected messages / 16,645 selected characters;
- exactly three model-visible tools;
- fresh availability and active-manifest binding before agent construction;
- relevant older-unit retrieval, irrelevant older-unit omission, and preservation of all three recent turns;
- stable prefix, current user turn, and active tool closure preservation;
- one selected JIT snippet, no unselected snippet, and `CONTEXT_ONLY` authority;
- 12 persisted messages after the turn, proving request selection did not truncate the stored transcript; and
- zero canonical receipts and no canonical-state mutation.

The committed-source TOKEN-100/600 compatibility gate retained:

- the exact three-tool model-visible surface;
- no first-turn status-tool call;
- batched independent refresh calls;
- three provider requests across two turns;
- zero FOIL model calls;
- stable system-prompt bytes; and
- zero canonical receipts and no canonical-state mutation.

## Evidence

- `outputs/TOKEN_200_300_500_QUALIFICATION_2026-08-30.json`
- `outputs/TOKEN_100_600_TOKEN230500_COMPATIBILITY_2026-08-30.json`
- `.github/token230500_verify.py`
- `tests/test_tool_sparse_context.py`

Both JSON manifests bind their results to implementation commit `ca4a14988a526b1a49cd2a93b46ce533329cb79d`, tree `68184b47035bd7181bbbc96348d0732c7d8ef82c`, and pinned Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`.

## Claim boundary

This stage establishes functional correctness and exact-source evidence for TOKEN-200, TOKEN-300, and TOKEN-500. It does not claim an end-to-end token-reduction percentage, quality non-inferiority, latency improvement, or release readiness. Those claims remain gated on TOKEN-400 instrumentation and TOKEN-700 paired evaluation.
