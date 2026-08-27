# Evidence Review Panel / Council — engineering specification

## Obligation

Provide selective, controlled review of a concrete artifact after a strong direct pass while measuring rather than assuming review diversity or independence.

Council owns only the `REVIEW` obligation. It may produce supported findings and proposal-only neutral challenges for target modules, but it cannot clear a `PROOF`, `DISCOVERY`, `SYNTHESIS`, `ENGINEERING`, `EVALUATION`, `ASSURANCE`, `PREFLIGHT`, `ADAPTATION`, or `ADVERSARY` obligation.

## Runtime and schemas

- Runtime: `tools/council_runtime.py`
- Domain receipt schema: existing `egrt.runtime.v1`
- Challenge schema: additive `egrt.challenge.v1`
- Neutral challenge implementation: `tools/egrt_challenge_types.py` and `tools/egrt_challenge.py`
- State machine: `COMMIT -> REVEAL -> CROSS_CRITIQUE -> CLOSED`

Council never imports `foil_*`. FOIL remains an optional later controller and is not part of the native Council path.

## Frozen Council state

A Council has:

- an optional bound task ID;
- a frozen artifact hash and frozen total-budget hash;
- 3–6 seats;
- first-pass commitment hashes;
- sealed and revealed submissions;
- structured cross-critiques;
- method, evidence, provenance, reviewer-provenance, and finding-overlap diagnostics;
- structured Council findings;
- supported finding IDs selected at synthesis;
- a mandatory same-artifact, same-total-budget `DIRECT` control receipt;
- an optional `VOTE` control receipt;
- one Council receipt that can clear only the bound `REVIEW` obligation.

## Challenge-derived seat contract

A vNext `CouncilSeat` extends the legacy seat fields with:

- `challenge_kind`;
- `discriminator`;
- `required_capability`;
- `target_obligation_id`;
- `refuter`;
- `reviewer_provenance`;
- `challenge_contract="vnext"`.

Legacy four-field seats remain readable and executable for backward compatibility. A Council cannot mix legacy and vNext seats in one run.

### Residual-gap seat classes

Derive seats from unresolved neutral challenge classes rather than generic personalities:

| Residual class | Typical role | Decisive partition or discriminator |
|---|---|---|
| Formal correctness | proof/formalization | exact derivation, contradiction, alternate formalization, counterexample |
| Evidence and provenance | source assessment | first-party evidence, source conflict, citation/provenance lineage |
| Executable behavior | implementation/integration | real entrypoint, failure class, output contract, metamorphic relation |
| Measurement validity | evaluation design | baseline/estimand, contamination, scorer, stopping or budget boundary |
| Novelty or costume | prior-art/ablation | strongest known costume, assumption knockout, transfer or ablation |
| Operational feasibility | state/decision/operations | state drift, resource boundary, reversal condition |

`derive_challenge_seats()` deterministically converts open `ChallengeRequest` objects into vNext seats. Resolved and dismissed challenges are ignored. Load-bearing, higher-risk, higher-information, and lower-cost challenges are prioritized within the frozen maximum of six seats.

Every seat must own a distinct question. Duplicate challenge kinds or duplicate discriminators are rejected unless both seats declare genuinely distinct evidence partitions. A skeptic/adversarial seat is mandatory and must name a concrete refuter; a generic instruction such as “be critical” does not satisfy the contract.

## Commit–reveal and cross-critique

1. Freeze the artifact, total budget, seats, questions, methods, evidence partitions, challenge bindings, and reviewer provenance.
2. Each seat commits a salted hash of its structured first-pass submission before any reveal.
3. Reveal only after all commitments are frozen. A wrong nonce or altered submission fails verification.
4. Compute evidence, provenance, method, reviewer-provenance, and finding overlap.
5. Cross-critique only after every reveal.
6. Require every seat to contribute a structured critique against another seat.
7. Synthesize by supported finding IDs and preserve unresolved disagreement.

