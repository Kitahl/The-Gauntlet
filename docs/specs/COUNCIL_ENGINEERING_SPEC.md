# Evidence Review Panel / Council v3 — engineering specification

## Obligation

Provide selective, controlled review of a concrete artifact after a strong direct pass while measuring rather than assuming review diversity or independence.

Council owns only the `REVIEW` obligation. It may produce supported findings and proposal-only neutral challenges for target modules, but it cannot clear a `PROOF`, `DISCOVERY`, `SYNTHESIS`, `ENGINEERING`, `EVALUATION`, `ASSURANCE`, `PREFLIGHT`, `ADAPTATION`, or `ADVERSARY` obligation.

Council v3 is additive over Council vNext. It adds a frozen, seat-local evidence-acquisition layer before commit-reveal. It does not merge FOIL into Council, does not import `foil_*`, and does not convert tool output into domain truth.

## Runtime and schemas

- Council vNext runtime: `tools/council_runtime.py`
- Council v3 evidence layer: `tools/council_v3_evidence/__init__.py`
- Domain receipt schema: existing `egrt.runtime.v1`
- Challenge schema: additive `egrt.challenge.v1`
- Council v3 evidence schema identifier: `egrt.council.v3`
- Neutral challenge implementation: `tools/egrt_challenge_types.py` and `tools/egrt_challenge.py`
- Council state machine: `COMMIT -> REVEAL -> CROSS_CRITIQUE -> CLOSED`
- Council v3 acquisition state: `INITIALIZED -> PLANS_FROZEN -> EVIDENCE_READY -> COMMITTED -> CLOSED`

Council never imports `foil_*`. A future FOIL smart-tool controller may supply neutral bundle candidates, but native Council v3 selection, evidence admission, and authority checks remain independently testable.

## Frozen Council state

Council vNext preserves:

- an optional bound task ID;
- a frozen artifact hash and frozen total-budget hash;
- 3–6 challenge-derived seats;
- first-pass commitment hashes;
- sealed and revealed submissions;
- structured cross-critiques;
- method, evidence, provenance, reviewer-provenance, and finding-overlap diagnostics;
- structured Council findings;
- supported finding IDs selected at synthesis;
- a mandatory same-artifact, same-total-budget `DIRECT` control receipt;
- an optional `VOTE` control receipt;
- one Council receipt that can clear only the bound `REVIEW` obligation.

Council v3 additionally freezes before any acquisition or first-pass commit:

- a caller-supplied total `EvidenceBudget`;
- one non-transferable `EvidenceBudget` per seat;
- one `EvidenceUtilityPolicy` per seat;
- each seat's baseline evidence IDs and provenance groups;
- all candidate bundle plans and exclusions;
- the selected bundle or explicit stand-down state;
- a plan-freeze digest.

## Challenge-derived seat contract

A vNext `CouncilSeat` contains:

- `challenge_kind`;
- `discriminator`;
- `required_capability`;
- `target_obligation_id`;
- `refuter`;
- `reviewer_provenance`;
- `challenge_contract="vnext"`.

Council v3 requires vNext seats. Legacy Council remains available through `tools/council_runtime.py` and is not reinterpreted.

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

Every seat must own a distinct question. Duplicate challenge kinds or discriminators are rejected unless both seats declare genuinely distinct evidence partitions. A skeptic/adversarial seat is mandatory and must name a concrete refuter.

## Council v3 evidence budget

`EvidenceBudget` contains:

- `token_limit`;
- `money_microunits_limit`;
- `latency_ms_limit`;
- `tool_call_limit`.

The caller freezes the total budget. Seat budgets are frozen before Council work starts.

For additive resources:

\[
\sum_i b^{token}_i \le B^{token},
\qquad
\sum_i b^{money}_i \le B^{money},
\qquad
\sum_i b^{calls}_i \le B^{calls}.
\]

Because first-pass seats may execute in parallel, the wall-time ceiling is enforced as:

\[
\max_i b^{latency}_i \le B^{latency}.
\]

Unused seat budget is not transferred after outcomes are observed. This prevents later seats from receiving an outcome-dependent evidence advantage.

## Frozen utility policy

`EvidenceUtilityPolicy` is frozen per seat and contains:

- `rescue_value`;
- `damage_loss`;
- `token_price`;
- `money_price`;
- `latency_price`;
- `privacy_price`;
- `failure_loss`;
- `minimum_margin`.

These values are **not** candidate fields. A candidate bundle cannot choose its own prices, damage penalty, or rescue value.

