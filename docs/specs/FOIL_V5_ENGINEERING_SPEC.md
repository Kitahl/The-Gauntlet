# FOIL v5 Engineering Specification

Status: **implementation contract plus unrun-gate specification**

This specification governs the FOIL v5 decidable-coverage candidate. It is
additive to existing FOIL contracts and does not change repository version,
public runtime ownership, or default invocation behavior.

## 1. Scope and invariants

FOIL/Mirror identifies a task-relevant residual and supplies or recommends the
minimum justified complement. It is not an autonomous general-agent runtime.

Hard invariants:

- FOIL has no Gauntlet or Mastermind runtime dependency.
- Profile/task coverage, answer residual evidence, and action authority are
  different typed surfaces.
- A0 is immutable throughout Gate 1. Changing model, prompt, skill, tool regime,
  compiler, bank, parser, applicability rule, threshold, or budget requires a
  new candidate binding.
- Unknown, undecidable, unavailable, malformed, stale, or mismatched data fails
  closed and preserves A0.
- No normal FOIL path has autonomous answer mutation, provider installation,
  provider trust promotion, host commit, or external execution authority.
- Public receipts use digests/locators and typed reasons, not raw task, answer,
  prompt, profile, or private reasoning content.

## 2. Current implementation map

| Concern | Live owner | State |
|---|---|---|
| Task/user coverage | tools/foil_requirements.py | Implemented; control-only routing |
| Signal/evidence boundary | tools/foil_signal_boundary.py | Implemented |
| Intervention and transfer | tools/foil_interventions.py; tools/foil_transfer.py | Implemented; descriptive/fail-closed |
| P1 planners | tools/foil_mechanisms.py | Implemented; default-off |
| Pre-solve monitor/hook | tools/foil_activation_monitor.py; tools/foil_hook.py | Implemented; event-driven/legacy default |
| Protocol and ledger | tools/foil_v5_protocol.py; tools/foil_v5_run_ledger.py | Implemented contracts; no real study receipt |
| Candidate state/token | tools/foil_candidate_state.py; tools/foil_authority_replay.py | Implemented; host-denied authority |
| Compiler | tools/egrt_claims.py; tools/foil_obligation_compiler.py | Implemented typed contract and strict structured-spec frontend |
| Closed verifier registry | tools/egrt_verifiers.py | Implemented deterministic registry |
| Coverage/scoring | tools/egrt_coverage.py; tools/foil_v5_metrics.py; tools/foil_v5_score.py | Implemented accounting |
| Certificate classes | tools/egrt_certificates.py | Implemented scoped evidence |
| Authority/admission | tools/foil_authority.py; tools/foil_residuals.py | Implemented shadow-only policy |
| Scanner/trigger | tools/foil_residual_scanner.py; tools/foil_postsolve_monitor.py | Implemented default-off/host invoked |
| External repair adapter | tools/foil_shadow_repair.py; tools/egrt_host_bridge.py | Implemented proposal/admission seam with one-use ACTIVE-token validation; no executor |
| Ditto resolver | tools/foil_ditto.py | Implemented closed READY registry and candidate-bound authorization; host-denied/no executor |
| Offline P0 reproducer | benchmarks/harness/foil_profile_ablation.py | Implemented protocol/receipt structural check; non-efficacy only |
| Adaptive compute | tools/foil_adaptive_route.py | Implemented; default-off, A0-preserving, shadow-only DIRECT/VERIFY/FULL recommendations |
| RouteVector history | tools/foil_shadow_route_ledger.py | Implemented; default-off observational ledger; no selection, learning, component credit, or execution |
| Future transformation admission | docs/FOIL_FORMALIZATION_FIDELITY.md | Specified only; NL-to-obligation generator remains absent |

## 3. Required flow

    frozen task + frozen solver configuration
      -> external answer generator emits A0
      -> immutable A0/task/spec/compiler/config bindings
      -> post-solve compiler emits typed obligations/claims
      -> closed deterministic verifier registry evaluates applicable predicates
      -> optional default-off EV controller recommends DIRECT/VERIFY/FULL in shadow
      -> coverage reports decidable, cleared, failed, unresolved, omitted mass
      -> scanner emits typed shadow evidence and ledger span
      -> authority policy returns stand-down/observe/flag/ask/escalation/repair-proposal
      -> external producer may create A1
      -> structural certificate + independent semantic certificate
      -> COMMITTABLE | REJECTED | UNKNOWN
      -> host/owner alone chooses whether to use A1

The compiler is post-solve and must not influence A0 generation. Gate 1 permits
only protocol-allowed local deterministic work. P1, P2, Ditto, model calls,
network, tools, repair, profile writes, and user-visible route changes are
forbidden unless a later separately frozen gate allows them.

## 4. Interface contracts

### 4.1 Compiler and coverage

ImmutableBindings bind A0, task, spec, compiler, and configuration digests.
PostSolveClaim and PostSolveObligation identify material scope without raw claim
persistence. Compilation returns exactly COMPILED, UNDECIDABLE, UNKNOWN, or
NOT_APPLICABLE. The executable frontend accepts only the versioned closed JSON
schema in `foil_obligation_compiler.py`; it does not infer obligations from
free-form prose. Only applicable deterministic obligations backed by the closed
verifier registry become scanner cases. Semantic, empirical, unknown, and
not-applicable obligations remain typed residuals and contribute no decidable
coverage.

