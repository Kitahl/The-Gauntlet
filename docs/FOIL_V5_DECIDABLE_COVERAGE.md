# FOIL v5: Decidable Coverage

Status: **implemented software contracts; behavioral efficacy unmeasured**
Branch inspected: codex/foil-v5-decidable-coverage at 4f088d688fa9e25b4608f44000a5d9812efa45f9.

FOIL v5 does not label a free-form answer “verified.” After an immutable base
answer (A0) is sealed, it compiles a declared material-obligation universe,
reports which obligations are decidable, and exposes the semantic residual that
remains outside mechanically cleared scope.

This document describes current local contracts. It is not an executed
natural-prevalence experiment, a promoted scanner, a safe-repair result, or a
personalized task-benefit result.

## System boundary

FOIL/Mirror is the adaptation and residual-complement component. It may select
or recommend a bounded complement, emit a shadow observation, ask/abstain, or
recommend escalation. It does not own factual truth, model execution, provider
installation/trust, answer commit, Gauntlet state, or Mastermind control.

Gauntlet is an external process/audit runtime. Mastermind is an external
development-review discipline. FOIL runtime modules must not import either as a
control dependency. The new monitor/hook tests and shadow-authority contracts
preserve that separation.

Three typed evidence surfaces remain separate:

1. User/task capability coverage — what a task requires and whether current or
   profile evidence supports a user capability.
2. Answer residual evidence — whether A0 has a scoped post-solve obligation that
   is decidable, unresolved, failed, or not applicable.
3. Action authority — what FOIL may suggest from evidence. The host owns
   execution and final answer selection.

An answer defect does not prove a user gap. A user profile does not affect
factual verdicts, evidence warrant, certificate class, or action authority.

## Implemented contracts

### P0 capability coverage and control-only routing

[foil_requirements.py](../tools/foil_requirements.py) supplies immutable
TaskCapabilityRequirement, five-state CoverageState, deterministic merging, and
route_requirements. Its rules are:

- UNKNOWN is not a gap.
- Current compatible task evidence outranks stale profile evidence.
- An unmapped capability does not guess a complement.
- Task relevance precedes profile routing.
- At most one complement is selected and the route records current-task versus
  profile basis.

[foil_signal_boundary.py](../tools/foil_signal_boundary.py) makes router,
monitor, and profile signals CONTROL_ONLY. Such signals may select what to
inspect; they cannot satisfy a factual obligation or promote user competence.
EVIDENCE_CANDIDATE still requires ordinary evidence admission.

[foil_interventions.py](../tools/foil_interventions.py) keeps task result
separate from additive useful, necessary, redundant, harmful, takeover,
insufficient, missed-gap, independent-after-assistance, and later-transfer
effects. These are descriptive ledger observations, not causal estimates.

### Compiler and decidable coverage

[egrt_claims.py](../tools/egrt_claims.py) binds each post-solve claim to A0,
task, specification, compiler, and configuration digests. Compilation emits one
of COMPILED, UNDECIDABLE, UNKNOWN, or NOT_APPLICABLE; a non-decidable claim can
never become a green result.

[foil_obligation_compiler.py](../tools/foil_obligation_compiler.py) is the
deterministic frontend. It accepts only a strict versioned structured schema,
binds exact verifier inputs and versions, rejects unknown fields and overlapping
weights, and creates scanner cases only for applicable deterministic obligations
in the closed registry. It does not infer claims from prose.

[egrt_coverage.py](../tools/egrt_coverage.py),
[foil_v5_metrics.py](../tools/foil_v5_metrics.py), and
[foil_v5_score.py](../tools/foil_v5_score.py) implement coverage accounting.
The primary declared-universe metric is:

    decidable coverage = decidable material weight / material weight

It remains separate from mechanically cleared coverage, known failed weight, and
unresolved residual weight. An unresolved residual includes unknown, omitted,
and undecidable material obligations. A high declared coverage score is not a
global correctness proof.

The score layer distinguishes declared-universe coverage, adjudicated compiler
coverage/precision, and action-conditioned R_flag, alpha_flag, R_act, alpha_act,
u_act, and d_act. Wide-bank flag recall cannot be credited as repair benefit
unless that path was itself action-authorized.

### Certificates, authority, and repair boundary

[egrt_certificates.py](../tools/egrt_certificates.py) defines STRUCTURAL_ONLY,
PREDICATE_SCOPED, REGRESSION_SCOPED, INDEPENDENT_SEMANTIC, and UNKNOWN
certificate classes. Certificate class is not action authority.

[foil_authority.py](../tools/foil_authority.py) separates evidence surface,
applicability, sensor outcome, authority ceiling, and admission state. Unknown
states preserve A0. A structural certificate does not establish semantic
admission; an independently represented semantic verification is required for a
COMMITTABLE candidate.

