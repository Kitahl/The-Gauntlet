# TOKEN-700 Matched Qualification Preregistration

**Protocol:** `gauntlet.token700-preregistration.v1`  
**Frozen:** 2026-08-30, before any matched TOKEN-700 outcome run  
**Status:** `FROZEN_LOCAL_GAUNTLET_ONLY`  
**Authority ceiling:** evaluation evidence only; no release authority  

## 1. Question and scope

This evaluation asks whether the continuity-correct FAST-P8 runtime and the token candidate
remain behaviorally equivalent on frozen local engineering invariants while the candidate
reduces provider-bound input composition.

The user constrained the run to this GitHub Gauntlet and its pinned Hermes gitlink. Therefore:

- the model endpoint is a deterministic localhost fixture;
- the only authorized runtime tools are the repository's Gauntlet tools;
- no external web, browser, MCP, model, bot, or billable provider is used;
- web, browser, coding-tool, and MCP workloads are capability-absence controls rather than
  qualification of those external capabilities;
- monetary savings, real-model semantic quality, prompt-cache behavior, and non-empty external
  MCP catalog savings cannot be established by this run.

A passing run may be called `LOCAL_NONMONETARY_NONINFERIOR`. It may not be called full production
promotion, real-model quality noninferiority, external-tool noninferiority, or monetized
complete-cost qualification.

## 2. Frozen arms

| Field | Baseline | Candidate |
|---|---|---|
| Role | continuity-correct FAST-P8 baseline | complete TOKEN-100..600 candidate |
| Runtime commit | `4e455e4dcddc329a6d2455676fdfc78a17338523` | `dcb63f1acf3b7aeab09e065fa116cbc32c5a18cb` |
| Runtime tree | `17225910e1962b18b652e922c01e897f707f5eb1` | `ec1fdf9385a16e878d4a8746aaec3cac6f8f85ed` |
| Evidence envelope | `d00e8e5a69cad022bc9a5cb701d3addcaeabfb81` | `31c4080482a15624e422d30ce3c0a980b719ced9` |
| Hermes gitlink | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |

The evidence-envelope commits add reports only. The runtime commits are the executable arms.
Neither floating branch names nor the preregistration commit are executable-arm identities.

## 3. Frozen workload population and sample size

The authoritative manifest is:

```text
benchmarks/token700/workloads.v1.json
SHA256 ce94b63a1488500895883fc0328aac637e1fcbca6bcec6959c4fbc44f01672de
```

It contains the ten audit-named workload classes and three fixed variants (`S01`, `S02`, `S03`)
per class, for exactly 30 matched case pairs. Case order is workload ID then variant ID.

Thirty pairs were selected prospectively to keep the ten workload classes balanced with three
separate fixed task/session manifests and provider-bound measurements per class. The run does not
add cases after outcomes are visible. These deterministic variants are not independent draws from
a human/model task population, so no binomial confidence interval or population-level power claim
is used. Noninferiority is a strict finite-suite claim with a frozen margin of zero percentage
points.

## 4. Matched controls

Every pair uses the same:

- workload and variant manifest;
- copied canonical task and obligation state, including IDs, timestamps, claims, and hashes;
- pinned Hermes source bytes;
- Python executable and installed dependencies;
- `phase5-mock` model name;
- `custom` provider;
- one localhost OpenAI-compatible chat-completions endpoint;
- deterministic response protocol and output strings;
- 131,072-token declared context length;
- 256-token output cap;
- one retry maximum;
- eight tool iterations maximum from the frozen host runtime;
- 90-second per-turn wall-clock timeout;
- Gauntlet-only authorized tool availability;
- no auxiliary/background model call;
- request/turn budget and stop rules.

Arm order is balanced deterministically across the 30 lexicographically ordered cases: even case
indexes run baseline then candidate; odd indexes run candidate then baseline. Timing is descriptive
only because localhost process startup noise is not a production latency benchmark.

Each arm executes from a detached temporary worktree at its exact runtime commit. The pinned
Hermes bytes are copied from the clean local gitlink checkout. No arm source file is patched.

## 5. Frozen provider and stop protocol

The fixture reads only the latest user turn marker.

- `FINAL`: one provider dispatch, no tool call, exact final marker.
- `STATUS_THEN_FINAL`: one exposed Gauntlet status call followed by one exact final marker.
- `UNAVAILABLE_FINAL`: one provider dispatch returning an explicit unavailable marker and no
  completion or clearance claim.

Any retry, fallback, auxiliary dispatch, unexpected tool, extra provider dispatch, missing final
marker, or unexpected server route invalidates that case. The server reports deterministic token
usage derived from the received request and response; the primary input endpoint remains the
Gauntlet provider-bound local estimator already qualified in TOKEN-000.

## 6. Frozen quality endpoint and noninferiority rule

A case arm is correct only if every global and workload-specific check in the workload manifest
passes. The checks cover worker completion, exact output protocol, current/relevant context,
measurement completeness, session binding, status read-only behavior, task/obligation parity,
no false clearance, no canonical receipt, no task release, and no cross-task marker leak.

Primary quality rules:

1. Any baseline hard-invariant failure makes the evaluation `INVALID_BASELINE`; token outcomes
   from that run are not promoted.
2. Any candidate safety failure (false clear, release, receipt, mutation, or cross-task leak) is an
   immediate `FAIL`.
