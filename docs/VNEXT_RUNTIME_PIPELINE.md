# vNext typed runtime pipeline

This document freezes the pipeline before component-specific implementation. It is the integration contract for Soul, Gauntlet, Meditate, Council, the five Gems, and FOIL.

## 0. Current v0.5.0 pipeline

```text
User
  -> Research Orchestrator specification
  -> model decides which skill(s) apply
  -> optional FOIL prompt relevance/profile context
  -> selected research work/tools
  -> Gauntlet hooks monitor stale state, repeated loops, and novelty/survivor framing
  -> optional Council/SNAP/red-team helpers
  -> prose synthesis/release
```

Strengths: modular epistemic obligations, privacy-conscious hooks, real Gauntlet/FOIL runtime, benchmark/reproducibility discipline.

Limitation: many obligations are represented in prose but do not share a single typed state/receipt/release contract.

## 1. vNext end-to-end pipeline

Every component in this pipeline exposes the five shared layers of the common runtime contract: `SPEC` (the owned obligation), `STATE` (typed machine-readable state and events), `ACTION/TOOL` (the evidence-producing method), `RECEIPT` (content-addressed record), and `VERDICT` (`CLEARED | ISSUE | UNKNOWN | UNAVAILABLE`). See `docs/specs/COMMON_RUNTIME_CONTRACT.md`.

```text
USER / ARTIFACT
      |
      v
+------------------------------+
| 1. SOUL — FRAME TASK         |
| task_id + goal_hash          |
| success / stakes / boundary  |
+------------------------------+
      |
      v
+------------------------------+
| 2. CREATE OBLIGATIONS        |
| PROOF / DISCOVERY /          |
| SYNTHESIS / ENGINEERING /    |
| EVALUATION / ASSURANCE /     |
| PREFLIGHT / REVIEW /         |
| ADAPTATION / ADVERSARY       |
+------------------------------+
      |
      +---------------------+
      |                     |
      v                     v
+-------------+      +----------------+
| 3. MEDITATE |      | 4. FOIL        |
| if triggered|      | routing/adapt. |
| select next |      | no self-cert.  |
| computation |      +----------------+
+-------------+               |
      |                       |
      +-----------+-----------+
                  v
+---------------------------------------------------------+
| 5. ROUTE CLAIM-NATIVE WORK                              |
| MIND | SPACE | REALITY | POWER | TIME | COUNCIL |        |
| BLACK GEM (ADVERSARY)                                   |
+---------------------------------------------------------+
                  |
                  v
+---------------------------------------------------------+
| 6. RECEIPTS                                              |
| action, input hash, output hash, evidence/provenance,    |
| verifier/tool identity, scope, uncertainty/unresolved    |
+---------------------------------------------------------+
                  |
                  v
+---------------------------------------------------------+
| 7. GAUNTLET — RUNTIME ASSURANCE                          |
| frame/audit/costume/derive/self/redirect/refresh/        |
| boundary/explain/oob with explicit support mode          |
+---------------------------------------------------------+
                  |
                  v
+---------------------------------------------------------+
| 8. SOUL RELEASE GATE                                     |
| every load-bearing obligation has a scoped valid receipt |
+---------------------------------------------------------+
        |             |              |              |
        v             v              v              v
     CLEARED         ISSUE         UNKNOWN       UNAVAILABLE
        |
        v
   supported result
```

## 2. Universal object lifecycle

### Task

`TaskState(task_id, goal_hash, obligations[], active, released, metadata)`

### Obligation

`Obligation(obligation_id, kind, claim, load_bearing, required_module, metadata)`

### Runtime event

`RuntimeEvent(event_type, component, task_id, payload_hash, timestamp, metadata)`

Generic events never require raw prompt/output persistence.

### Evidence

`EvidenceRef(evidence_class, artifact, claim, verifier, provenance_group, fresh_at, metadata)`

### Receipt

