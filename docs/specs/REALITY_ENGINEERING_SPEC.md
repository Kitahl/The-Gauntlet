# Reality / Method Synthesis — engineering specification

## Authority

Reality owns **SYNTHESIS**. A Reality `CLEARED` receipt means only:

> the candidate is sufficiently specified and evidence-bound to be tested.

It does **not** establish global novelty, formal truth, engineering correctness,
empirical efficacy, benchmark superiority, evaluation clearance, execution authority,
or host-write authority.

The admission receipt therefore carries:

- `authority = SYNTHESIS_ONLY`
- `admission_only = true`
- `testable_candidate = true|false`
- `novelty_established = false`
- `efficacy_established = false`
- `engineering_verified = false`
- `evaluation_cleared = false`
- `execution_authorized = false`
- `host_write_authorized = false`

## Automatic routing

Soul already maps dependency-ready `SYNTHESIS` obligations to `reality`. Reality must
remain automatically routable. The normal bounded path is:

1. receive/construct a `MethodCandidate`;
2. resolve the task-bound Discovery dependency;
3. validate current stored Space assessment evidence;
4. construct a `CandidateAttackBundle`;
5. create four Reality-native neutral challenges;
6. deterministically select the minimum useful discriminator when one dominates;
7. leave incomparable/unavailable work explicit;
8. emit a bounded SYNTHESIS admission receipt.

No human approval is required merely because a challenge exists. Host choice is
required only when the registered discriminator set is genuinely incomparable or an
externally consequential capability is unavailable.

## MethodCandidate

The historical constructor remains compatible. A candidate contains:

- gap and failed constraint;
- changed assumption;
- mechanism and actual delta;
- nearest prior art;
- inputs, outputs, invariants and dependencies;
- failure modes;
- negative control;
- transfer target;
- ablation plan;
- verifier plan;
- optional metadata.

Useful additive metadata includes `scope_hash`, `prior_art_claim_scope`,
`competing_mechanism`, `competing_mechanism_required`, and discriminator objective
ranks. Metadata never grants evidence authority.

## CandidateAttackBundle

`CandidateAttackBundle` is persisted in private runtime state and binds:

- `bundle_id`
- `task_id`
- `obligation_id`
- `candidate_id`
- `candidate_hash`
- `scope_hash`
- `obligation_set_hash`
- native `challenge_ids`
- selected discriminator plan ids
- nearest stored Space source-assessment receipt ids
- status and unresolved reasons
- metadata hash
- content hash

The bundle content hash is recomputed on load/admission. Candidate, task, scope and
obligation-set binding mismatches are admission issues.

## Space prior-art boundary

Reality does not trust caller-provided prior-art dictionaries. Costume/prior-art state
must be reconstructed from `RuntimeStore`.

A usable prior-art chain requires:

1. an integrity-valid stored Space `source-assessment` receipt;
2. `CLEARED` only for that claim-scoped assessment;
3. a bound stored Space `multi-index-retrieval` receipt;
4. the retrieval receipt's `candidate_hash` equal to the concrete Reality candidate
   hash;
5. the retrieval registered scope hash equal to any explicit candidate `scope_hash`;
6. the Space assessment obligation be a Discovery dependency of the SYNTHESIS
   obligation;
7. cited assessed evidence be content-addressed and claim-scoped.

Retrieval is not assessment. `NOT_FOUND_WITHIN_SCOPE` is not nonexistence. Derivative
copies sharing content/provenance do not gain independent weight. A scoped non-match
may be described as no matching prior mechanism found **within the registered assessed
scope**; it is never promoted to global novelty.

## Native challenges

Reality proposes native neutral challenges through `egrt.challenge`; it does not
import `foil_*`.

### NOVELTY_COSTUME

