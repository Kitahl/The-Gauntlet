# Process Assurance Framework / Gauntlet — engineering specification

## Obligation and authority

Gauntlet monitors represented research-process and framing hazards that ordinary candidate verification may miss. It owns only `ASSURANCE` obligations.

A Gauntlet receipt cannot clear `PROOF`, `DISCOVERY`, `SYNTHESIS`, `ENGINEERING`, `EVALUATION`, `PREFLIGHT`, `REVIEW`, `ADAPTATION`, or `ADVERSARY`. It does not decide whether a theorem is true, a source is authoritative, software is correct, an experiment is causal, or a candidate should be adopted.

The runtime records:

```text
authority = ASSURANCE_ONLY
target_domain_clearance_authorized = false
```

When a bound task exists, attempting to run Gauntlet against a non-`ASSURANCE` obligation raises `GauntletAuthorityError`.

## Design sources and non-merger boundary

This upgrade adopts general mechanics without merging external control planes:

- **FOIL:** represent task-local residual hazards, choose minimum discriminators, stand down when no relevant trigger exists, and keep unsupported tool output non-authoritative.
- **Math Foundry:** distinguish explicit routes from AUTO scheduling, freeze availability and complete cost, and compare the selected schedule with a declared full-registry baseline.
- **Mastermind:** freeze the observed state before intervention, prefer general mechanisms over benchmark rules, issue coverage/minimality certificates, require negative controls, and prohibit self-promotion.
- **Tools:** run typed deterministic checks before semantic tools, read the task ledger once, reuse the frozen snapshot, and stop when a release-blocking issue is already sufficient.

Gauntlet imports no `foil_*` module, does not execute Math Foundry, and cannot read or mutate Mastermind control-plane state. Any future external controller may propose typed evidence or a discriminator, but Gauntlet retains its own assurance authority and fail-closed semantics.

## Existing boundary preserved

The public runtime remains split into:

- `tools/gauntlet_runtime.py` — typed operation registry, minimal assurance planning, task-scoped monitoring, and receipts;
- `tools/gauntlet_boundary.py` — narrow legacy free-text `frame`/`costume` candidate detection and optional semantic precision judge;
- `tools/gauntlet_monitor.py` — registered authority snapshots and drift events;
- existing hook/configuration/ledger helpers.

Free-text semantic judgment remains optional and independently configured. Absence is `UNAVAILABLE`; it is never silently converted into a pass.

## Operation registry

| Operation | Mode | Hazard class | Cost units | Typed discriminator | Boundary |
|---|---:|---|---:|---|---|
| `frame` | automatic | repeated failure frame | 1 | compare three recent failure signatures | observes only represented signatures |
| `audit` | automatic | premature release | 1 | inspect latest valid task-scoped receipts | receipt validity is not semantic truth |
| `costume` | assisted | novelty costume | 2 | require actual cleared source-assessed Space receipt | no global novelty proof |
| `derive` | automatic | inherited value | 1 | require current task-scoped Mind derivation | inherited flag must be explicit |
| `self` | automatic | self-verification | 1 | compare producer/verifier identity and provenance | missing provenance is unresolved |
| `redirect` | automatic | stagnant work | 1 | compare recent blocker/progress hashes | hashes must be supplied consistently |
| `refresh` | automatic | stale authority | 1 | inspect latest snapshot/change event | only registered authorities |
| `boundary` | automatic | unbound handoff | 1 | match handoff ID and contract hash | only typed handoffs |
| `explain` | assisted | explanation drift | 2 | compare claim IDs and non-empty hashes | free-text entailment remains assisted |
| `oob` | automatic | uncovered failure class | 1 | require valid artifact/scope-bound named probe | never proves exhaustive coverage |

The registry's total is a **derived planning baseline**, not a measured token or compute baseline.

## Frozen assurance policy

```text
AssurancePolicy
  mode                 # RELEASE_GATE | DIAGNOSTIC
  max_cost_units
  max_operations
  stop_on_issue
```

The caller supplies the budget. Product code does not hard-code a benchmark token ceiling.

`RELEASE_GATE` allows sufficiency stopping after the first `ISSUE`. `DIAGNOSTIC` executes the complete selected schedule so multiple represented defects can be reported.

## Hazard candidates

A `HazardCandidate` is created only when its typed trigger is present. It contains:

- operation and hazard class;
- trigger event IDs;
- stable reason code;
- risk and information ranks;
- deterministic cost units;
- required capability, when relevant.

Current trigger rules are deliberately narrow:

- three recent failures → `frame`;
- release attempt → `audit`, `refresh`, `oob`;
- novelty claim → `costume`;
- inherited claim → `derive`;
- evidence attachment → `self`;
- three recent attempts → `redirect`;
- handoff → `boundary`;
- explanation claim → `explain`;
- authority change without a release attempt → `refresh`.

No trigger means no operation. Difficulty alone is not a trigger.

## Deterministic AUTO schedule

Candidates are ordered by:

```text
risk descending
information rank descending
cost units ascending
operation name ascending
```

The planner selects the longest prefix that fits both caller-frozen budgets. This is an ordinal rule; it does not fabricate rescue probabilities or token prices from model confidence.

