# TOKEN-700 Matched Qualification Preregistration v2

**Protocol:** `gauntlet.token700-preregistration.v2`  
**Frozen:** 2026-08-30, after discarding v1 and before any v2 matched outcome run  
**Status:** `FROZEN_LOCAL_GAUNTLET_ONLY`  
**Authority ceiling:** evaluation evidence only; no release authority

## 0. Why v1 is invalid

The complete v1 run returned `INVALID_BASELINE`. No v1 efficacy percentage is promotable.
Inspection found semantic evaluator defects after outcome exposure, so the entire run is discarded
under the v1 amendment rule and this independently frozen protocol supersedes it.

The defects were:

1. pinned Hermes legitimately generated an asynchronous session-title request on a new baseline
   session, while v1 incorrectly required zero auxiliary requests in both arms;
2. v1 applied conversation marker and dispatch-count oracles to the combined conversation and
   auxiliary server-request slice, and the fixture answered title requests as conversations;
3. route and status capsule metrics were read from `payload.capsule_metrics` although the committed
   candidate emits them at `payload.lean_context.capsule_metrics`.

The invalid run also exposed a real candidate gap: automatic title generation was still enabled.
Candidate commit `bd621d64876ff2434ebef46c2115603e072bd247` fixes the isolated Gauntlet profile through pinned
Hermes's supported `auxiliary.title_generation.enabled=false` setting. Pinned Hermes source is not
modified. The invalid raw artifact is retained only under an explicit `V1_INVALID` name for audit;
it is not an input to v2 thresholds, case selection, or reported efficacy.

## 1. Question and bounded scope

This evaluation asks whether the continuity-correct FAST-P8 baseline and the complete TOKEN-100..600
candidate remain equivalent on frozen local engineering invariants while the candidate reduces
provider-bound input composition and avoids candidate-side auxiliary model calls.

The user constrained the run to this GitHub Gauntlet and its pinned Hermes gitlink. Therefore:

- the model endpoint is a deterministic localhost fixture;
- the only authorized runtime tools are repository-owned Gauntlet tools;
- no external web, browser, MCP, model, bot, or billable provider is used;
- web, browser, coding-tool, and MCP workloads are capability-absence controls;
- real-model quality, prompt-cache behavior, money, and live external-tool savings are not established.

A passing run may be called `LOCAL_NONMONETARY_NONINFERIOR`. It may not be called production
promotion or real-model, external-tool, cache, or monetary qualification.

## 2. Frozen arms

| Field | Baseline | Candidate |
|---|---|---|
| Role | continuity-correct FAST-P8 baseline | TOKEN-100..600 candidate plus scoped title suppression |
| Runtime commit | `4e455e4dcddc329a6d2455676fdfc78a17338523` | `bd621d64876ff2434ebef46c2115603e072bd247` |
| Runtime tree | `17225910e1962b18b652e922c01e897f707f5eb1` | `1b7a2d47540aef0a0fb68707bd2e1cf5a3ed9667` |
| Prior evidence envelope | `d00e8e5a69cad022bc9a5cb701d3addcaeabfb81` | `31c4080482a15624e422d30ce3c0a980b719ced9` plus focused tests at candidate commit |
| Hermes gitlink | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |

The runtime commits, not branches or evidence commits, are the executable identities. Each arm runs
from a detached temporary worktree. Pinned Hermes bytes are copied from the clean local gitlink;
neither arm source nor the submodule is patched by the evaluator.

## 3. Frozen workloads and sample

The authoritative manifest is:

```text
benchmarks/token700/workloads.v2.json
SHA256 7a5cbff109f53348a43f84bcc3b819ddcdad0d6cb13d683236b42f7326089a3f
```

The ten workload definitions, their three fixed variants, prompts, obligations, and ordering are
byte-for-byte the v1 workload content after its pre-outcome continuity amendment. Only protocol
metadata and global oracle names changed. The suite remains exactly 30 matched pairs, ordered by
workload ID then variant. It is a finite deterministic suite, not an IID sample; the quality margin
is zero percentage points and no population confidence interval is claimed.

Arm order remains balanced: even case indexes run baseline then candidate; odd indexes run candidate
then baseline. The canonical task state, Python executable, installed dependencies, fixture model,
provider, context length, output cap, retry cap, tool-iteration cap, timeout, and Gauntlet-only tool
availability are matched.

## 4. Frozen request classification and auxiliary policy

Server requests are classified before any oracle is applied:

- `conversation`: a pinned main chat-completions stream with no `session_title` response schema;
- `title_generation`: a request whose JSON response schema name is exactly `session_title`;
- `unknown`: anything else, which invalidates the arm turn.

