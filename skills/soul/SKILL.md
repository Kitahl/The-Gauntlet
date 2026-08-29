---
name: soul
description: Automatic Research Orchestrator — control plane for the Evidence-Governed Research Toolkit. Trigger: /soul, "orchestrate", "route this", or equivalent. Automatically reframes incorrect active tasks with lineage, routes every dependency-ready obligation, integrates claim-native receipts and challenges, runs Process Assurance, and releases only a current evidence-bound state.
---

# Research Orchestrator

Soul owns **automatic task control, routing, integration, assurance invocation, and release**. It does not own proof, factual truth, software correctness, experimental validity, review authority, or host adoption.

## Authority

- The user/host controls goals, constraints, priorities, risk tolerance, voluntary actions, and adoption.
- Claim-native modules determine factual warrant.
- Soul emits routing plans, lineage events, and release decisions—not domain receipts.
- FOIL, Council, Gauntlet, or model agreement cannot clear another module's obligation.
- A declared graph is never treated as proof that every real-world obligation was discovered.

## Automatic workflow

1. **Frame** — persist the goal by digest and create the active task.
2. **Reframe automatically** — when a corrected task replaces an unresolved one, the new task becomes active immediately; the old task is preserved as `SUPERSEDED` with content-bound lineage.
3. **Decompose and revise** — create typed obligations and dependencies. If a new obligation appears after freeze, create an automatic successor graph revision rather than blocking discovery or mutating the frozen predecessor.
4. **Freeze** — validate and content-bind the current task revision.
5. **Route automatically** — select every unresolved, dependency-ready obligation by default.
6. **Batch automatically but isolate** — combine same-module transport envelopes while requiring separate subrequest contexts; explicit shared context remains opt-in and unvalidated.
7. **Integrate** — read one current task-scoped receipt/challenge snapshot.
8. **Assure automatically** — add and run a load-bearing Process Assurance obligation when enabled.
9. **Release** — compare-and-swap the task/evidence token and commit only if the same current revision remains cleared.

## Routing

- proof / formal logic / probability derivation → Formal Reasoning (`/mind`)
- literature / prior art / current external facts → Research Discovery (`/space`)
- new mechanism after known routes fail → Method Synthesis (`/reality`)
- code / execution / integration / software correctness → Engineering Verification (`/power`)
- benchmark / baseline / ceiling / cost / stop-go → Evaluation & Benchmarking (`/time`)
- process/frame/stale-state/false-green audit → Process Assurance (`/gauntlet`)
- user/task-specific complementary challenge → FOIL (`/foil`)
- selective independent review → Evidence Review Panel (`/council`)
- grounding before consequential action or after drift → Decision Preflight
- adversarial break attempt → Black Gem

Mandatory claim-native checks and transitive dependencies may not be optimized away.

## Typed runtime contract

`tools/soul_runtime.py` is the public API. It delegates automatic policy to `tools/soul_automatic.py` and low-level evidence/release mechanics to `tools/soul_vnext/`.

- `start_task()` automatically supersedes an incorrect active frame unless strict compatibility mode is explicitly enabled.
- `add_obligation()` follows supersession lineage and creates a successor graph revision when the current graph is frozen.
- `freeze_task()` validates the current revision and injects automatic Process Assurance when configured.
- `plan_routes()` creates an automatic, non-executing routing plan.
- `automatic_release()` plans, runs automatic Gauntlet assurance, and attempts release.
- `release_gate()` and `release_task()` follow lineage to the current task revision.

An obligation may declare:

```text
depends_on[]
cost_units
risk_rank
information_rank
shared_context_group      # optional true shared-context opt-in
candidate_hash            # optional challenge-binding expectation
scope_hash                # optional challenge-binding expectation
```

A task may declare `required_obligation_kinds[]`. Soul checks those caller-declared requirements but does not pretend a goal hash is enough to infer every missing obligation.

## Automatic supersession

A new task does not wait for an incorrect active task to become "resolved."

```text
Task A active
→ corrected frame Task B appears
→ A becomes SUPERSEDED
→ A records superseded_by=B and a reason digest
→ B becomes active immediately
```

No raw supersession reason is persisted. All prior task state remains inspectable and can be revisited through lineage.

A newly discovered obligation after freeze uses the same principle: the frozen task remains unchanged and a successor task revision carries the copied graph plus the new obligation. Existing receipts remain bound to their original task and cannot silently clear the successor.

## Automatic scheduling semantics

The candidate order remains deterministic:

```text
current-state severity descending
risk rank descending
information rank descending
cost units ascending
module ascending
obligation id ascending
```

Production mode is:

```text
AUTOMATIC_ALL_READY
```

It selects **every** dependency-ready unresolved obligation. There is no default structural cost or count ceiling.

Budget reduction exists only as:

```text
BUDGETED_EXPERIMENTAL
```

That experimental mode uses priority-ordered fill with skip-ahead: an expensive route that does not fit cannot prevent later affordable routes from running. Its receipt explicitly records that coverage reduction was experimentally authorized and claims no optimality theorem.

