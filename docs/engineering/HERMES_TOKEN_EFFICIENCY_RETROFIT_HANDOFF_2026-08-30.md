# Hermes Token-Efficiency Retrofit Handoff

**Branch:** `work/hermes-token-lean`
**Starting handoff:** `6a50046b23e4f4cef6667b80d2e700e7167d14ac`
**Pinned Hermes:** `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`)
**Scope:** repository-local GitHub Gauntlet only; no external providers/tools; no push or merge

## Stage status

| Stage | Scope | Result | Primary commits |
|---|---|---|---|
| 1 | Source/graph seam map and audit boundaries | COMPLETE | inherited handoff plus source confirmation |
| 2 | TOKEN-000 and TOKEN-010 measurement/session continuity | PASS | `b793e6f`, `4e455e4`, `d00e8e5` |
| 3 | TOKEN-100 and TOKEN-600 lean prefetched context/model-call controls | PASS | `7731031`, `760e085` |
| 4 | TOKEN-200/300/500 compiled tools, sparse context, JIT retrieval | PASS | `ca4a149`, `f431fe2` |
| 5 | TOKEN-400 safe large-result externalization/rehydration | PASS | `dcb63f1`, `31c4080` |
| 6 | TOKEN-700 matched local qualification | VALID FAIL | `bd621d6`, `8457ff8`, `a8961c9`, `c6e09d7` |
| 7 | Final process audit, evidence preservation, handoff | COMPLETE | this handoff |

All requested stages were executed. The final state is deliberately fail-closed: component
mechanisms and quality/safety pass, but the complete retrofit is not promoted because both frozen
overall efficiency gates failed.

## Final evidence

The authoritative result is
`outputs/TOKEN_700_QUALIFICATION_2026-08-30.json`, summarized by
`outputs/TOKEN_700_IMPLEMENTATION_REPORT_2026-08-30.md`.

- Quality: baseline 30/30, candidate 30/30, zero regressions.
- Safety: zero candidate false clears, cross-task leaks, releases, receipts, or canonical mutation.
- Candidate auxiliary calls: zero; baseline measured 20 title-generation calls.
- Route/status maxima: 113 and 262 tokens; both gates pass.
- Overall median conversation-input reduction: -21.37%; 40% gate fails.
- Overall median complete-token reduction: +10.44%; 25% gate fails.
- Continuity median: +35.98%; W09 resumed sessions: +43.81% conversation input.
- Full regression suite: 508 tests passed in 48.658 seconds.

V1 and V2 are preserved as explicitly invalid JSON artifacts. Their outcomes were never combined
with v3. V3 added exact 102-turn marker preflight and passed every quality/reconciliation check.

## Decision

Do not merge or promote this branch as an overall token-efficiency success. The valid evidence
supports retaining the measurement, continuity, sparse-context, tool-compilation, title-suppression,
and safe externalization mechanisms as a basis for the next iteration, but not the overall savings
claim.

The next load-bearing discriminator is a new candidate that bypasses or materially shrinks the
volatile lean capsule and compiled tool surface on short/capability-absence turns while preserving
W08-W10 continuity behavior. That work must receive a new immutable runtime commit and prospective
TOKEN-700 protocol; v3 must remain unchanged.

## Repository state contract

- No external service, web search, browser, MCP catalog, or billable model was used.
- No submodule source was edited; the Hermes gitlink remains pinned and clean.
- No push, merge, release, or canonical receipt was performed.
- `graphify-out/` is pre-existing untracked operator data and was never staged or modified.

**PROCESS ASSURANCE:** repeated invalid evaluations were version-bounded and retained; no exposed
threshold was relaxed; the valid all-green quality result was denied promotion on its two failed
efficacy gates.
