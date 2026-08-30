# TOKEN-700 Matched Qualification Preregistration v3

**Protocol:** `gauntlet.token700-preregistration.v3`
**Frozen:** 2026-08-30, after discarding v1/v2 and before any v3 matched outcome run
**Status:** `FROZEN_LOCAL_GAUNTLET_ONLY`
**Authority ceiling:** evaluation evidence only; no release authority

## 0. Invalid predecessors and binding corrections

Both prior complete runs returned `INVALID_BASELINE`; neither produced a promotable efficacy
percentage.

- v1 combined title-generation and conversation requests in conversation oracles, prohibited a
  legitimate baseline title request, answered the title request through the conversation fixture,
  and read route metrics from the wrong payload level.
- v2 corrected those defects and proved the candidate makes zero auxiliary calls, has zero
  candidate safety events, and emits bounded route/status metrics. It nevertheless remained
  invalid: `expand_turns()` used `None` as W10's first template when the optional
  `first_prompt_template` key was absent, producing the literal prompt `"None"` in all six W10 arm
  executions. The same run also showed one legitimate baseline title attempt on W08 turn 3, while
  v2 had incorrectly limited baseline title generation to T01.

The v2 stored quality totals were baseline 26/30 and candidate 27/30 with zero candidate
regressions, but the run was invalid and all efficacy fields were suppressed. Those counts inform
only the protocol repair; they are not v3 evidence.

V3 makes exactly two semantic corrections:

1. absent `first_prompt_template` falls back to the required `prompt_template`, and preflight
   rejects any expanded turn lacking its exact `TOKEN700|case|turn|` marker;
2. the baseline may emit at most one measured pinned-Hermes `title_generation` request anywhere in
   a case's single session, while the candidate must still emit zero.

The v1 and v2 raw artifacts are retained only under explicit `V1_INVALID` and `V2_INVALID` names.
They are not used in v3 thresholds, selection, statistics, or promoted reporting.

## 1. Bounded question and scope

This run asks whether the continuity-correct FAST-P8 baseline and complete TOKEN-100..600 candidate
remain equivalent on frozen local engineering invariants while the candidate reduces
provider-bound input composition and avoids auxiliary model calls.

The user constrained execution to this GitHub Gauntlet and its pinned Hermes gitlink. The endpoint
is a deterministic localhost fixture; authorized runtime tools are repository-owned Gauntlet tools;
no external web, browser, MCP, model, bot, or billable provider is used. Capability-absence
workloads do not qualify those external capabilities. Real-model quality, prompt-cache behavior,
money, external-tool savings, production promotion, and release authority are not established.

## 2. Frozen identities

| Field | Baseline | Candidate |
|---|---|---|
| Role | continuity-correct FAST-P8 baseline | TOKEN-100..600 plus scoped title suppression |
| Runtime commit | `4e455e4dcddc329a6d2455676fdfc78a17338523` | `bd621d64876ff2434ebef46c2115603e072bd247` |
| Runtime tree | `17225910e1962b18b652e922c01e897f707f5eb1` | `1b7a2d47540aef0a0fb68707bd2e1cf5a3ed9667` |
| Prior evidence | `d00e8e5a69cad022bc9a5cb701d3addcaeabfb81` | `31c4080482a15624e422d30ce3c0a980b719ced9` plus focused candidate tests |
| Hermes gitlink | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |

The runtime commits are the executable identities. Each arm runs from a detached temporary
worktree. Pinned Hermes bytes are copied from the clean local gitlink; no arm or submodule source is
patched by the evaluator.

## 3. Frozen workload population

```text
benchmarks/token700/workloads.v3.json
SHA256 4a95d8e3d54afc26a5d198df43257ac3e58731b3fcd1cf0049cb82b867297947
```

Prompts, obligations, variants, actions, and ordering are byte-for-byte the v2 workload content.
Only protocol metadata changed. The suite remains ten workload classes times three variants: 30
matched pairs in workload/variant order. It is a finite deterministic suite, not an IID sample; the
quality margin is zero percentage points and no population confidence interval is claimed.

Every expanded turn must contain exactly its expected case/turn marker. Manifest loading and
`--validate-only` exercise this preflight before worktrees or outcomes are created.