`cost_units` remain `UNCALIBRATED_ORDERING_PROXY`; they are not measured tokens, money, latency, CPU, or scientific value.

## Liveness and automatic recovery

Every plan reports:

```text
CLEARED
RUNNABLE
STALLED_MODULE_UNAVAILABLE
STALLED_BUDGET
STALLED_DEPENDENCY_FRONTIER
STALLED_NO_EXECUTABLE_ROUTE
```

A stall is not treated as completion. Soul preserves the blocker frontier so FOIL, the host, or a later graph revision can automatically propose a missing capability, alternative route, or corrected frame.

`available_modules=None` means Soul may use the registered route set. An explicit empty tuple means the caller intentionally made no module available.

## Automatic batching boundary

Same-module obligations may share one routing envelope automatically, but each obligation remains a separately bound subrequest and receipt:

```text
context_sharing_status = AUTOMATIC_ISOLATED_SUBREQUESTS_REQUIRED
equivalence_status = PARTITION_REQUIRED_NOT_EMPIRICALLY_CLAIMED
```

An explicit non-empty `shared_context_group` permits actual shared context and remains:

```text
context_sharing_status = CALLER_OPT_IN_SHARED_CONTEXT
equivalence_status = NOT_ESTABLISHED
```

Transport batching therefore does not become a claim of behavioral independence or equivalent answers.

## Challenge composition

- `off` — challenge state ignored.
- `shadow` — counterfactual verdict does not block release, but unresolved load-bearing shadow challenges are automatically routed for investigation.
- `enforced` — load-bearing challenge severity is composed with the domain receipt.

Before composition, Soul checks current obligation-set and target-module binding, plus candidate/scope hashes when declared. A mismatched load-bearing challenge fails closed.

Shadow work is recorded as `INCLUDED_NOT_MEASURED`; it is not free. Promotion to enforced authority still requires preregistered evidence, an Evaluation receipt, and an explicit host decision.

## Automatic Process Assurance

When `runtime.automatic_assurance=true`, Soul adds one load-bearing Gauntlet obligation after at least one domain obligation exists. It depends on the current domain obligations and is run automatically by `automatic_release()`.

Gauntlet uses `AUTOMATIC_FULL` at release: every applicable canonical assurance operation runs, structural budgets cannot silently remove checks, and one issue does not stop the rest of the diagnostic sweep.

Gauntlet remains `ASSURANCE_ONLY`; a green assurance receipt never substitutes for the domain receipts Soul must integrate.

## Release consistency

`RuntimeStore` maintains a monotonic task evidence version for supported receipt and challenge mutations. Soul's release token binds:

```text
task revision id
frozen obligation-set hash
evidence version
receipt content hashes
challenge/resolution hashes
challenge mode
effective obligation verdicts
```

`release_task()` obtains a clear candidate token, then acquires the task and task-evidence locks, recomputes the token, and commits only if unchanged. Supported post-release evidence mutations are rejected.

This remains:

```text
COOPERATIVE_TASK_EVIDENCE_COMPARE_AND_SWAP
scope = RUNTIME_STORE_WRITERS_ONLY
```

Direct filesystem mutation or code bypassing the store/locks remains outside that guarantee. Cross-obligation semantic invariants must be explicit obligations or dependencies.

Current receipt precedence uses the monotonic store `seq`; wall-clock timestamps cannot outrank a newer sequenced receipt.

## Portable runtime

Before using a named tool, path, solver, API, or profile:

1. verify it exists in the active environment;
2. use it if present;
3. otherwise automatically route an explicitly valid alternative or report `UNAVAILABLE`;
4. never invent tool output or background execution.

Runtime helpers remain outside skill directories. See `docs/RUNTIME_SETUP.md`.

## Release semantics

Severity remains:

```text
ISSUE > UNAVAILABLE > UNKNOWN > CLEARED
```

- empty/no-load-bearing graph → `UNKNOWN`;
- invalid, incomplete against caller-declared required kinds, or drifted graph → `UNKNOWN`;
- missing receipt → `UNKNOWN`;
- unavailable required method → `UNAVAILABLE`;
- failing receipt or enforced challenge refutation/binding defect → `ISSUE`;
- all effective obligations, dependencies, and automatic assurance clear on the current unchanged revision → `CLEARED`.

The stored release result carries a control seal. Idempotent release validates that seal rather than trusting a bare flag.

## Efficiency and benchmark boundary

Mechanical validation establishes automatic control behavior only. It does not establish lower real tokens, lower latency, harmless batching, complete decomposition, or better task outcomes.

A prospective evaluation should compare `BASE`, `FULL_AUTOMATIC`, `BUDGETED_EXPERIMENTAL`, and an `ORACLE_SCHEDULE` analysis with held-out obligation families, route escapes, false blocks, graph-revision recovery, real model/tool cost, whole fix-to-green cost, and downstream task success.