3. Candidate regressions are pairs where baseline is correct and candidate is incorrect.
4. Observed candidate regressions must equal zero.
5. Candidate correctness on the complete frozen 30-pair suite must be greater than or equal to
   baseline correctness; the frozen finite-suite noninferiority margin is 0 percentage points.

With 30 valid pairs, zero observed regressions satisfies rules 4 and 5. One or more regressions
fails the frozen gate; the suite is not enlarged to rescue it. McNemar statistics may be reported
as descriptive sensitivity only and are not the noninferiority test. Passing applies only to this
finite frozen suite and does not estimate a broader task-population regression probability.

## 7. Frozen efficacy and safety endpoints

For each valid pair, case input cost is the sum of `local_estimated_tokens` over conversation
provider dispatches. The paired reduction is:

```text
(baseline_case_input - candidate_case_input) / baseline_case_input
```

The following gates are frozen before outcomes:

| Endpoint | Gate |
|---|---:|
| Candidate route capsule | maximum <= 512 local estimated tokens |
| Candidate compact status, up to four frozen obligations | maximum <= 1,024 local estimated tokens |
| Candidate extra LLM calls | 0 |
| Valid canonical task/obligation parity | 100% |
| Candidate false-clear events | 0 |
| Candidate cross-task context leaks | 0 |
| Overall median paired input-token reduction | >= 40% |
| Continuity stratum (`W08`..`W10`) median paired reduction | reported, no post-hoc gate |
| Capability-absence controls (`W03`..`W07`) | reported separately |
| External MCP/tool-heavy median reduction | not established in this Gauntlet-only run |
| Median complete-token reduction | >= 25% descriptive local target |
| Monetary complete-cost reduction | not established; localhost fixture is unpriced |

`complete-token` is the case sum of local estimated input, provider-reported output, reasoning,
and cache-write tokens, with cache-read tokens reported separately and never treated as negative
cost. API calls, tool calls, wall latency, source identity, and monetary status are separately
reported for every case; they are not hidden inside an arbitrary dollar conversion.

No percentage is reported unless all 30 pairs are valid. Medians are computed over case-level
paired percentages, not a ratio of grand totals. Workload medians and raw paired values are always
published so a large long-session case cannot hide single-turn regressions.

## 8. Complete-cost record

Every arm/case records, where available:

- provider-bound component counts and keyed digests;
- local estimated input tokens;
- provider-reported input, cache-read, cache-write, output, reasoning, and total tokens;
- logical API calls and tool calls;
- retry and fallback indicators;
- latency and time to first token;
- runtime/model/provider/endpoint identity;
- source commit/tree and Hermes gitlink;
- cost status and estimated money, which must remain `UNPRICED`/null for this fixture;
- task, obligation, session, release, receipt, and mutation checks.

Raw prompts, raw responses, secrets, and raw tool outputs are not persisted in the qualification
artifact. Fixed public workload templates and marker identifiers are not secrets.

## 9. Stop, discard, and amendment rules

Stop without an efficacy claim if any of these occurs:

- arm commit/tree or Hermes gitlink mismatch;
- workload manifest hash mismatch;
- dirty Hermes checkout;
- inability to create isolated exact worktrees;
- task/obligation state differs between arms;
- measurement drop, invalid record, unknown dispatch kind, or source-identity mismatch;
- unexpected network target, provider action, tool call, retry, fallback, or auxiliary call;
- any baseline hard-invariant failure;
- incomplete case count.

An evaluator defect found before outcome exposure may be fixed and recorded. After any matched
outcome is exposed, a semantic evaluator/workload/oracle change requires discarding the whole run,
bumping the protocol/manifest version, and committing a new preregistration before rerunning.
Formatting-only report fixes may not change stored raw measurements or dispositions.

## 10. Selection contamination and process assurance

The same implementer selected and will run this local harness and has seen earlier component-level
TOKEN qualification evidence. No matched TOKEN-700 result has been run at freeze time. This is not
an independent or blinded evaluator; the prospective manifest, exact Git objects, strict stop
rules, complete raw paired publication, and non-rescuable zero-regression rule bound that risk.

**PROCESS ASSURANCE**

- Fired: `derive`, `self`, `refresh`, `boundary`, `oob`.
- Claim/frame: a local matched run can establish bounded engineering noninferiority and request
  reduction, but not external-tool, real-model, cache, or monetary performance.
- Evidence inspected: the audit's TOKEN-700 section, live Git objects/trees/gitlinks, TOKEN-000
  measurement contracts, paired-statistics implementation/tests, pinned Hermes runtime source,
  and the hashed workload manifest.
- Counterevidence: five named audit workload classes require capabilities deliberately absent under
  the user's Gauntlet-only constraint; localhost output is deterministic and unpriced.
- Result: `ISSUE` for full promotion; `CLEARED` for the explicitly bounded local qualification.
- Consequence: proceed with the frozen local comparison and publish limitations next to results.
- Next discriminator: a separately preregistered, user-authorized live provider/tool/catalog run is
  required before any external-tool, real-model, cache, or monetary claim.

## 11. Planned immutable outputs

```text
outputs/TOKEN_700_QUALIFICATION_2026-08-30.json
outputs/TOKEN_700_IMPLEMENTATION_REPORT_2026-08-30.md
```

The JSON will contain all raw paired numeric measurements, checks, case dispositions, formulas,
and exact identities. The report will summarize the JSON without adding a stronger claim.
