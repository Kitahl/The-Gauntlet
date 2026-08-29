# Space / Research Discovery — engineering specification

## 1. Obligation and authority

Space owns **DISCOVERY** obligations: finding and assessing reusable prior art, current
evidence, repositories, standards, and source conflicts before novelty or absence claims.

Space is claim-native only for discovery evidence. It does not clear PROOF, SYNTHESIS,
ENGINEERING, EVALUATION, REVIEW, ASSURANCE, PREFLIGHT, or ADAPTATION obligations.
A query, challenge proposal, or challenge resolution is not factual evidence. Retrieval
candidates remain `UNKNOWN` until inspected sources are recorded in a separate
`source-assessment` receipt.

## 2. State and compatibility

Runtime: `tools/space_runtime.py`
Schema: `egrt.space.v2`

The additive state objects are:

- `SearchPlan` — frozen base queries, source adapters, scope, budgets, optional current
  task binding, and zero or more pre-outcome `QueryHypothesis` values;
- `QueryHypothesis` — one named retrieval-failure class plus one frozen reframe query;
- `QueryRoundState` — hash-only lineage for each executed or rejected round;
- `SourceAssessment` — one inspected, content-addressed source and its scoped relation.

Existing `SearchPlan` positional construction, `multi-index-retrieval`, and
`source-assessment` action names remain readable. Challenge mode `OFF` restores baseline
search behavior: frozen base queries still run, but challenge-derived reframes are not
executed.

## 3. Typed retrieval diagnosis

`QueryClass` supports at least:

1. `TERMINOLOGY_MISMATCH`
2. `REPRESENTATION_MISMATCH`
3. `SOURCE_ADAPTER_GAP`
4. `QUERY_TOO_NARROW`
5. `QUERY_TOO_BROAD`
6. `NEIGHBOR_FIELD_MISSED`
7. `CITATION_CHAIN_NOT_TRAVERSED`
8. `DERIVATIVE_SOURCE_COLLISION`
9. `STALE_SOURCE`
10. `TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE`

A registered hypothesis binds:

- task revision when supplied;
- DISCOVERY obligation;
- search-plan identifier;
- parent query hash;
- query class;
- frozen reframe query hash;
- optional alternate registered source adapters;
- registered search-scope hash when supplied;
- load-bearing status and metadata hash.

The persisted `QueryRoundState` additionally binds the generated challenge identifier,
reframe outcome, novel yield, adapter availability, and current task/scope hashes. Raw
queries are sent to adapters but are not persisted in generic Space state or receipts.

## 4. Automatic bounded reframe

For a load-bearing, task-bound plan in `shadow` or `enforced` challenge mode:

1. execute the frozen base query;
2. measure novel yield and adapter availability;
3. before applying saturation, locate the first matching frozen `QueryHypothesis`;
4. reject an exact normalized repeat of any frozen/executed base query;
5. create one task/candidate/scope/obligation-set-bound `RETRIEVAL_REFRAME` challenge;
6. select and execute exactly one frozen mechanism-level reframe;
7. record parent query, challenge, class, scope, adapter state, and novel yield;
8. mark the challenge `UNRESOLVED` when source assessment is still required, or
   `UNAVAILABLE` when every registered reframe adapter fails;
9. apply the registered saturation rule only after that reframe result.

At most one automatic reframe is executed per `run_plan` call. An exact repeat is retained
as a diagnostic with `counted_as_round=false`; it cannot inflate query or challenge-round
counts. A challenge budget/configuration failure does not become a fabricated successful
round.

The reframe is frozen before outcomes. Space does not ask a model to improvise an
outcome-conditioned query and then treat it as preregistered evidence.

## 5. Retrieval verdicts

- At least one adapter call succeeds and candidates are found:
  `UNKNOWN / CANDIDATES_RETRIEVED_REVIEW_REQUIRED`.
- At least one adapter call succeeds and no candidates are found:
  `UNKNOWN / NOT_FOUND_WITHIN_SCOPE`.