If these values are not defensible for a deployment, the smart-evidence route should remain off or shadow rather than inventing pseudo-precise utilities.

## Neutral evidence bundle contract

`EvidenceBundleCandidate` contains:

- seat and bundle IDs;
- provided capabilities;
- tool IDs;
- exact tool-contract digests;
- frozen scored estimate-receipt IDs and digests;
- dependency edges;
- lower bound on rescue probability;
- lower bound on valid-evidence probability;
- upper bound on damage probability;
- upper bound on failure probability;
- complete expected token, money, latency, and privacy costs;
- interaction basis;
- task-only frontier flag;
- hidden-gold-dependence flag;
- side-effect class.

Every bundle must be dependency-complete and acyclic. Tool-contract digests bind exactly one versioned contract to every tool.

`interaction_basis` is restricted to:

- `DIRECT_BUNDLE_RECEIPTS`; or
- `PESSIMISTIC_PRIOR`.

Council v3 never assumes multi-tool independence by multiplying individual tool success probabilities.

## Conservative utility

For candidate bundle \(B\) under frozen seat policy \(\pi\):

\[
U_{LCB}(B \mid \pi)
=
V_R \, LCB(P_{rescue}) \, LCB(P_{valid})
-
L_D \, UCB(P_{damage})
-
p_t C_t
-
p_m C_m
-
p_l C_l
-
p_p C_p
-
L_F \, UCB(P_{failure}).
\]

The runtime selects a bundle only if:

1. it is task-only;
2. it is not hidden-gold-dependent;
3. it is `READ_ONLY`;
4. it provides the seat's required capability;
5. it is inside that seat's frozen budget;
6. it is not dominated by another feasible bundle; and
7. its conservative utility exceeds the frozen `minimum_margin`.

Otherwise the seat stands down and uses only its frozen baseline evidence.

A bundle \(A\) dominates \(B\) when \(A\) has at least as much conservative utility, no greater token, money, latency, or call cost, and is strictly better on at least one of those dimensions.

## Evidence-acquisition isolation

All seat plans freeze before acquisition.

All selected acquisition completes before **any** seat first-pass commitment. This is stricter than merely hiding commitment contents and prevents later acquisition plans from becoming outcome-dependent.

During acquisition:

- cross-seat result reuse is forbidden;
- cross-seat budget transfer is forbidden;
- only tools in the frozen selected bundle may execute;
- only read-only evidence is admissible;
- actual costs must remain within the seat's frozen budget;
- call outcomes must conserve attempted calls exactly;
- invalid or unresolved evidence has no admitted evidence IDs.

`SeatEvidenceReceipt` records:

- Council, seat, and bundle IDs;
- evidence status;
- executed tool IDs and tool-receipt IDs;
- source artifact digests;
- provenance groups;
- admitted evidence IDs;
- exact token, money, latency, and call accounting;
- output digest;
- side-effect class;
- any attempted reuse provenance.

A non-`VALID` receipt cannot carry admitted evidence IDs.

## Submission binding

`commit_v3()` is the normative Council v3 commit entrypoint.

For each seat, the submitted evidence IDs must exactly equal:

\[
E_i^{baseline} \cup E_i^{admitted}
\]

and submitted provenance groups must exactly equal the frozen baseline plus the admitted seat-local acquisition provenance.

This prevents a seat from silently importing another seat's newly acquired evidence before reveal.

## Commit-reveal and cross-critique

After every seat's acquisition phase is complete:

1. each seat commits a salted hash of its structured first-pass submission;
2. reveal only after all commitments are frozen;
3. reject altered submissions or wrong nonces;
4. compute evidence, provenance, method, reviewer-provenance, and finding overlap;
5. compute Council v3 source-digest and tool overlap;
6. cross-critique only after every reveal;
7. require every seat to contribute a structured critique against another seat;
8. synthesize by supported finding IDs and preserve unresolved disagreement.

Nominal seat count never establishes statistical independence. Every Council v3 source/tool pair reports `independence_status="NOT_ESTABLISHED"`, and the Council-level diagnostic remains `NOT_ESTABLISHED_BY_SEAT_COUNT`.

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

After Council finalization, `propose_supported_finding_challenge()` may convert one supported finding into a neutral `ChallengeRequest` with `origin=COUNCIL`.

The emitted challenge is proposal-only and cannot:

- resolve itself;
- create a domain receipt;
- clear the target module's obligation;
- apply a repair;
- authorize a write.

The target module remains responsible for claim-native verification.

## Council v3 evidence audit

