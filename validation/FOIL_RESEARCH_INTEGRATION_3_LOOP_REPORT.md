# FOIL — Research Integration and Three Mastermind Loops

Date: 2026-08-21

## Executive verdict

The two user-supplied research audits materially changed FOIL. The original concept survives, but the promoted skill is no longer a personalized assistant that simply labels weaknesses. It is now specified as an evidence-governed adaptive system that:

- maintains competing hypotheses about competence and transient state;
- conditions learner evidence on assistance, item, context, and retention;
- treats ownership as behavioral proof obligations;
- separates answer reliability from pedagogical friction;
- routes tools/skills through hard obligations plus a provisional marginal-value layer;
- leaves Council off unless it can add independent information or verification;
- governs claims through an atomic dependency graph and claim-native verification; and
- judges scientific success primarily by delayed independent transfer after relevant AI assistance is removed.

The integration passed specification and package checks. It has **not** yet passed behavioral or learning-effect validation.

## Source boundary

Inputs:

- `research_inputs/FOIL_RESEARCH_AUDIT_REPORT.md`;
- `research_inputs/FOIL_EVIDENCE_BASED_ARCHITECTURE.md`;
- frozen pre-integration FOIL baseline;
- Mastermind v4.4.11 used only as `PRE_REVIEW_ONLY` process discipline.

The audits were treated as evidence-bearing inputs, not unquestioned authority. Load-bearing source records were independently spot-checked against publisher or primary records and recorded in `FOIL_RESEARCH_BASIS.md`. The audit covered ACM Digital Library, Wiley, ACL Anthology, current arXiv records, and Science. Each basis entry separates:

1. what the source supports;
2. what it does **not** establish; and
3. the additional FOIL-specific architecture inference.

A paper adjacent to a FOIL mechanism is not evidence that the FOIL mechanism itself works.

## Frozen versions

| Version | Purpose | Bytes | Lines | SHA-256 |
|---|---|---:|---:|---|
| `v0` | pre-research baseline | 37,279 | 808 | `913e20a243132dd4316c3e7c39f4c22fe179073846e46eedd4ad451a3004489f` |
| `v1` | learner inference / ownership | 44,969 | 907 | `1fef74c1a08e6f6b45f3b066ee94cc1f2bc4a48eac1c3d0a4c1c16f4d0fb03da` |
| `v2` | routing / Council / stopping | 48,565 | 962 | `89f73804b2c3da590304e004deabf0ec93df0dc69f76a28f4dd41c11817103c6` |
| `v3` | evidence graph / verification / validation program | 55,903 | 1,072 | `4972dc14ee6d81dd88e8ff276af6853e173226f4e35994f0eec561775e07a8ac` |

Active `SKILL.md` is byte-identical to `v3`.

# LOOP 1 — Learner inference, ownership, and assistance

## Earliest causal defect

The previous Gap-Diagnosis Gate blocked a single bad answer from becoming a permanent label, but it still lacked a longitudinal assistance-conditioned state, explicit competing causes, retention decay, falsifiable ownership transitions, and an evidence-responsive scaffolding policy.

## Mechanisms promoted

1. **Learner-state hypothesis model:** `S_t=(K_t,C_t,A_t,R_t)` for competence, transient context, assistance, and retention.
2. **Competing explanations:** knowledge gap, retrieval failure, ambiguity, temporary state, communication effect, missing substrate, execution slip, and other task-specific causes.
3. **Active diagnostic probes:** select the smallest probe that discriminates the leading explanations.
4. **Prospective calibration:** freeze numeric learner predictions before the probe; score later with Brier score/log loss when numeric probabilities are actually emitted.
5. **Behavioral ownership:** `SEEN / ASSISTED / OWNED / TRANSFERRED / DEFENSIBLE` now require progressively stronger independent demonstrations.
6. **Retention separation:** highest historical level is distinct from current retention confidence.
7. **Assistance-responsive fading:** worked solution → faded completion → independent problem according to observed support dependence, with hysteresis.
8. **Dual controls:** verification intensity is separate from pedagogical friction.

## Mastermind admission