Tests whether the concrete candidate's claimed assumption/mechanism delta is matched by
nearest assessed prior art. The load-bearing challenge is attached to the Discovery
obligation so the neutral resolution can be bound to the actual Space
`source-assessment` receipt. A raw retrieval receipt, citation count, model confidence,
Council opinion, FOIL profile, or caller-supplied dictionary cannot resolve it.

A Space-grounded resolution supports only the registered scoped prior-art relation. It
does not establish global novelty.

### ASSUMPTION_KNOCKOUT

Binds the changed assumption, candidate/scope hashes, a restoration/neutralization
intervention, expected symptom and refuter. For SYNTHESIS admission, the candidate must
contain a meaningful assumption change and a bound knockout discriminator. Empirical
knockout results remain downstream evaluation evidence; Reality never fabricates them.

### COMPETING_MECHANISM

When a credible alternative is supplied or explicitly required, the challenge binds
mechanism A, mechanism B, alternative assumptions, expected differing behavior and the
A-vs-B discriminator. When scoped prior-art work yields no credible alternative,
Reality records `DISMISSED_NOT_APPLICABLE` rather than inventing one.

### MINIMUM_DISCRIMINATOR

Reality constructs bounded plans for:

- negative control;
- component-specific ablation;
- meaningful transfer.

The neutral selector uses a Pareto objective over capability availability,
discrimination, information, risk reduction, cost and irreversibility. If one plan
dominates, it is selected automatically. If multiple incomparable plans survive, the
challenge remains `UNRESOLVED`; Reality does not invent a pseudo-optimum and does not
claim global cost optimality.

## Mechanism diversity

`mechanism_signature()` normalizes and compares structural candidate fields:

- changed assumption;
- mechanism;
- causal route;
- intervention;
- dependency structure;
- required information;
- failure modes;
- predicted behavior.

Candidate id, labels, tag order and presentation metadata do not create structural
diversity. A different signature is only a diversity diagnostic; it is not novelty
proof or semantic-equivalence proof.

## Admission gate

`evaluate_admission()` requires:

1. complete `MethodCandidate`;
2. meaningful changed assumption;
3. current stored candidate-bound Space assessment evidence;
4. intact `CandidateAttackBundle`;
5. exact candidate/task/scope/obligation-set bindings;
6. `NOVELTY_COSTUME` resolved by the bound Space receipt;
7. `ASSUMPTION_KNOCKOUT` with a bound discriminator (not an unresolved challenge);
8. competing-mechanism requirement satisfied or explicitly not applicable;
9. a selected minimum useful discriminator;
10. no Reality self-certification used as challenge evidence.

Results:

- `CLEARED`: testable enough for SYNTHESIS scope only;
- `UNKNOWN`: unresolved attack, ambiguity or insufficient prior-art state;
- `UNAVAILABLE`: required capability/evidence cannot currently be obtained;
- `ISSUE`: a binding failure, self-certification, meaningless assumption change or
  direct attack result invalidates the admission claim.

## Downstream boundary

Reality defines attacks and test plans. It does not fabricate their measured outcomes.

- Power owns implementation and engineering verification.
- Time owns experimental execution/evaluation.
- Mind owns formal proof when needed.
- Space owns additional current evidence/prior-art work.
- Gauntlet owns process assurance.
- Soul owns routing/integration/release.

Reality's bundle cannot substitute for any of those receipts.

## Mechanical validation

`tests/test_reality_challenge_runtime.py` covers the required Reality regressions:
bundle creation/binding; real Space assessment requirements; retrieval/fake receipt
rejection; derivative-source accounting; costume and assumption blocking; competing
mechanism paths; wording-only diversity; all three discriminator families and
incomparable selection; candidate/scope/obligation mismatch; SYNTHESIS-only receipt
authority; self-certification rejection; historical `MethodCandidate` compatibility;
and the no-FOIL-import boundary.

Repository-level completion still requires the official exact-head validation workflows,
including the full test suite, Soul/Gauntlet and vNext validators, showcase validation,
Ruff, compileall, portability, security and CodeQL.