- Every executed registered adapter/call is unavailable:
  `UNAVAILABLE / SEARCH_UNAVAILABLE`.

After a successful, non-redundant zero-yield reframe, Space may label the bounded diagnosis
`TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE`. That label is still scoped `UNKNOWN`; it is not
a global nonexistence claim.

`run_automatic_discovery` is an explicit alias for Soul-routed execution. Search and
reframe are automatic once the dependency-ready DISCOVERY plan is routed; they are not
manually activated per query.

## 6. Retrieval mechanics

1. Translate the question into mechanism/capability queries.
2. Freeze query, adapter, inclusion/exclusion, and reframe scope.
3. Search OpenAlex + Crossref initially; adapters are explicit and feature-detected.
4. Deduplicate primarily by DOI/OpenAlex identity, then URL/normalized title.
5. Merge adapter provenance without counting the same work twice.
6. Record only hashes and minimal bibliographic metadata in generic state.
7. Track novel-result yield and typed adapter errors by round.
8. Stop on the registered budget/saturation rule, never model confidence.
9. Preserve `NOT_FOUND_WITHIN_SCOPE` as scoped uncertainty.
10. Add future citation, author/project, neighbor-field, repository, and screening adapters
    without changing verdict semantics.

Author/project expansion and citation traversal are complementary query classes, not
proven replacements for keyword/mechanism search. Embedding or semantic similarity is a
retrieval signal, not formal dependency or factual warrant.

## 7. Source assessment and conflict

`assess_sources` requires a valid Space retrieval receipt for the same obligation. Each
assessment binds a content-addressed artifact, verifier, claim scope, relation, and optional
provenance group.

Relations are `SUPPORTS`, `REFUTES`, or `CONTEXT_ONLY`.

Artifacts sharing either content hash or declared provenance are unioned into one
**independence group**. Therefore:

- derivative/mirrored copies remain visible evidence;
- they count as one independent support/refutation unit;
- two derivative copies cannot be reported as two independent confirmations;
- the receipt records group hashes, group sizes, and independent support/refutation counts.

Space creates a neutral `SOURCE_CONFLICT` challenge for:

- assessed support/refutation conflict;
- non-equivalent claim scopes;
- provenance collision;
- derivative-source collision.

A pure derivative collision does not erase a source's scoped relation, but it records an
unresolved independence limitation and, under enforced challenge policy, can block
promotion. Source counts and model/reviewer agreement never become factual authority.
Historical source evidence is retained rather than deleted when a version is stale or
superseded.

## 8. Privacy and provenance

Generic runtime state persists query hashes, source identifiers, minimal metadata,
challenge bindings, and evidence hashes. It does not persist raw queries, prompts, or
unbounded adapter output. Source artifacts are referenced separately through `ArtifactRef`.

A content hash or signed provenance record establishes integrity/lineage, not scientific
truth. A cleared Space receipt means inspected cited evidence supports or refutes one
registered claim scope under the recorded assessment; stronger novelty, efficacy, proof,
or evaluation claims require their own modules and receipts.

## 9. Mechanical tests

Required focused coverage:

- terminology mismatch and novel-yield reframe;
- query reframe parent/challenge/task/scope lineage;
- exact repeat rejected as a fake new round;
- ambiguous duplicate load-bearing reframes rejected;
- source-adapter gap;
- derivative-source collision and independence grouping;
- shared-provenance collision distinguished from byte-identical copies;
- assessed source conflict;
- scoped `NOT_FOUND_WITHIN_SCOPE` after reframe;
- saturation evaluated after reframe;
- all registered adapters unavailable;
- challenge `OFF` rollback behavior;
- raw-query persistence negative control;
- legacy retrieval/source-assessment separation.

Mechanical validation proves implementation behavior and compatibility only. It does not
establish that any reframe taxonomy improves recall or that Space finds all relevant work.
