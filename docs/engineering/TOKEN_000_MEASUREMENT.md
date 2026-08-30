# TOKEN-000 Provider-Boundary Measurement

Status: measurement-only checkpoint. This phase adds observation and qualification; it does not optimize prompts, compress context, change tool schemas, alter routing, or claim token or cost savings.

## Frozen source boundary

TOKEN-000 starts from the FAST-P8 handoff commit `6a50046b23e4f4cef6667b80d2e700e7167d14ac` and tree `bb490654eba9eb5bef24102ba5f94321862cfdd0`. The isolated Hermes snapshot remains pinned to `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`). Each measurement records those frozen identities plus the running Gauntlet commit and tree supplied by the launcher.

## Measurement boundaries

The main conversation path is measured by the Gauntlet plugin's `llm_execution` middleware, after Hermes finishes request construction and before the provider callback. Successful usage is attached by the `post_api_request` hook. Failed attempts are recorded by the middleware itself.

Hermes auxiliary calls do not consistently traverse the main plugin path. The worker therefore installs process-local, behavior-preserving wrappers around the pinned auxiliary relay functions:

- `_relay_sync_completion`
- `_relay_async_completion`
- `_relay_sync_stream`

These wrappers cover Hermes-owned logical retries and fallback destinations. The measurement unit is a logical provider dispatch, not an SDK-internal HTTP retry or exact wire byte sequence. `wire_utf8_bytes` and time to first token remain `null` unless a future provider adapter supplies them directly.

## Stored fields

Each content-addressed `gauntlet.token-measurement.v1` record contains:

- task, host request, runtime session, turn, workload, dispatch, attempt, and retry identity;
- requested and effective provider, model, API mode, sanitized endpoint identity, and fallback state;
- running/frozen source identity;
- canonical request character and UTF-8 byte counts, a documented local token estimate, and keyed HMAC digests;
- non-overlapping component counts for the combined system material, tool schemas, FOIL route, canonical task status, conversation roles, images, and the remaining request envelope;
- provider-reported input, output, cache-read, cache-write, reasoning, and total tokens with unknown values preserved as `null` and reported zeroes preserved as `0`;
- outcome, error class, timeout/cancellation flags, latency, tool-call count, and explicitly unpriced cost metadata.

Stable/context/volatile system provenance and separate skill, memory, profile, and context-file attribution are marked `UNAVAILABLE`: pinned Hermes has already merged them before the final provider boundary. Combined system size is measured, but the implementation does not invent a more precise attribution.

A per-host-request `gauntlet.token-measurement-summary.v1` reconciles main dispatch records against Hermes' main `api_calls` count. Auxiliary and conversation counts are reported separately because Hermes' aggregate usage and `api_calls` cover the conversation path only.

## Privacy and authority

Raw prompts, tool outputs, and model responses are not written to the measurement store or qualification manifest. Content identity uses HMAC-SHA256 with a private, runtime-local 32-byte key. Endpoint hostnames are also HMACed; query strings and user information are not persisted. Counts, sanitized metadata, outcomes, and keyed digests are retained.

The storage bridge recursively rejects raw-content keys and canonical-authority fields. Measurements have an `OBSERVATION_ONLY` authority ceiling and cannot create receipts, clear obligations, release tasks, or mutate canonical state.

## Frozen qualification workloads

The TOKEN-000 verifier lists ten workload classes:

1. no-tool one-shot;
2. one canonical status-tool call;
3. web research;
4. coding/edit/verification;
5. browser interaction;
6. small MCP catalog;
7. large MCP catalog;
8. ten-turn chat;
9. resumed long session;
10. mixed multi-obligation task.

The deterministic local provider currently measures W01, W02, and W08. W03-W07 and W10 remain `NOT_MEASURED` because this checkpoint has no frozen local fixture for those tool/provider surfaces. W09 remains blocked when the session-continuity probe fails. Unmeasured workloads are retained in the manifest rather than silently removed.

The ten-turn workload uses private canaries only in memory and in local provider requests. It separately checks whether all turns share a runtime session and whether prior canaries reach later final provider requests. The current launcher starts a fresh worker and Hermes session per turn, so continuity failure is an explicit correctness result, not a token-efficiency improvement.

## Verification

Run the focused unit tests:

```powershell
python -m unittest tests.test_token_measurement -v
```

Run the deterministic pinned-runtime qualification:

```powershell
python .github/token000_verify.py --output <manifest-path>
```

The verifier starts a localhost-only synthetic provider, compares its observed request count with stored dispatch measurements, checks raw-content non-persistence, records all ten workload statuses, and reports session correctness. Synthetic usage values are suitable for plumbing verification only and are not a token or cost baseline.

## Claim boundary

TOKEN-000 can establish that the configured logical provider boundaries were observed on the executed fixtures and that the stored records satisfy the privacy/counting contract. It cannot establish token savings, cost savings, quality non-inferiority, prompt-cache behavior, cross-task isolation, restart/resume correctness, or coverage of workloads that remain `NOT_MEASURED`.