Coverage uses positive integer weights and no double counting. Output retains
decidable, cleared, failed, unresolved, omitted, and undecidable mass. It must
report declared-universe coverage separately from adjudicated extraction
coverage/precision. A residual bound is only over the named versioned obligation
universe, never global semantic truth.

### 4.2 Certificates and authority

| Class | May establish | May not establish |
|---|---|---|
| STRUCTURAL_ONLY | patch/diff/schema/runnability facts | semantic correctness or commit |
| PREDICATE_SCOPED | named predicate in named environment | unenumerated semantics |
| REGRESSION_SCOPED | named passing obligations remain passing | complete semantic non-regression |
| INDEPENDENT_SEMANTIC | independently verified scoped semantic result | host commit by itself |
| UNKNOWN | no admission | pass, authority, or mutation |

Warrant/evidence class, applicability, authority ceiling, and admission state are
orthogonal. The repair producer, structural verifier, and semantic verifier must
be distinct where policy requires it. COMMITTABLE remains host decision input,
not execution permission.

### 4.3 Candidate release and invocation

Candidate release state is DORMANT, SHADOW, LOCKED, or ACTIVE. Invocation mode
is independently legacy, off, observe, or smart. A qualifying signed,
candidate-bound receipt is required for LOCKED/ACTIVE. Even then tokens are
non-executing and host-action-required.

The hook and post-solve monitor are event-driven only and have zero
model/tool/network/polling budget. SCAN merely asks a host to consider a
separately budgeted scanner invocation.

### 4.4 Adaptive compute and route history

The controller consumes frozen fixed-point EV estimates and compiler-created
host-declared verifier routes. Missing or non-positive value, insufficient budget,
unknown/mismatched bindings, and model-generated obligations retain A0. Its output
is CONTROL_ONLY, host-action-required, and never execution authority.

Optional posterior stand-down requires explicit thresholds, minimum evidence,
freshness, and exact model/contract/task-regime binding. Optional k=2 returns a
non-final probe request only; the controller cannot make the calls and agreement
is not correctness.

The RouteVector ledger is observational-only. Exact-route summaries never imply
causal superiority and never feed the controller. Component effects require a
separately frozen matched or randomized experiment.

The current compiler never transforms prose. Generated obligations remain
ineligible until the separate fidelity and extraction-recall gate is implemented
and passed.

## 5. Gate protocol

### Gate 0 — contract lock

1. Freeze source/worktree identity, API snapshots, and baseline tests.
2. Seal protocol bindings, partitions, metrics/bounds, forbidden effects,
   no-answer taxonomy, authority issuer/expiry, and candidate ID.
3. Ledger every registered effect. Missing observation remains unknown and blocks
   a cost claim.

### Gate 1A — infrastructure contract

Current code/tests cover typed outcomes, privacy/digest binding, forbidden-call
behavior, closed verifier dispatch, A0 binding, replay rejection, and host-denied
repair proposals. This is not detector-value evidence.

### Gate 1B — lock evaluation (not run)

Use development data only for compiler/bank selection. Freeze selected artifacts,
numeric gates, and scoring code. Evaluate once on a disjoint lock partition
without exposing gold, labels, or bank membership. Report per-domain compiler
coverage/precision, verifier validity, residual recall, false activation,
conditional incremental value, declared residual, typed no-answer outcomes, and
sealed costs.

### Gate 1C — prospective confirmation (not run)

Keep Gate 1B artifacts fixed. Use a source/time-separated natural-prevalence
stream with preregistered inclusion, stopping, adjudication, sampled
non-activation, clustering, and uncertainty rules. Promotion requires every
domain/bound to pass, exact A0 equivalence, zero forbidden calls, complete cost,
and successful negative/fault controls. Failure yields GATE1_NOT_PROMOTED.

### Gate 2 — repair/authority (not run)

Measure action-authorized R_flag, alpha_flag, R_act, alpha_act, u_act, and d_act
on the same frozen policy/population. Include false-positive, wrong-location,
duplicate/repeated action, verifier/certificate failure, and prospective
right-to-wrong controls. No no-write rule or reference-answer proxy estimates
damage.

### Gate 3 — Ditto/Mirror execution (not run)

Use only READY providers for USE. METHOD_ONLY must be reviewed/versioned and run
through an already READY capability; SUGGEST is display-only. Compare benefit and
cost with cheaper Gate 2 repair. Discovery, auto-install, trust promotion, and
silent fallback remain prohibited.

### Later gates (not run)

- RQ-26 complement selection: raw vs checklist vs FOIL vs oracle.
- Scoped model/effort/domain/task/tool/date calibration and replicated model-policy
  factorial; no global tier ontology.
- Evidence-conditioned history with redaction, provenance, expiry, drift, and
  rollback.

## 6. Non-claims

An implementation contract is acceptable when focused tests and entrypoint checks
pass. It is never behavioral promotion. Historical profile P0 remains
P0_NOT_PROMOTED: profile efficacy, smart-monitor benefit, P1/P2 activation, and
human complementarity are unresolved. Profile P0 and residual Gate 1 are
separate hypotheses and cannot promote each other.