Before ordinary Council finalization, `finalize_v3()` constructs an immutable evidence audit containing:

- plan-freeze hash;
- proof that plans froze before commits;
- proof that evidence acquisition completed before commits;
- exact total token, money, call, and critical-path latency accounting;
- cross-seat reuse violations;
- side-effect violations;
- source/tool overlap diagnostics;
- `EVIDENCE_ACQUISITION_ONLY` authority;
- `domain_clearance_authorized=false`.

Any audit violation is forwarded as an unresolved Council review defect.

The v3 evidence-audit hash is then cryptographically bound into the synthesis output hash passed to ordinary `council_runtime.finalize()`. Council v3 therefore reuses the existing REVIEW-only receipt rather than creating a second domain-like receipt.

## Control and release semantics

A Council review still requires a real `DIRECT` control receipt with the same:

- review obligation ID;
- frozen artifact hash;
- frozen total-budget hash.

Council v3 does not relax any vNext release condition.

Council finalization returns:

- `UNKNOWN` when commit/reveal is incomplete;
- `UNKNOWN` when cross-critique participation is incomplete;
- `UNKNOWN` when the matched `DIRECT` control is absent, invalid, or mismatched;
- `UNKNOWN` when a supported vNext finding lacks a structured record;
- `UNKNOWN` when Council v3 reports an evidence-process violation;
- `UNKNOWN` when synthesis supports no findings;
- `CLEARED` only when the frozen Council REVIEW protocol completed and at least one supported finding remains.

`CLEARED` means only that the controlled Council review protocol completed. It is not a verdict on the target domain claim and not evidence that Council v3 improves outcomes.

## FOIL composition boundary

The FOIL Smart-Tool Value Update is currently proposed and unvalidated. Council v3 therefore does not depend on a `foil_*` implementation.

A future FOIL controller may provide neutral `EvidenceBundleCandidate` rows only if:

- bundle selection remains task-local;
- estimates come from frozen scored receipts or a pessimistic prior;
- Council's frozen utility policy remains external to the candidate;
- Council's native baseline challenges are not removed;
- no cross-seat evidence partition is merged before reveal;
- authority remains evidence-acquisition-only.

FOIL may help buy evidence. It cannot choose Council truth, clear a target obligation, or become another Council voter.

## Backward compatibility

- Council vNext remains in `tools/council_runtime.py`.
- Legacy Council remains readable and executable.
- Council v3 requires vNext seats and is opt-in through `tools/council_v3_evidence/__init__.py`.
- Historical Council state and receipts are not rewritten.
- No existing receipt semantics are reinterpreted.
- No non-FOIL module imports `foil_*`.

## Mechanical acceptance tests

`tests/test_council_v3_evidence.py` proves:

- deterministic positive-utility bundle selection;
- stand-down on non-positive utility;
- hidden-gold and non-read-only bundle exclusion;
- frozen seat-budget conservation;
- dependency-cycle rejection;
- all acquisition completes before any first-pass commit;
- cross-seat result reuse is rejected;
- invalid evidence cannot become admitted evidence;
- seat submissions are bound to the frozen evidence partition;
- shared source evidence is measured as overlap without an independence claim;
- final Council v3 review preserves `REVIEW_ONLY` authority and binds the evidence audit.

Existing Council vNext tests continue to prove:

- 3–6 seat bounds;
- skeptic requirement;
- commitment hiding and binding;
- tampered reveal rejection;
- distinct challenge/discriminator rules;
- overlap diagnostics;
- complete cross-critique participation;
- structured finding/challenge conversion;
- matching direct-control semantics;
- target-domain authority denial;
- non-recallable finalization.

## Efficacy boundary and required evaluation

Council v3 is a mechanical and architectural upgrade, not evidence of behavioral benefit.

Promotion requires a matched evaluation such as:

| Arm | Council | Smart evidence |
|---|---|---|
| A | off / direct analysis | off |
| B | off / direct analysis | on |
| C | Council vNext | off |
| D | Council v3 | on |

The incremental Council-v3 smart-evidence estimand is:

\[
\tau_{smart|Council} = E[Y_D - Y_C].
\]

The interaction estimand is:

\[
\tau_{interaction}
=
(E[Y_D-Y_C])-(E[Y_B-Y_A]).
\]

Primary outcomes should include independently validated load-bearing defects found, false findings, target-module confirmation rate, challenge recall, source/evidence overlap, tool calls, tokens, latency, total cost, and cost per validated finding.

Null and negative results must be retained. Council v3 remains optional until prospective matched-budget evidence justifies broader promotion.
