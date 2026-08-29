# Automatic Research Orchestrator — engineering specification

## Obligation and authority

Soul owns automatic framing, task-lineage control, declared obligation decomposition,
route scheduling, receipt/challenge integration, Process Assurance invocation, and
release control. It owns **control**, not domain truth.

```text
authority = CONTROL_ONLY
target_domain_clearance_authorized = false
```

Proof, discovery, synthesis, engineering, evaluation, assurance, preflight, review,
adaptation, and adversarial authority remain with their registered modules. External
writes and candidate adoption remain host actions.

## Corrected design principle

Safety controls must preserve automatic self-correction. They must not force Soul to
finish or bless an active task whose frame may be wrong.

The production system therefore uses:

```text
automatic task supersession with lineage
automatic graph revision through successor tasks
automatic routing of all dependency-ready obligations
automatic isolated transport batching
automatic full applicable Process Assurance
evidence-bound cooperative release CAS
```

Budget-reduced routing and reduced assurance coverage remain explicit experimental
modes. They are not production defaults.

## Runtime layering

```text
tools/soul_runtime.py       public compatibility and CLI
tools/soul_automatic.py     automatic policy and integration
tools/soul_vnext/           low-level graph/evidence/release mechanisms
tools/gauntlet_automatic.py automatic Process Assurance controller
tools/egrt_store.py         integrity, sequence, evidence version, locks
```

Soul does not import `foil_*`, execute Math Foundry, or read/mutate Mastermind state.
It may consume neutral challenge records through the common challenge interface.

## Automatic task supersession

`start_task()` checks the current active pointer. If an active unreleased task exists,
production mode does not reject the new frame and does not delete the old one.

It atomically creates a successor and records:

```text
predecessor.active = false
predecessor.status = SUPERSEDED
predecessor.soul_superseded_by = successor task id
predecessor.soul_supersession_reason_hash
successor.soul_supersedes = predecessor task id
successor.status = ACTIVE
active_task = successor task id
```

The raw reason is not persisted. An optional `strict_active_task=true` compatibility
setting restores the old refusal behavior, but the repository production configuration
uses automatic supersession.

A supersession cycle is invalid. Public planning/release APIs follow at most 64 lineage
links and fail closed on a cycle or excessive chain.

## Automatic graph revision

A frozen graph is an immutable historical revision, not a prison.

When `add_obligation()` discovers a new obligation after freeze and
`automatic_graph_revision=true`:

1. preserve the frozen predecessor unchanged;
2. create a successor task revision with the same goal digest and copied obligations;
3. append the new obligation;
4. remove stale freeze/release metadata from the successor;
5. validate and freeze the successor graph;
6. supersede the predecessor and move the active pointer;
7. emit `task.superseded` and `task.graph.revised` lineage events.

Receipts and challenges remain bound to their original task ID, so predecessor evidence
cannot silently clear the successor. The automatic system may reroute required work on
the new revision.

## Decomposition boundary

Soul stores a goal digest, not the raw goal, and therefore cannot prove semantic
completeness of any graph.

```text
decomposition_scope = AUTOMATIC_REVISIONED_DECLARED_GRAPH
decomposition_completeness_established = false
```

The host may declare `required_obligation_kinds[]`; Soul verifies those declarations.
Cross-obligation invariants must be represented as obligations or dependencies.

## Automatic Process Assurance obligation

When `runtime.automatic_assurance=true`, freeze ensures one load-bearing `ASSURANCE`
obligation after at least one load-bearing non-assurance obligation exists.

The assurance obligation:

- is owned by `gauntlet`;
- depends on the current load-bearing domain obligations;
- has `automatic_control=true`;
- cannot replace any domain receipt;
- is run automatically by `automatic_release()`.

An empty task does not gain an assurance-only path to green; without a domain
obligation it remains `UNKNOWN`.

## Routing policy

```text
RoutingPolicy
  mode = AUTOMATIC_ALL_READY | BUDGETED_EXPERIMENTAL
  max_cost_units = int | None
  max_obligations = int | None
  batch_same_module
  include_non_load_bearing
  available_modules[] | None
```

### Production mode

```text
AUTOMATIC_ALL_READY
```

Every unresolved, dependency-ready obligation whose required module is available is
selected. There is no default structural cost or operation ceiling.

### Experimental budget mode

```text
BUDGETED_EXPERIMENTAL
```

The caller must set at least one ceiling. Candidates retain deterministic priority
ordering, but an unaffordable candidate is deferred while later affordable candidates
may still run. This restores useful automatic throughput under an explicit experiment.

The selection certificate states:

```text
optimality_claimed = false
coverage_reduction_authorized = true
```

No monotonicity, minimum-cost, maximum-coverage, makespan, or approximation theorem is
claimed for the skip-ahead experimental schedule.

## Candidate order

```text
current-state severity descending
risk rank descending
information rank descending
cost units ascending
module ascending
obligation id ascending
```

`cost_units` remain:

```text
UNCALIBRATED_ORDERING_PROXY
```

They are not measured tokens, money, latency, CPU, or scientific value.

## Dependencies and liveness

Load-bearing obligations bring all transitive dependencies into the effective graph.
A child waits until its dependencies clear, but Soul reports the live frontier rather
than silently producing an empty plan.