The plan records:

```text
AssurancePlan
  input_hash
  candidates
  selected_operations
  excluded_operations + reason
  planned_cost_units
  registry_cost_units
  coverage_certificate_hash
  minimality_certificate_hash
  plan_hash
```

### Coverage certificate

The coverage certificate binds:

- all triggered hazard classes;
- selected hazard classes;
- triggered classes excluded by budget.

An excluded triggered hazard prevents aggregate `CLEARED`.

### Minimality certificate

The minimality certificate binds the frozen candidate order, selected prefix, exclusions, policy, and deterministic selection rule. It proves reproducibility of this bounded scheduler; it does not prove global optimality or behavioral efficacy.

## Single-snapshot execution

One assurance run:

1. resolves the bound task and confirms `ASSURANCE` authority;
2. loads the integrity-valid task once;
3. loads valid task-scoped events once;
4. loads valid task-scoped receipts once in deterministic order;
5. freezes the input hash and plan;
6. evaluates selected operations against that same snapshot;
7. applies release-gate sufficiency stopping when configured;
8. emits one compact aggregate receipt.

This prevents cross-task receipt leakage and avoids rescanning the full ledger once per operation.

The aggregate receipt reports counts and derived cost units with:

```text
cost_unit_status = DERIVED_NOT_TOKENS
efficacy_status = NOT_ESTABLISHED
semantic_tool_calls = 0   # for the typed planner path
```

No token, money, latency, or benchmark-score reduction is claimed without measured matched evaluation.

## Hardened monitor semantics

### Audit

For bound tasks, `audit` uses the latest integrity-valid, task-scoped receipt from the obligation's required module. Historical events alone cannot clear the audit. Gauntlet's own assurance obligation is excluded to avoid circularity.

### Derive

A same-ID Mind receipt from another task cannot satisfy an inherited claim.

### Self

Exact producer/verifier identity is `ISSUE`. Shared provenance is `UNKNOWN`. Missing identity or provenance is also `UNKNOWN`; absence cannot become an independence claim.

### Refresh

The latest registered authority event controls the result. A fresh snapshot can supersede an earlier `authority.changed`; historical drift does not poison the task forever.

### Boundary

A handoff requires a non-empty ID, a matching `contract.bound`, and a non-empty content hash. An explicitly expected contract hash must match.

### OOB

A named failure class is insufficient. A probe also requires valid measured status, verifier identity, artifact hash, and scope hash. The result covers only that named class and binding.

### Costume

A synthetic `receipt.written` event cannot establish prior-art coverage. The underlying integrity-valid Space receipt must exist, be task-scoped, be `CLEARED`, and have action `source-assessment`.

### Explain

Claim IDs alone do not establish agreement. Both explanation and artifact require non-empty hashes; missing counterparts are `UNKNOWN`, mismatches are `ISSUE`.

## Aggregate verdict

The aggregate ordering is:

```text
ISSUE
UNKNOWN if any triggered hazard was excluded by budget
UNAVAILABLE
UNKNOWN
CLEARED
```

`CLEARED` requires at least one executed triggered operation, all executed operations cleared, and no triggered operation excluded by budget. No triggered hazards yields `UNKNOWN`, not a ceremonial green result.

## Mechanical acceptance tests

`tests/test_gauntlet_planner.py` covers:

- only triggered operations are selected;
- deterministic plan and certificate hashes;
- release-gate stopping after the earliest sufficient issue;
- diagnostic mode executes the complete selected schedule;
- budget exclusion forces `UNKNOWN`;
- cross-task receipts cannot clear audit or derivation;
- non-assurance authority is rejected;
- one aggregate receipt records derived-not-token metrics;
- missing provenance is not independence;
- fresh authority snapshots supersede old drift;
- handoffs require content-bound contracts;
- OOB probes require status and artifact/scope binding;
- explanations require hash-bound counterparts;
- novelty claims require an actual Space receipt rather than a receipt event.

Existing tests continue to cover the ten-operation registry, repeated failure detection, redirect behavior, missing semantic judges, privacy, hook recursion, portability, and release gates.

## Benchmark and usefulness evaluation

Implementation correctness is not an efficacy result. A future matched benchmark should freeze the same task traces and compare:

```text
BASE: no Gauntlet
FULL: all ten operations / legacy broad assurance
AUTO: minimal frozen assurance planner
ORACLE_SCHEDULE: cheapest operation schedule that detects each seeded hazard
```

Primary measurements:

- validated hazard recall and false-positive rate;
- release-blocking defect recall;
- cost per validated finding;
- measured model/tool tokens, latency, calls, and money;
- unnecessary blocks and unresolved-rate calibration;
- downstream benchmark score under the same total budget.

The primary incremental estimand for the planner is `AUTO - FULL` for efficiency at preserved hazard recall, and `AUTO - BASE` for net task value. Null and negative outcomes must be retained.

## Next upgrade boundary

The next Gem scheduled for analysis is **Soul / Research Orchestrator**. This Gauntlet change does not modify Soul code, routing, task state, release semantics, or authority.