Nominal seat count never establishes statistical independence. Every pair reports `independence_status="NOT_ESTABLISHED"`, and the Council-level diagnostic is `NOT_ESTABLISHED_BY_SEAT_COUNT`. Same-model or same-reviewer provenance remains explicit.

## Structured findings and neutral challenge output

A supported vNext finding is recorded as `CouncilFinding` with:

- seat ID;
- target module and target obligation ID;
- challenge kind;
- hypothesis, alternative, concrete refuter, and consequence if true;
- load-bearing flag and required capability;
- evidence partition;
- candidate, scope, and obligation-set SHA-256 bindings;
- provenance and typed metadata.

`record_finding()` is permitted only after all seats reveal. For vNext seats, the finding must match the seat’s challenge kind, target obligation, required capability, concrete refuter, and evidence partition, and its finding ID must have appeared in that seat’s frozen revealed submission.

A vNext Council cannot clear its `REVIEW` obligation with a supported finding that lacks a structured `CouncilFinding` record.

After Council finalization, `propose_supported_finding_challenge()` may convert one supported structured finding into a neutral `ChallengeRequest` with `origin=COUNCIL`. The emitted object is:

- bound to the same task, target obligation, candidate, scope, and obligation set;
- stored initially as `PROPOSED`;
- marked `authority=PROPOSAL_ONLY`;
- unable to resolve itself;
- unable to create a domain receipt;
- unable to clear the target module’s obligation;
- subject to the shared challenge budget, deduplication, selection, and release rules.

The target module or host must select a discriminator and the claim-native module must produce the resolving evidence.

## Control and release semantics

A Council review requires a real `DIRECT` control receipt with the same:

- review obligation ID;
- frozen artifact hash;
- frozen total-budget hash.

The optional `VOTE` control is diagnostic only.

Council finalization returns:

- `UNKNOWN` when commit/reveal is incomplete;
- `UNKNOWN` when cross-critique participation is incomplete;
- `UNKNOWN` when the matched `DIRECT` control is absent, invalid, or mismatched;
- `UNKNOWN` when a vNext supported finding lacks a structured record;
- `UNKNOWN` when synthesis supports no findings;
- `CLEARED` only when the frozen Council review protocol completed and at least one supported finding remains.

`CLEARED` means only that the controlled Council protocol completed for the `REVIEW` obligation. It is not a verdict on the target domain claim and not evidence that Council outperforms `DIRECT` or `VOTE`.

When a bound task exists, attempting to finalize Council against a non-`REVIEW` obligation raises `CouncilAuthorityError`. A Council receipt records `authority=REVIEW_ONLY` and `target_domain_clearance_authorized=false`.

## Backward compatibility

- Existing `CouncilSeat(seat_id, role, question, method, evidence_partition=None)` construction remains valid.
- Existing commit/reveal, overlap, cross-critique, control, and finalization behavior remains valid for legacy Council state.
- Historical Council state loads through inferred legacy challenge fields; historical receipts are not rewritten.
- Native Council challenge behavior is additive and uses the shared challenge configuration.
- No FOIL profile, FOIL receipt, or seat count changes evidence authority.

## Mechanical acceptance tests

`tests/test_council_challenge_seats.py` proves:

- distinct challenge questions and duplicate-kind/discriminator rejection;
- deterministic derivation from open challenge classes;
- concrete skeptic/refuter behavior;
- structured supported finding to neutral `COUNCIL` challenge conversion;
- target-domain authority denial;
- mandatory same-artifact/same-budget `DIRECT` control;
- same-model seats are never labeled independent solely by seat count.

Existing Council tests continue to prove:

- 3–6 seat bounds;
- skeptic requirement;
- commitment hiding and binding;
- tampered reveal rejection;
- overlap diagnostics;
- complete cross-critique participation;
- matching control semantics;
- non-recallable finalization.

## Non-goals and efficacy boundary

This work does not establish that Council improves task outcomes. It does not treat agreement as truth, seat count as independence, or a Council finding as claim-native evidence. Marginal-value claims still require prospective, matched-budget comparison against `DIRECT`; null and negative results must be retained.