Arm order remains balanced by case index. Canonical task state, Python, dependencies, fixture model,
provider, context/output limits, retry/tool-iteration caps, timeout, and Gauntlet-only tool
availability remain matched.

## 4. Request classification and auxiliary policy

Requests are classified before oracles:

- `conversation`: pinned main chat-completions stream, no `session_title` response schema;
- `title_generation`: response schema name exactly `session_title`;
- `unknown`: invalidates the arm turn.

Conversation marker, action, tool, dispatch-count, and continuity checks inspect conversation
requests only. Every server request must reconcile one-for-one with a persisted TOKEN-000
measurement of the same kind. Raw requests and responses are not persisted.

The baseline may make zero or one measured `title_generation` request across the entire case/session,
on any turn. A second title request or any other auxiliary task invalidates the baseline. Candidate
policy is unchanged: zero auxiliary requests on every turn and across the case.

Auxiliary input/output/reasoning/cache-write units are included in complete-token cost. Primary
input efficacy remains conversation-only. API, conversation dispatch, auxiliary dispatch, tool,
and cache-read counts are reported separately.

## 5. Quality protocol

Conversation actions remain:

- `FINAL`: one dispatch, no tool, exact final marker;
- `STATUS_THEN_FINAL`: one read-only status call then exact final marker;
- `UNAVAILABLE_FINAL`: one explicit unavailable marker, no completion or clearance claim.

Every turn and case check must pass: exact output/current/history context, measurement/source
reconciliation, session binding, read-only status behavior, task/obligation parity, no false clear,
release, receipt, mutation, or cross-task leak.

Rules:

1. any baseline hard-invariant failure yields `INVALID_BASELINE` and suppresses efficacy;
2. any candidate safety failure is an immediate failure;
3. observed candidate regressions must be zero;
4. candidate correctness must be at least baseline correctness across all 30 pairs;
5. cases are never added after outcomes to rescue a result.

## 6. Frozen efficacy and safety gates

For every valid pair:

```text
(baseline conversation input - candidate conversation input) / baseline conversation input
```

Medians use case-level paired percentages, not grand totals.

| Endpoint | Gate |
|---|---:|
| Candidate route capsule maximum | <= 512 local estimated tokens |
| Candidate compact status maximum, up to four obligations | <= 1,024 local estimated tokens |
| Candidate extra LLM calls | 0 |
| Canonical task/obligation parity | 100% |
| Candidate false-clear events | 0 |
| Candidate cross-task leaks | 0 |
| Overall median paired conversation-input reduction | >= 40% |
| Continuity stratum (`W08`..`W10`) median | reported, no post-hoc gate |
| Capability-absence controls (`W03`..`W07`) | reported separately |
| Median complete-token reduction | >= 25% local target |
| External MCP/tool-heavy and monetary reduction | not established |

Route/status maxima come from `payload.lean_context.capsule_metrics`. Complete-token units include
all measured conversation and auxiliary local input, output, reasoning, and cache-write tokens;
cache-read is reported separately and never counted as negative cost.

## 7. Stop, amendment, and process assurance

Stop without efficacy for identity/hash/gitlink mismatch, dirty Hermes, incomplete cases, task-state
mismatch, missing expanded marker, unknown request kind, request/measurement mismatch, drops/invalid
records, unexpected source/tool/retry/fallback/network/action, title-policy violation, release,
receipt, mutation, output-oracle failure, or any baseline hard-invariant failure.

After any v3 matched outcome is exposed, another semantic change requires discarding the whole run,
advancing the protocol, and committing a new preregistration before rerunning.

**PROCESS ASSURANCE**

- Fired: `derive`, `self`, `refresh`, `boundary`, `oob` after both invalid runs.
- Frame correction: optional first-turn templates require an explicit fallback and marker preflight;
  pinned asynchronous title attempts are session-bounded, not T01-bounded.
- Counterevidence retained: both invalid artifacts and their exact failed checks.
- Cleared only for this corrected bounded localhost rerun; all broader claim ceilings remain.

Planned outputs:

```text
outputs/TOKEN_700_QUALIFICATION_2026-08-30.json
outputs/TOKEN_700_IMPLEMENTATION_REPORT_2026-08-30.md
```
