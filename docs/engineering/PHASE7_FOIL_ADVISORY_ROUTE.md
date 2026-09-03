# FAST-P7 — Advisory FOIL Route Before Runtime Work

Status: **implemented candidate / checkpoint qualification required**

## Scope

FAST-P7 adds one proposal-only FOIL route before the first model request of a
Gauntlet-bundled runtime turn. It is the fast-build route milestone, not
`NATIVE-600`, `NATIVE-700`, a production activation, or evidence of routing
efficacy.

The sequence is:

```text
runtime tool schemas
→ semantic capability snapshot
→ read-only Gauntlet module adapter
→ existing RuntimePolicyV2
→ minimum capability bundle proposal
→ bounded public route instruction
→ first model request
```

The route is computed from:

- the integrity-valid canonical task and its load-bearing obligations;
- explicit `metadata.foil_task_context` fields, when present;
- the runtime-reported tool-definition manifest and derived semantic
  capabilities.

The route does not receive the raw user prompt, obligation claim text, profile
memory, skill content, provider credentials, or raw tool output.

## Authority boundary

Every route uses:

```text
schema: gauntlet.foil-route.v1
mode: SHADOW
authority_ceiling: ADAPTATION_ONLY
execution_authorized: false
toolset_narrowing_applied: false
profile_used: false
private_profile_data_transmitted: false
```

The route cannot:

- create a canonical receipt;
- change a verdict;
- clear an obligation;
- release a task;
- execute a tool;
- narrow the active toolset;
- replace claim-native verification;
- replace Soul's release gate.

Runtime-reported capability availability is explicitly marked
`verified_by_gauntlet=false`. It is planning input, not authority evidence.

## Minimum-bundle behavior

The existing FOIL policy produces task regime, effort mode, required and
pending verifiers, task complements, actions, resource allocation, and stop
advice. FAST-P7 maps those requirements to the frozen semantic capability
registry and selects the first available minimum-sufficient capability for
each requirement.

Missing capability groups remain explicit. They do not become invented tools,
automatic fallbacks, or a successful verification claim.

## Runtime integration

`gauntlet_host/phase7_worker.py` wraps the existing isolated worker. It
intercepts the single upstream `AIAgent.run_conversation` call, obtains the
route after tool discovery, injects the bounded route block before the original
prompt, and restores the original method after the turn. The pinned upstream
Hermes gitlink is unchanged.

Operational route failure returns `UNAVAILABLE` before the model request. It
does not create a Gauntlet verdict.

## Qualification target

The bounded checkpoint harness must establish:

1. live tool definitions are mapped to semantic capabilities;
2. unknown capability names fail closed;
3. the route is task-bound and content-hashed;
4. the route enters the first model request;
5. raw claim text and profile data are absent;
6. the runtime still executes `gauntlet_task_status`;
7. tool results remain `OBSERVATION_ONLY`;
8. the existing Soul gate still returns `UNKNOWN` for the unresolved fixture;
9. no receipt is created and the task remains unreleased.

FAST-P8, including the single user-facing alpha CLI, remains separate.
