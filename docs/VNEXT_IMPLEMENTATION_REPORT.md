# The Gauntlet vNext — typed, stateful, evidence-producing, runtime-verifiable implementation

## Executive architecture

The vNext candidate changes the repository from a mix of strong method specifications plus uneven runtime support into one common research-control substrate:

```text
USER / ARTIFACT
  -> SOUL creates TaskState
  -> load-bearing typed obligations
  -> optional MEDITATE metareasoning / FOIL adaptation
  -> claim-native GEM / COUNCIL action
  -> content-addressed evidence receipt
  -> GAUNTLET runtime assurance
  -> SOUL release gate
  -> CLEARED | ISSUE | UNKNOWN | UNAVAILABLE
```

The names and epistemic responsibilities are preserved. The upgrade is in enforceability, state, receipts, tool boundaries and release semantics.

## Current and vNext workflows

### Soul — Research Orchestrator

**v0.5.0:** model frames/decomposes/routes in prose, invokes skills/tools, integrates evidence and releases.

**vNext:** `start_task` hashes the goal and creates `TaskState`; `add_obligation` creates load-bearing typed obligations; module ownership is deterministic by obligation kind; receipts are resolved by owning module; the release gate consumes the **latest valid** receipt for each obligation; tampered/missing/wrong-module receipts cannot clear release; `release_task` closes the task only after the gate clears.

### Gauntlet — Process Assurance

**v0.5.0:** ten operations are specified, while runtime primarily automates repeated-loop/novelty framing and stale governing-state checks.

**vNext:** all ten operations have an explicit support mode and scoped monitor semantics. Typed event streams support mechanical checks; semantically unobservable free text remains `UNKNOWN`/`UNAVAILABLE` rather than fake clear. Repetition/novelty incidents are throttled by incident fingerprint + refractory window instead of lifetime quotas. Authority snapshots are task-addressed. The evidence ledger verifies typed receipt integrity and configured state paths.

### Meditate — Decision Preflight

**v0.5.0:** `STILL -> GROUND -> ORIENT -> WEIGH -> RELEASE` is a specification-only decision protocol.

**vNext:** `DecisionState` records goal, success condition, authoritative artifacts, facts, assumptions, unknowns, candidate actions, blocker and one shared current decision utility. Trigger-free cases skip. Complete quantitative models use one-step value-of-computation; incomplete quantitative models do not manufacture numbers. Ordinal dominance is explicitly labeled heuristic. The output is a PREFLIGHT receipt, not factual proof.

### Council — Evidence Review Panel

**v0.5.0:** strong Council specification; executable helpers are generic red-team/SNAP processes rather than full Council protocol.

**vNext:** dedicated 3–6-seat state machine with artifact-derived roles/questions, required skeptic/adversarial seat, frozen artifact hash, frozen total-budget hash, independent commit hashes, reveal verification, one cross-critique from every seat, overlap diagnostics and DIRECT/VOTE control recording. Council can clear protocol completion only with a same-artifact/same-budget cleared DIRECT control. Later empirical work must test marginal value.

### Mind — Formal Reasoning Gem

**v0.5.0:** claim-native formal reasoning specification without a common portable verifier-receipt interface.

**vNext:** typed `ProofObligation`; bounded exact arithmetic adapter; optional SMT2/Z3 adapter with tool/version/input/output hashes and explicit missing/timeout semantics. Solver success is scoped to the encoding.

### Space — Research Discovery Gem

**v0.5.0:** strong discovery specification plus a small single-index OpenAlex helper.

**vNext:** typed bounded `SearchPlan`, ordered queries, OpenAlex/Crossref adapters, DOI/identity deduplication, source-index provenance and saturation state. Retrieval produces candidates but **not factual clearance**. A separate content-hashed, claim-scoped source-assessment receipt is needed for support/refutation.

### Reality — Method Synthesis Gem

**v0.5.0:** synthesis/admission specification only.

**vNext:** machine-readable `MethodCandidate` with named gap/constraint, changed assumption/mechanism, nearest prior art + delta, invariants/dependencies/failure modes, negative control, transfer target, ablation and verifier plan. Admission requires a stored cleared Space source-assessment receipt; it cannot trust caller-supplied claims of prior-art clearance.

### Power — Engineering Verification Gem

**v0.5.0:** engineering workflow specification; tool execution is task-specific rather than normalized into one receipt contract.

**vNext:** typed `VerificationPlan` with known verifier families, mandatory/optional semantics, `shell=False`, resource timeout, output hashes, named defect-class coverage and explicit scope. Arbitrary custom commands require outer opt-in. Missing mandatory tools yield `UNAVAILABLE`; failing checks yield `ISSUE`.

### Time — Evaluation & Benchmarking Gem

**v0.5.0:** good benchmark methodology and project-specific harnesses, but no generic statistical receipt engine.

**vNext:** typed paired-binary plans/observations, item-addressed frozen exclusions, explicit contamination handling, exact conditional McNemar, Wilson intervals and Holm correction. Silent exclusion mapping is rejected. Initial statistics are fixed-n only; anytime-valid inference remains a separate future implementation obligation.

### FOIL — adaptation bridge

**v0.5.0:** mature profile/onboarding/calibration and prompt-time relevance routing.

**vNext integration:** the existing FOIL engine is preserved. The prompt hook emits a hashed typed adaptation event and may clear only a typed `ADAPTATION` obligation. A profile snapshot alone is `UNKNOWN`, not success. FOIL cannot clear proof/discovery/engineering/evaluation obligations.

## Full cross-component workflow

1. `SessionStart`: initialize typed runtime, snapshot authority, reset legacy boundary incident state, load FOIL profile.
2. `UserPromptSubmit`: generic hook records only prompt digest/size bucket/explicit aliases; FOIL computes relevance and emits a typed adaptation receipt when an explicit typed adaptation obligation exists.
3. Soul starts an explicit substantial task and records success boundary/stakes/reversibility metadata.
4. Soul decomposes into obligation kinds and routes deterministic owners.
5. Meditate runs only when trigger conditions make preflight valuable.
6. Mind/Space/Reality/Power/Time/Council perform claim-native actions and write content-addressed receipts.
7. Gauntlet consumes typed events/receipts plus its compatibility monitors and emits scoped assurance verdicts.
8. Soul release gate resolves the latest valid owning-module receipt for every load-bearing obligation.
9. `CLEARED` permits release. `ISSUE`, `UNKNOWN`, and `UNAVAILABLE` remain visibly unresolved and block an explicit typed task release.
10. Ordinary simple interactions with no explicit typed task are not forced through ceremonial gating.

## Privacy and storage

Mutable runtime data remains owner-private under configured `.egrt/state/` by default. Generic events use hashes and compact structured metadata; they do not persist raw prompts or generic raw tool output. Deliberately saved evidence artifacts are separate, explicit objects.

## Empirical boundary

This candidate is an implementation/mechanical milestone. After full repository CI passes, freeze the implementation before benchmarking. Then run matched-budget component ablations and whole-system comparisons without modifying mechanisms after seeing benchmark answers.
