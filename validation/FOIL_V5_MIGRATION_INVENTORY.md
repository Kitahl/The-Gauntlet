# FOIL v5 Migration Inventory

Status: **live branch reconciliation, not a promotion receipt**

Prepared against codex/foil-v5-decidable-coverage at
4f088d688fa9e25b4608f44000a5d9812efa45f9. Classifications say how a seam may
be used; they do not imply behavioral efficacy.

| Area | Canonical owner(s) | Class | Required treatment |
|---|---|---|---|
| User/task requirements and coverage | tools/foil_requirements.py; tools/foil_evidence.py; tools/foil_profile.py | REUSE | Preserve TaskCapabilityRequirement; UNKNOWN is not gap; no provider-schema overload. |
| Runtime profile routing | tools/foil_policy.py | EXTEND | Keep current-task evidence visibly distinct and all profile routing CONTROL_ONLY. |
| Intervention ledger | tools/foil_interventions.py | EXTEND | Retain task-result/ownership semantics; effects are additive and legacy-readable. |
| Signal/evidence admission | tools/foil_signal_boundary.py; estimator | REUSE | Control signals cannot satisfy facts or promote competence. |
| Run cost receipt | tools/foil_costs.py | EXTEND | Preserve None for unavailable data and exact matched-cost rules; no parallel cost truth. |
| Evaluation run ledger | tools/foil_v5_run_ledger.py | NEW | Seal every registered effect at harness boundary; incomplete data cannot support cheap claims. |
| Frozen protocol | tools/foil_v5_protocol.py; validation/foil_v5_protocol.example.json | NEW | Bind A0/prompt/model/skill/tool/scanner/bank/parser/applicability, partitions, gates, authority. Example is not a receipt. |
| Candidate release/token | tools/foil_candidate_state.py; tools/foil_authority_replay.py | NEW | DORMANT -> SHADOW -> LOCKED -> ACTIVE is separate from hook mode; mismatch/replay/expiry fails closed. |
| Post-solve compiler | tools/egrt_claims.py; tools/foil_obligation_compiler.py; validation/foil_v5_task_spec.example.json | NEW | Compile only a strict closed structured specification after A0; explicit non-pass outcomes; no prose inference or Gate 1 model/tool/network effects. |
| Closed verifier registry | tools/egrt_verifiers.py | NEW | Code-owned IDs and typed results; no arbitrary implementation strings or dynamic external dispatch. |
| Coverage/scoring | tools/egrt_coverage.py; tools/foil_v5_metrics.py; tools/foil_v5_score.py | NEW | Keep declared coverage, adjudicated compiler coverage/precision, failure, and residual separate. |
| Residual/provider needs | tools/foil_v5_metrics.py | NEW | Use ResidualDiagnosticNeed and DiagnosticCapabilityRequirement, never TaskCapabilityRequirement. |
| Certificate classes | tools/egrt_certificates.py | NEW | Scoped structural/predicate/regression/semantic/unknown evidence; class is not authority. |
| Authority/admission | tools/foil_authority.py; tools/foil_residuals.py | NEW | Separate surface, warrant, applicability, ceiling, calibration, admission; unknown preserves A0. |
| Scanner | tools/foil_residual_scanner.py | NEW | Default-off deterministic shadow evidence, never person-gap update/global truth label. |
| Post-solve trigger | tools/foil_postsolve_monitor.py | NEW | Event-driven, opt-in, zero-token; SCAN delegates rather than hides work. |
| Pre-solve monitor/hook | tools/foil_activation_monitor.py; tools/foil_hook.py | ADAPT | Legacy default; off/observe/smart non-enforcing, no polling/model/network. |
| P1 planners | tools/foil_mechanisms.py | REUSE | Default-off/ablatable; not Gate 1 independent sensors. |
| P2 transfer/refinement | tools/foil_transfer.py | REUSE | Preserve user-owned changed-context gate; not Ditto or answer repair. |
| External repair/host bridge | tools/foil_shadow_repair.py; tools/egrt_host_bridge.py | NEW | Accept external artifacts only; require COMMITTABLE admission plus an issuer-verified ACTIVE token and one-use replay consumption; still emit host-denied requests and never commit A0. |
| Provider resolver | tools/foil_ditto.py | NEW | Closed READY capability/recipe registry; USE/METHOD_ONLY require a current issuer-verified candidate-bound ACTIVE token; resolution never executes and always requires host action. |
| Typed runtime bridge | tools/foil_runtime_bridge.py | REUSE | Metadata/hash scope only; no factual warrant, candidate state, or execution authority. |
| Profile/history learning | tools/foil_transfer.py; profile ledger | DEFERRED | Wait for verified joint outcomes plus privacy/drift/rollback evidence. |
| Ditto behavioral execution/effectiveness | external Gate 3 harness | DEFERRED | Resolver software exists, but bounded provider/method comparison, provenance/budgets, execution controls, and marginal benefit/cost evidence require Gate 2/3. |
| Model ladder/prompt policy | future calibration experiment | DEFERRED | Requires scoped calibration and replicated factorial study. |
| RQ-26 adaptive complement | future benchmark protocol | DEFERRED | Requires raw/checklist/FOIL/oracle selection experiment. |
| Gauntlet/Mastermind | external systems | REUSE AS EXTERNAL REVIEW ONLY | No FOIL runtime import, shared control path, or authority transfer. |

## Required migration order

1. Preserve all REUSE contracts and legacy serializations.
2. Complete/validate NEW v5 seams in shadow mode.
3. Apply EXTEND/ADAPT only with compatibility, entrypoint, and fault-path tests.
4. Freeze a protocol and run Gate 1B/1C before answer-changing behavior.
5. Keep DEFERRED work out of normal execution until its preceding gate passes.

## Explicit non-migration rules

- Do not overwrite TaskCapabilityRequirement with a provider requirement.
- Do not create a second cost ledger or user profile system.
- Do not use profile evidence to classify a factual answer defect.
- Do not treat scanner FAIL, certificate PASS, or ACTIVE state as autonomous
  execution/final admission.
- Do not merge Gauntlet/Mastermind runtime logic into FOIL.
- Do not use structural tests or old P0 non-promotion as evidence that another
  candidate has behaviorally promoted.

## Gate ledger

| Gate | Honest state | Missing evidence |
|---|---|---|
| Historical profile P0 | P0_NOT_PROMOTED; offline reproducer implemented | New same-item matched three-arm study with valid profile evidence and preregistered quality/harm/cost analysis. The offline structural fixture is not such a study. |
| Gate 1A contracts | Implemented/tested locally | Does not replace behavioral Gate 1B/1C. |
| Gate 1B lock | Not run | Frozen bank/config/thresholds, blind lock evaluation, sealed receipts, per-domain metrics. |
| Gate 1C prospective | Not run | Untouched natural-prevalence stream, sampled/blind adjudication, uncertainty bounds, complete ledger. |
| Gate 2 repair | Not run | Authorized rescue/damage study, independent semantic verification, prospective harm bound. |
| Gate 3 Ditto | Resolver implemented; behavioral gate not run | Bounded method/provider comparison, marginal benefit/cost, and external host execution controls. |
| RQ-26 | Not run | Adaptive complement selection versus raw, checklist, and oracle. |
| Model ladder | Not run | Scoped calibration and replicated policy factorial. |
| History | Not run | Verified joint outcomes plus privacy, drift, expiry, rollback design. |
