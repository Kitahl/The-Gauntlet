# TOKEN-400 implementation report

Date: 2026-08-30
Branch: `work/hermes-token-lean`
Implementation commit: `dcb63f1acf3b7aeab09e065fa116cbc32c5a18cb`
Implementation tree: `ec1fdf9385a16e878d4a8746aaec3cac6f8f85ed`
Pinned Hermes: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`)

## Scope and authority

TOKEN-400 implements the audited large tool-result lifecycle:

```text
sanitized raw result in the current provider call
→ bounded deterministic extraction
→ private task/session-bound operational artifact
→ content hash + short summary + opaque reference
→ full content available only through explicit bounded paging
```

The operational store is not canonical evidence and cannot create or change a Gauntlet verdict, receipt, obligation, or release decision. The pinned Hermes submodule is unchanged.

## Implementation

- Intercepts pinned Hermes' post-tool persistence seam inside the isolated Gauntlet worker and restores the original function after every run.
- Applies the Gauntlet lifecycle only to text results above 8,000 characters. Small results remain on the existing Hermes path, so raw output is not stored merely because the lifecycle exists.
- Redacts deterministic secret patterns before any artifact write, including plain assignments, JSON-quoted keys/values, JSON-escaped lines, bearer values, OpenAI-style keys, GitHub tokens, and AWS access-key IDs.
- Rejects results above the 2,000,000-character hard artifact bound without falling back to raw durable replay.
- Stores sanitized content under the isolated runtime home in task- and session-hashed private buckets.
- Uses a full SHA-256 content address (`art_<sha256>`), validates schema, task binding, session binding, content length, hash, and expiry on every read, and applies a 24-hour TTL.
- Produces a bounded structural summary without an auxiliary model call.
- Persists only a compact, opaque reference in the Hermes transcript.
- Projects the full sanitized content plus its reference into the immediate provider request only. The provider-response hook acknowledges visibility so retries remain safe while later requests use only the reference.
- Adds `gauntlet_artifact_get` to the deterministic capability compiler as `BOUNDED_OPERATIONAL_REHYDRATION`.
- Bumps the compiled surface to `gauntlet-active-v2` and the standalone plugin manifest to `0.4.0`.
- Limits explicit retrieval to 4,096 characters per call; the live qualification requested 512 characters.
- Never exposes the private artifact filesystem path to the model.

## Verification

All gates used repository-local code, the pinned Hermes submodule, and localhost-only provider fixtures.

| Gate | Result |
| --- | --- |
| TOKEN-400 focused lifecycle tests | 7 passed |
| TOKEN-400 plus prior-stage focused tests | 16 passed |
| Full repository suite | 494 passed in 96.334 seconds |
| Changed-file Ruff format/lint, compilation, and diff integrity | PASS |
| TOKEN-010 sequential continuity replay | PASS: 10 task-A turns, no cross-task leak, fresh-parent resume at turn 6 |
| TOKEN-400 committed-source live qualification | PASS |
| TOKEN-100/600 committed-source compatibility | PASS |
| TOKEN-200/300/500 committed-source compatibility | PASS |

The TOKEN-400 live gate observed:

- a canonical claim of 11,853 characters;
- one sanitized operational artifact of 13,091 characters, including the surrounding exact-obligation response;
- a 644-character durable reference;
- one explicitly retrieved 512-character page;
- three provider requests: obligation detail, explicit artifact page, then final response;
- exactly four model-visible tools;
- full sanitized content visible in the immediate provider call;
- only the reference persisted for the original large tool result;
- no current-call projection or tail marker in the durable transcript;
- no raw secret in the provider-visible content, artifact, or transcript;
- verified content hash and TTL;
- no private artifact path in any provider request; and
- zero canonical receipts and no canonical-state mutation.

During verification, the first live gate exposed a JSON-escaped secret-redaction miss. The scanner was corrected and a permanent regression test was added before the successful live qualification. A parallel full-suite run also exceeded an existing 60-second FOIL enumeration budget because it competed with the ten-turn live replay; the isolated timing test passed in 40.958 seconds, and the authoritative uncontended full suite passed.

The local pinned runtime emitted its existing SQLite 3.49.1 WAL-reset warning and safely used `journal_mode=DELETE`. No WAL mode was enabled by this work.

## Evidence

- `outputs/TOKEN_400_QUALIFICATION_2026-08-30.json`
- `outputs/TOKEN_100_600_TOKEN400_COMPATIBILITY_2026-08-30.json`
- `outputs/TOKEN_200_300_500_TOKEN400_COMPATIBILITY_2026-08-30.json`
- `.github/token400_verify.py`
- `tests/test_tool_result_lifecycle.py`

All three JSON manifests bind their results to implementation commit `dcb63f1acf3b7aeab09e065fa116cbc32c5a18cb`, tree `ec1fdf9385a16e878d4a8746aaec3cac6f8f85ed`, and pinned Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`.

## Claim boundary

This stage establishes source-bound functional correctness for TOKEN-400 and compatibility with the completed TOKEN-100/200/300/500/600 mechanisms. It does not establish an end-to-end token-reduction percentage, latency benefit, cost benefit, quality non-inferiority, or release readiness. Those claims remain gated on TOKEN-700's prospectively frozen matched evaluation.