```text
CLEARED
RUNNABLE
STALLED_MODULE_UNAVAILABLE
STALLED_BUDGET
STALLED_DEPENDENCY_FRONTIER
STALLED_NO_EXECUTABLE_ROUTE
```

A stalled task may be automatically reframed or revised; liveness state is diagnosis,
not permanent prohibition.

`available_modules=None` means the registered route set is available. An explicit
empty tuple means the caller made no route available.

## Automatic batching

Transport batching is automatic when enabled, but context sharing is not assumed.

Same-module obligations without `shared_context_group` may share one envelope marked:

```text
context_sharing_status = AUTOMATIC_ISOLATED_SUBREQUESTS_REQUIRED
equivalence_status = PARTITION_REQUIRED_NOT_EMPIRICALLY_CLAIMED
```

The executor must preserve separate subrequest contexts and separate receipts.

An explicit common `shared_context_group` permits shared context and is marked:

```text
context_sharing_status = CALLER_OPT_IN_SHARED_CONTEXT
equivalence_status = NOT_ESTABLISHED
```

A routing batch never combines factual verdicts.

## Challenge-aware automatic routing

Challenge modes retain their release semantics:

| Mode | Release effect |
|---|---|
| `off` | ignored |
| `shadow` | counterfactual result does not block |
| `enforced` | severity combines with domain receipt |

For **routing**, a live load-bearing shadow challenge is treated as unresolved work even
when the current domain receipt is green. Soul automatically sends it to the bound
claim-native module for investigation without granting the challenge release authority.

Challenge binding checks remain:

- current obligation-set hash;
- target module;
- optional candidate hash;
- optional scope hash.

Shadow work is `INCLUDED_NOT_MEASURED`. Promotion to enforced mode requires a
preregistered Evaluation receipt and explicit host adoption.

## Receipt precedence and snapshot integration

Soul scans integrity-valid task receipts once per decision and indexes only receipts
from the correct task and required module.

The monotonic store `seq` is authoritative. Wall-clock timestamps are diagnostic
fallback only and cannot outrank a newer sequenced receipt.

## Automatic release sequence

`automatic_release(task_id)`:

1. follows supersession lineage to the current task revision;
2. freezes/validates the current graph and automatic assurance obligation;
3. writes an automatic route plan;
4. records `release.attempted` bound to the route plan;
5. runs Gauntlet `AUTOMATIC_FULL` for the assurance obligation;
6. evaluates the low-level release gate;
7. commits only through the evidence-version compare-and-swap.

Gauntlet runs every applicable canonical operation, ignores structural budgets as a
reason to remove production release checks, and continues after the first issue.

## Cooperative release consistency

`RuntimeStore` maintains a monotonic `evidence_version` for supported task-scoped
receipt/challenge mutations. The release token binds:

```text
task revision id and content hash
frozen obligation-set hash
evidence version
receipt content hashes
challenge/resolution hashes
challenge mode
effective obligation verdicts
```

Soul obtains a clear token, acquires the task and task-evidence locks, recomputes the
token, and commits only if unchanged.

```text
COOPERATIVE_TASK_EVIDENCE_COMPARE_AND_SWAP
scope = RUNTIME_STORE_WRITERS_ONLY
```

Direct filesystem mutation or unsupported writers remain outside the guarantee.
Supported post-release evidence mutations are rejected. Idempotent release validates a
content-derived control seal.

## Public compatibility

Public functions:

```text
start_task()
add_obligation()
freeze_task()
plan_routes()
release_gate()
release_task()
automatic_release()
resolve_current_task_id()
```

Legacy strict refusal and budget reduction remain opt-in compatibility/experimental
policies rather than default behavior.

## Mechanical acceptance requirements

Tests must establish:

- automatic active-task supersession preserves lineage and activates the successor;
- planning/release through an old ID follows the current successor;
- post-freeze obligation discovery creates a successor graph revision;
- predecessor receipts cannot clear the successor;
- automatic assurance is injected only when domain work exists;
- production routing selects every dependency-ready obligation;
- budgeted experimental routing skips unaffordable work without blocking later work;
- automatic same-module batching requires isolated subrequest execution;
- explicit shared context remains `NOT_ESTABLISHED`;
- shadow challenges are routed but do not block release;
- liveness states and frontiers are explicit;
- current receipt uses monotonic sequence;
- automatic release runs Gauntlet and the release CAS;
- Soul writes no domain receipt and Gauntlet remains `ASSURANCE_ONLY`.

## Efficacy boundary

Mechanical tests establish automatic control behavior, not flawless performance.
Prospective matched evaluation should compare:

```text
BASE
FULL_AUTOMATIC
BUDGETED_EXPERIMENTAL
ORACLE_SCHEDULE
```

Pre-register final task success, held-out obligation families, wrong-route and escape
counts, graph-revision recovery, batching disagreement, real tokens/tool calls/latency/
money, whole fix-to-green cost, and downstream score at equal complete cost.

## Stacked validation rule

Soul is stacked on Gauntlet. Any Gauntlet base change invalidates Soul merge-tree
validation. Rebase onto the exact accepted Gauntlet head and rerun the complete suite
before merge or efficacy claims.