| Gate | Result | Reason |
|---|---|---|
| A — Causal adequacy | `PASS-SPEC` | Closes the observed overdiagnosis and assistance-credit defects. |
| B — Identifier independence | `PASS` | Uses general state/evidence variables, not project IDs. |
| C — Representation transformation | `PASS-SPEC` | Applies to proof, statistics, code, systems, and research tasks. |
| D — Negative control | `PASS-SPEC` | Tired, ambiguous, terse, or heavily assisted responses do not create stable gaps/mastery. |
| E — Cross-domain transfer | `PASS-SPEC` | Observation-versus-cause distinction is domain-independent. |
| F — Existing-mechanism compression | `PASS` | Extends the prior Gap-Diagnosis and Ownership laws. |
| G — Ablation | `PASS-STRUCTURAL` | Removing assistance/context/retention conditioning makes the loop-1 checks fail. |
| H — Regression | `PASS` | Authority, claim law, contention duel, and delivery behavior remain. |

# LOOP 2 — Routing, Council, and stopping

## Earliest causal defect

“Minimum sufficient combination” was still mainly a fixed table. It lacked a non-optional proof-obligation layer, an explicit decision rule for optional tools/skills, a release condition, and a strong negative presumption against correlated Council deliberation.

## Mechanisms promoted

1. **Two-layer router:** mandatory claim-native obligations first; discretionary routing second.
2. **No optimization-away:** provenance, current-source, safety, authority, and verification obligations cannot be skipped because doing so is cheaper.
3. **Ordinal marginal-value decision:** estimate task, learning, and epistemic gain against money, compute, latency, and human burden without inventing precise calibration.
4. **Release rule:** stop only after mandatory obligations are handled and no optional action has sufficient expected marginal value.
5. **Direct-answer negative control:** low-stakes, stable, reversible tasks may remain a direct pass.
6. **Council default OFF:** multiple agents are not evidence.
7. **Commit–reveal Council:** independent first passes, disjoint evidence where possible, anonymized claims, critique after reveal, and evidence-weighted rather than headcount aggregation.
8. **Matched-budget control:** compare Council/tool escalation against a strong direct route with comparable evidence and compute.

## Mastermind admission

| Gate | Result | Reason |
|---|---|---|
| A | `PASS-SPEC` | Addresses unnecessary orchestration and undefined stopping. |
| B | `PASS` | Routes by epistemic structure, not topic labels or IDs. |
| C | `PASS-SPEC` | Transfers across current facts, formal claims, code, literature, and private artifacts. |
| D | `PASS-SPEC` | Direct low-stakes answers remain allowed; mandatory checks remain mandatory. |
| E | `PASS-SPEC` | Uses general evidence requirements. |
| F | `PASS` | Extends, rather than replaces, the prior router and Council. |
| G | `PASS-STRUCTURAL` | Removing commit–reveal or stop/value markers makes loop-2 checks fail. |
| H | `PASS` | Loop-1 learner and ownership controls remain intact. |

# LOOP 3 — Evidence graph, verification, and scientific validation

## Earliest causal defect

Atomic claim IDs existed, but the decomposition itself was not audited; dependencies could not propagate a failed premise; support type and confidence were conflated; disagreement lacked a stable schema; and assisted output quality could still masquerade as evidence that FOIL improved the user.

## Mechanisms promoted

1. **Dependency-aware atomic claim graph:** proposition, scope, origin, evidence, counterevidence, assumptions, dependencies, status, confidence, verifier, last-checked time, and impact.
2. **Decomposition audit:** coverage, scope preservation, non-invention, non-merger, dependencies, and recomposition.
3. **No citation laundering:** a source must entail the exact atomic claim at the stated scope.
4. **Orthogonal support and confidence:** `PROVEN / MEASURED / CITED / DERIVED` describe proof/provenance obligations; confidence is a separate field and is numeric only after calibration.
5. **Disagreement schema:** contention, both bases, verification, counterevidence, scope, uncertainty, consequence, and user decision.
6. **Verifier escalation:** use the cheapest sufficiently independent verifier diagnostic of the exact claim; same-model reflection and Council agreement are not verification by themselves.
7. **Scientific validation program:** direct AI vs static FOIL vs adaptive FOIL vs low/no-AI where feasible.
8. **Primary endpoint:** delayed independent transfer with relevant AI assistance unavailable.
9. **Learner-model validation:** prospective predictions and confound challenge sets.
10. **Ownership validation:** each state must add incremental predictive validity.
11. **Routing/Council validation:** matched budgets and a retrospective oracle route to measure exploitable headroom.