Conversation marker, action, tool, dispatch-count, and continuity oracles inspect conversation
requests only. Every server request must reconcile one-for-one with a persisted TOKEN-000 measurement
of the same kind. No raw request is persisted.

The baseline may make at most one measured `title_generation` request on `T01` of a newly created
session and none on later turns. The fixture returns deterministic structured title JSON. Any other
baseline auxiliary task, retry, second title request, or later-turn title request invalidates the
baseline. The candidate must make zero auxiliary requests on every turn. This is both a correctness
check and the frozen candidate-extra-LLM-call gate.

Auxiliary request input, output, reasoning, and cache-write units are included in complete-token
cost. Primary input efficacy remains conversation-only so an auxiliary request cannot masquerade as
conversation compression. API-call, conversation-dispatch, auxiliary-dispatch, tool-call, and
cache-read counts are reported separately.

## 5. Frozen provider and quality protocol

The conversation fixture reads the latest user turn marker and uses one of three actions:

- `FINAL`: one conversation dispatch, no tool call, exact final marker;
- `STATUS_THEN_FINAL`: one read-only Gauntlet status call followed by one exact final marker;
- `UNAVAILABLE_FINAL`: one conversation dispatch with an explicit unavailable marker and no
  completion or clearance claim.

A case arm is correct only when every turn and case check passes. Checks cover worker completion,
exact final output, current and required historical context, complete measurement reconciliation,
source identity, session binding, status read-only behavior, task/obligation parity, no false clear,
no canonical receipt or release, no mutation, and no cross-task marker leak.

Primary quality rules are unchanged:

1. any baseline hard-invariant failure makes the run `INVALID_BASELINE` and suppresses efficacy;
2. any candidate safety failure is an immediate `FAIL`;
3. observed candidate regressions must be zero;
4. candidate correctness must be at least baseline correctness across all 30 pairs.

One or more regressions fails the frozen gate; cases are not added to rescue the result.

## 6. Frozen efficacy and safety gates

For each valid pair, primary input reduction is:

```text
(baseline conversation input - candidate conversation input) / baseline conversation input
```

Medians are computed across case-level paired percentages, never from grand totals.

| Endpoint | Gate |
|---|---:|
| Candidate route capsule maximum | <= 512 local estimated tokens |
| Candidate compact status maximum, up to four obligations | <= 1,024 local estimated tokens |
| Candidate extra LLM calls | 0 |
| Canonical task/obligation parity | 100% |
| Candidate false-clear events | 0 |
| Candidate cross-task context leaks | 0 |
| Overall median paired conversation-input reduction | >= 40% |
| Continuity stratum (`W08`..`W10`) median reduction | reported, no post-hoc gate |
| Capability-absence controls (`W03`..`W07`) | reported separately |
| Median complete-token reduction | >= 25% local target |
| External MCP/tool-heavy and monetary reduction | not established |

Route/status maxima are read from the committed nested `payload.lean_context.capsule_metrics` path.
Complete-token units sum all measured conversation and auxiliary local input, output, reasoning, and
cache-write tokens. Cache-read is reported and is never treated as negative cost.

## 7. Stop and amendment rules

Stop without an efficacy claim for an identity/hash/gitlink mismatch, dirty Hermes checkout,
incomplete case count, task-state mismatch, unknown request kind, request/measurement count mismatch,
measurement drop or invalid record, unexpected source identity, tool, retry, fallback, network target,
provider action, title policy violation, release, receipt, mutation, baseline failure, or output-oracle
failure.

After any v2 matched outcome is exposed, a semantic evaluator, workload, or oracle change requires
discarding the whole run, advancing the protocol again, and committing a new preregistration before
rerunning. Formatting-only report fixes may not alter stored measurements or dispositions.

## 8. Process assurance and planned outputs

**PROCESS ASSURANCE**

- Fired: `derive`, `self`, `refresh`, `boundary`, `oob`.
- Frame correction: title generation is a distinct measured auxiliary dispatch, not a conversation
  failure; candidate suppression is still a strict zero-call requirement.
- Counterevidence retained: v1 `INVALID_BASELINE`, candidate title-call gap, W10 first-turn fixture
  contamination, and missing route metrics.
- Result: `CLEARED` only for this corrected, bounded localhost rerun.
- Claim ceiling: no real-model, external-tool, cache, monetary, or release claim.

Planned immutable outputs:

```text
outputs/TOKEN_700_QUALIFICATION_2026-08-30.json
outputs/TOKEN_700_IMPLEMENTATION_REPORT_2026-08-30.md
```