`Receipt(receipt_id, module, obligation_id, verdict, action, input_hash, output_hash, evidence, verifier, tool_version, unresolved, notes)`

Receipts are content-addressed and owner-private under `.egrt/state/runtime/` by default.

## 3. Release semantics

- `CLEARED`: the represented obligation passed the stated verifier within its stated scope.
- `ISSUE`: evidence actively contradicts or fails the obligation.
- `UNKNOWN`: the represented state is insufficient to reach a sound conclusion.
- `UNAVAILABLE`: the required method/integration/tool could not be executed.

These are not confidence levels.

## 4. Privacy model

The generic hook layer stores:

- prompt hash, length bucket, explicit slash-command aliases;
- tool-input hash, tool name, error flag;
- task/obligation/receipt IDs;
- structured evidence/provenance metadata.

It does not store raw prompts or generic raw tool output. Component-specific artifacts may be deliberately saved by the user/tool when they are themselves the evidence object.

## 5. Failure semantics

- Missing receipt for a load-bearing obligation -> `UNKNOWN`, not silent success.
- Missing verifier/tool -> `UNAVAILABLE`, not false.
- Same producer/verifier provenance -> independence `UNKNOWN`/`ISSUE` according to the claim, not automatic independent confirmation.
- Search saturation with no result -> `NOT_FOUND_WITHIN_SCOPE`, not nonexistence.
- Council synthesis without full commit/reveal + per-seat cross-critique + same-artifact/same-budget DIRECT control -> REVIEW remains `UNKNOWN`.
- Solver success -> formal encoding only; English entailment remains a separate obligation when nontrivial.
- Green engineering checks -> only named check/defect-class coverage.
- Black Gem surviving an attack panel -> `UNKNOWN`, never `CLEARED`; ADVERSARY receipts can raise an issue but never clear one.

## 6. FOIL integration

FOIL remains the adaptive complementary-assistance layer. It may:

- alter routing priority;
- recommend extra verification/representation changes;
- contribute adaptation evidence about the user/task.

FOIL may not mark another obligation `CLEARED` merely because it recommended or assisted the action. Factual warrant comes from the claim-native receipt.

## 6b. Black Gem — adversarial review

Black Gem is the producer for the `ADVERSARY` obligation. It runs a frozen attack
rubric across two or more independently provenanced breaker seats — a blind
independent pass, off-diagonal cross-critique, then one synthesis — over a frozen
candidate, and probes each seat with a planted-costume canary at the graded
temperature before trusting its verdict.

Its verdict range is deliberately incomplete: a surviving break, a `KILL`, or an
`AMEND` produces `ISSUE`; a trusted `SURVIVES_TO_GATE` produces `UNKNOWN`; an
untrusted canary, unestablished independence, or a successful injection canary
produces `UNKNOWN` with unresolved items; fewer than two contributing seats or no
transport produces `UNAVAILABLE`. **Black Gem never emits `CLEARED`** (asserted in
`finalize`). The absence of a found break is not warrant that the candidate is
correct, so a downstream claim-native receipt — not this one — is what can clear a
substantive obligation.

## 7. Mastermind boundary

Mastermind is not part of this pipeline or repository runtime. It may be used externally during development audits, but no import, hook, state, package, benchmark-control file, or runtime dependency is permitted in The-Gauntlet.

## Important non-upgrades

- Space retrieval candidates are not factual warrant; only a content-hashed claim-scoped source-assessment receipt can clear DISCOVERY.
- A valid receipt hash proves integrity, not semantic entailment.
- Council overlap diagnostics do not prove statistical independence.
- Meditate numeric VOC is used only with one common supplied current decision utility and complete action outcome models; otherwise it stays heuristic/unknown.
- Power never invokes a shell; arbitrary custom verifier commands require explicit outer `EGR_POWER_ALLOW_CUSTOM_COMMANDS=1`.
- Time fixed-n statistics are not anytime-valid under repeated peeking.