## Mastermind admission

| Gate | Result | Reason |
|---|---|---|
| A | `PASS-SPEC` | Closes scope loss, citation laundering, correlated verification, and assisted-output proxy defects. |
| B | `PASS` | Generic claim/evidence structure. |
| C | `PASS-SPEC` | Applies to prose, equations, code claims, empirical claims, and system behavior. |
| D | `PASS-SPEC` | Preferences and user-stipulated goals remain outside external-fact verification. |
| E | `PASS-SPEC` | Claim-native verification and AI-free transfer apply across domains. |
| F | `PASS` | Extends existing evidence law and self-improvement gates. |
| G | `PASS-STRUCTURAL` | Removing decomposition/recomposition or the AI-free endpoint makes loop-3 checks fail. |
| H | `PASS` | Prior loops, user authority, and mandatory two-list output remain. |

# Defects caught during closure

1. **Validator path defect:** one validator initially looked for frozen versions in the package root instead of `validation_research_integration/`.
2. **Contention-duel wording defect:** the validator required independent two-sided checking, while the operative heading omitted the explicit word `INDEPENDENTLY`; the protocol was clarified.
3. **Undefined source key:** `RB-ROUTING-SURVEY-2025` was cited before it existed in the basis ledger.
4. **Missing decomposition source record:** the decomposition audit initially relied on the supplied audit without its own primary-source record; Wanner et al. 2024 was added.
5. **Routing-survey metadata defect:** the basis used an older/inexact title; it was corrected to the current arXiv v3 record.
6. **Release-boundary defect:** the final candidate existed, but active `SKILL.md` and the ZIP still contained the pre-integration skill. Internal validation therefore did not describe the shipped artifact. Active `SKILL.md` is now byte-identical to `v3`; `TC-RELEASE-01` and package hash checks make this state release-blocking.
7. **Validation-contamination defect:** rerunning Python validators without suppressing bytecode created `__pycache__` files in the working extraction and correctly caused manifest verification to fail. The extraction was cleaned and all targeted checks were rerun with `PYTHONDONTWRITEBYTECODE=1`; no bytecode remained. The source archive itself was unchanged.

# Validation result

## Mastermind source package

- manifest: `215/215 PASS`;
- closure/reopen validator: `PASS`, 14 questions × 10 loops = 140 attempts;
- authority: `PRE_REVIEW_ONLY`;
- Python source check: 83 files, no failures, no bytecode written.

The broad legacy `validate_v4.py` did not complete inside the isolated execution windows and is **NOT MEASURED**, not counted as a pass.

## FOIL integration

- structural/source/regression validator: `94/94 PASS`;
- frozen behavioral-contract coverage: `18/18 PASS-SPEC`;
- three structural ablations detected;
- all `RB-*` references resolve;
- top-level section numbering and internal section references close;
- active `SKILL.md` equals frozen `v3`.

`PASS-SPEC` means the specification contains the required decision behavior. It does not mean an executing model has demonstrated that behavior.

# SUPPORTED / PROVEN CLAIMS

- The two supplied audits support replacing direct weakness inference with uncertain learner-state hypotheses and diagnostic probes.
- The audits support separating assisted task performance from evidence of independent competence.
- The final active skill contains all three promoted mechanism sets.
- The frozen version sequence, source-key closure, prior invariants, and active-file identity pass the recorded checks.
- The Mastermind package passed the stated source/package validators under `PRE_REVIEW_ONLY` authority.

# FURTHER EVIDENCE / PROOF REQUIRED

- Behavioral evidence that an executing LLM follows FOIL reliably.
- Calibration of learner-state and forgetting predictions.
- Evidence that ownership states predict distinct future capabilities.
- Causal evidence that adaptive fading or cognitive forcing improves this user's learning.
- A calibrated marginal-value router.
- Matched-budget evidence that Council adds value on FOIL tasks.
- Delayed AI-free transfer showing FOIL improves independent competence over ordinary strong AI assistance.