[foil_shadow_repair.py](../tools/foil_shadow_repair.py) is host-denied. It
accepts an externally produced candidate, records certificate digests, preserves
A0, and sets execution_authorized to false. Even COMMITTABLE requires an
external host/owner decision.

### Candidate and invocation state

[foil_candidate_state.py](../tools/foil_candidate_state.py) separates research
release state from hook mode:

    DORMANT -> SHADOW -> LOCKED -> ACTIVE

Invalid, stale, mismatched, incomplete, or failed evidence fails closed and
cannot advance a candidate from DORMANT, SHADOW, or LOCKED. Gate receipts require
exact frozen bindings, solve equivalence, zero forbidden calls, required-domain
success, and complete cost evidence. ACTIVE is still not execution authority:
its tokens are host-action-required.

The hook instead uses FOIL_AUTO_MODE = legacy | off | observe | smart. Legacy
remains default. The event-driven activation monitor has no polling, model, tool,
or network path; observe emits no context/writes; smart caps active context at
1,200 characters. The post-solve monitor is also opt-in and zero-token. Its SCAN
decision only invites a host to invoke a separately budgeted scanner.

### Existing P1/P2 foundation

[foil_mechanisms.py](../tools/foil_mechanisms.py) contains independently
ablatable, default-off P1 planners for claim-native verifier selection, bounded
acquisition, 2–4 challengers, and one repair plus recheck. They are not active
Gate 1 sensors and do not close claims merely from an observation.

[foil_transfer.py](../tools/foil_transfer.py) keeps P2 transfer and one-step
presentation refinement default-off and fail-closed. Transfer requires verified,
independent, user-owned changed-context evidence; harmful, takeover, and
redundant effects block selection. It is not external Ditto method transfer.

### Gated Ditto resolver and host bridge

[foil_ditto.py](../tools/foil_ditto.py) implements a closed READY
capability/recipe registry. USE and METHOD_ONLY resolution require an exact,
current, issuer-verified ACTIVE token bound to the same candidate. Every result
remains non-executing and host-action-required. The resolver does not discover,
install, trust-promote, or call providers.

[egrt_host_bridge.py](../tools/egrt_host_bridge.py) accepts a repair request only
after COMMITTABLE admission plus the same candidate-bound ACTIVE-token checks,
then consumes the authority token through a one-use replay guard. A valid bridge
request is still not execution permission and never mutates A0.

The provider-neutral offline P0 reproducer in
[foil_profile_ablation.py](../benchmarks/harness/foil_profile_ablation.py)
validates the sealed three-arm routing/receipt structure. It has no provider,
network, model, subprocess, or efficacy path and always reports
P0_NOT_PROMOTED.

## Evidence status

The repository-wide contract suite ran locally on 2026-08-24: **661 tests
passed**.
That demonstrates the named in-process contracts behaved as tested. It is not
evidence for natural-error recall, repair safety, model ladders,
personalization, or human learning.

The earlier profile P0 result remains P0_NOT_PROMOTED. It is an audited
historical receipt, not re-run evidence on this branch. It keeps profile
efficacy unresolved and does not authorize monitor/P1/P2 promotion. It also
does not forbid a separate offline, default-off residual-scanner candidate.

## Research gates not yet run

1. Gate 1B lock evaluation: use development data only to select compiler,
   parser, applicability, and one diagnostic bank; freeze hashes and numeric
   bounds; evaluate once on a disjoint blind lock set.
2. Gate 1C prospective confirmation: evaluate the locked candidate on a
   time/source-separated natural-prevalence stream. Require per-domain bounds
   for compiler coverage/precision, verifier validity, residual recall, false
   activation, incremental value, no forbidden calls, and complete cost.
3. Repair gate: measure action-authorized u_act and d_act on the same frozen
   routed population, including wrong-location, false-positive, repeated firing,
   certificate-failure, and prospective-harm controls.
4. Ditto gate: after repair safety, compare closed READY-provider or reviewed
   METHOD_ONLY execution with cheaper repair. No install, trust promotion, or
   silent fallback is authorized.
5. RQ-26: compare raw baseline, fixed checklist, FOIL-selected complement, and
   oracle complement for gap classification, selector regret, stand-down quality,
   benefit, unnecessary intervention, cost, and boundary violations.
6. Model ladder: run scoped, replicated prompt-policy × answer-policy studies;
   it is not a global runtime ontology.
7. History: add it only after verified joint-route outcomes plus redaction,
   provenance, expiry, drift, and rollback rules exist.

Until those gates pass, FOIL may observe residual evidence but may not
autonomously act, mutate a returned answer, claim safe repair, claim end-to-end
complement benefit, or represent a shadow result as promotion.
