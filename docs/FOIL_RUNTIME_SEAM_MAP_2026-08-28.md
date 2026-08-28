# FOIL runtime compatibility and seam map — 2026-08-28

Status: pre-implementation audit. This document maps live code at
`38ddc6abe29a32c49c7cdb646ae140dc199792df`; it is not an efficacy claim.

## Scope and verified starting state

- Repository: `foil-persona-validation`
- Branch: `codex/foil-persona-validation`
- HEAD: `38ddc6abe29a32c49c7cdb646ae140dc199792df`
- Tracked worktree: clean at audit start
- Pre-existing untracked state: `handoff/` only; preserved and excluded from
  graph extraction, runtime inputs, and benchmark gold access
- Remotes: local-path `origin` and GitHub `github`; no push is authorized
- Authority boundary: FOIL only. Gauntlet, Mastermind, repository-librarian,
  and external/free bots are outside this work.

## Graph evidence and limitations

Graphify was run deterministically over 274 Git-tracked code files only, with
directed AST edges and no semantic/model extraction. The untracked `handoff/`
corpus and tracked result documents were excluded from extraction. The graph
contains 5,167 nodes, 14,558 directed edges, and 230 communities.

The graph health gate reports no missing endpoints or self-loops, but it does
report 2,063 dangling-endpoint edges and 571 directed same-endpoint collapses.
Accordingly, graph paths are discovery evidence only. Every load-bearing edge
below was confirmed by reading the referenced code.

## Live path and required seam changes

| Seam | Live implementation | Verified behavior | Required additive change |
|---|---|---|---|
| Benchmark entry | `benchmarks/harness/foil_evidence_closed_hle10.py` | Reuses historical A0, batches ten questions into one constructor call, exposes only web search, then performs two batched comparator calls. | New sealed harness: ten fresh hash-selected items, one fresh A0 call and one independent active FOIL row per item, persist-before-print, scorer-only gold after frozen prediction hashes. |
| Task-only opportunity | `tools/foil_route_opportunity.py:discover_route_opportunity` | Closed `schema/task_id/question` input rejects A0/gold fields and emits reasoned candidates. Exact arithmetic is conflated with `SYMBOLIC_COMPUTATION`; coverage gaps are named `UNSUPPORTED`. | Add a typed v2 opportunity with complexity, exactly four runtime families, `COVERAGE_GAP`, cheapest-first ordering, and no answer/correctness inputs. Preserve v1 parsing and persisted values. |
| Tool contract | `tools/foil_tool_contract.py` | Closed digested v1 contract and receipt; three broad families, four operations, one-call/no-retry. Retrieval receipts keep URL and evidence digest but not passage/offsets. | Add v2 closed contracts for exactly `EXACT_ARITHMETIC`, `RESTRICTED_PYTHON`, `SYMBOLIC_COMPUTATION`, and `PASSAGE_RETRIEVAL`; typed failures, origins, timeouts, resource envelopes, raw boundary receipts, passage identity, offsets, and digests. Default-deny unknown fields/operations. |
| Active adapters | `tools/foil_smart_tool_runtime.py` | Implements exact rational arithmetic, a tiny `print(expr)` Python subset, and callback retrieval; no independent symbolic family. Retrieval result has text and URLs but its receipt loses exact passage binding. | Implement four v2 adapters. Generated Python/symbolic specs require admitted formalization; deterministic exact arithmetic does not. Retrieval must fetch passage text rather than accept search snippets. |
| Token ledger | `tools/foil_benchmark_budget.py:BenchmarkTokenLedger` | Hard aggregate cap plus provider-enforced reservations. | Add aggregate-unbounded benchmark accounting with finite per-call/per-route reservations, empirical expected-cost/value fields, and settlement conservation. No 250k global cancellation and no `NOT_RUN_BUDGET`. Keep the legacy capped constructor compatible. |
| Generated-spec admission | `tools/foil_formalization_admission.py` | Route-calibrated, freshness-aware, mutation-checked, instance-bound admission is control-only and never grants execution itself. | Reuse unchanged as the required gate for generated symbolic/Python specs. Record its receipt in the v2 tool contract; reject absent, stale, mismatched, or stand-down admission. |
| Evidence packet | `tools/foil_evidence_contract.py` | `EvidenceDocument` binds HTTPS identity/content digest; `EvidenceSpan` validates exact offsets; `ComputationReceipt` mechanically recomputes rational expressions. Public traces intentionally omit raw passage text. | Retain these validators, add a benchmark raw evidence archive containing fetched passage text before any digest-only public trace, and bind exact/numeric/quoted claims deterministically. |
| Candidate constructor | `tools/foil_bounded_answer_constructor.py` | One pass, question/evidence only, no A0/tools, claim bindings required. It always requires an output-token cap and converts all runner exceptions into a zero-token `ERROR`. | Add optional provider-enforced output bound; no artificial answer-length cap. Persist prompt, evidence IDs, raw answer, origin, full token receipt, and typed provider failure without fabricating zero cost. |
| Symmetric comparator | `tools/foil_retrieval_claim_comparator.py:compare_candidate` | Same function evaluates A0 and B. Semantic callback sees only one claim and common spans. Exact computation/span equality is mechanical; semantic authority can be configured as calibrated or uncalibrated. | Add hidden randomized candidate labels at the harness boundary and deterministic exact/numeric/quoted contradiction checks. Uncalibrated semantic results are `SUPPORTING_ONLY`/`UNRESOLVED` and never selection-eligible. |
| External selector | `tools/foil_answer_selector.py:select_answer` | Preserves A0 unless B is fully supported/eligible, A0 has a critical contradiction, and benchmark selection is explicitly enabled. Production authority is impossible. | Retain this safety law. Extend receipt origin/identity conservation and require the same evidence packet/authority policy for both assessments. |
| Active route finalization | `tools/foil_adaptive_executor.py` and `tools/foil_evidence_closed_runtime.py` | DIRECT skips runner; VERIFY/FULL can execute. The evidence runtime catches broad `Exception` and returns A0 with a generic reason and incomplete accounting. | New v2 outcome enum: exactly one of DIRECT, COVERAGE_GAP, VERIFY_RESOLVED, FULL_RESOLVED, PRESERVED_A0, or typed ERROR. Catch only at named external boundaries; configuration/import failures fail preflight. One item failure cannot cancel another. |
| Final output | legacy harness `run/score/audit` | Raw provider streams are persisted, but the failed run prints after batch stages and does not produce an independent per-item end-to-end conservation record. | Persist each item receipt atomically before progress output; freeze/hash all predictions before scorer access; independently recompute report and conservation from raw rows. |
| HLE scoring | legacy `normalize()` functions | Whitespace/case folding only; strict and normalized scores are not separate. | Add strict raw equality and a separately reported bounded normalizer for tuple whitespace and one final bounded answer in a short explanation. Reject multiple/contradictory final answers. |

## Governing-plan contradictions and resolutions

1. **Global benchmark ceiling.** Older docs and the initial task text refer to a
   250,000-token caller ceiling and `NOT_RUN_BUDGET`. The later explicit
   correction removes both for this fresh task. Resolution: no aggregate budget
   cancellation or model downgrade; retain per-call/per-route bounds and report
   actual tokens after the run.
2. **Coverage cancellation.** The initial text cancels below 3/10 implemented
   opportunities; the later correction makes replay diagnostic only. Resolution:
   freeze ten items before routing and run all ten. Inapplicable rows produce
   typed `COVERAGE_GAP` stand-downs and remain in the denominator.
3. **Question-only routing versus A0-bound contracts.** The current opportunity
   probe is question-only while later plans/contracts bind A0. Resolution: family,
   applicability, and complexity are frozen before A0 exists; a later contract
   may include the frozen A0 digest only as an integrity/fallback binding and may
   not change the previously frozen frontier.
4. **Generated specifications versus deterministic parsing.** Existing admission
   law requires calibrated admission for external formalizers; simple exact
   arithmetic is deterministically parsed by host code. Resolution: host-derived
   exact parsing is not called generated. Any model-generated symbolic/Python
   operation spec must carry a live admitted receipt or stand down.
5. **Semantic comparison authority.** Existing policy can make an explicitly
   admitted semantic route selection-eligible, while the requested benchmark has
   no newly calibrated semantic comparator. Resolution: semantic judgments in
   this run are advisory only; only deterministic exact/numeric/source-span checks
   can satisfy answer-changing authority.
6. **Constructor output caps.** Existing code requires a configured token cap;
   the benchmark forbids artificial answer-length caps unless provider-enforced.
   Resolution: the new constructor policy accepts no output cap by default and
   records/enforces one only when the preregistered provider configuration proves
   it is enforced.
7. **Fail-safe versus typed failure.** Existing broad exception handling preserves
   A0 but can make a failed route look like a normal stand-down. Resolution:
   preserve A0 as the answer identity while marking the run `ERROR` with boundary,
   typed code, and accounting completeness; configuration/import failures fail
   preflight rather than becoming benchmark successes.
8. **Profile adaptation versus answer routing.** PERSON/profile evidence may adapt
   assistance, but it cannot learn or supply the routing/acceptance verdict for the
   same event. Resolution: the v2 benchmark runtime accepts no profile input,
   writes no profile state, and logs routing evidence separately from any learning
   store.
9. **Exactly ten independent rows versus the previous batch.** The previous
   implementation shared one ten-question constructor context. Resolution: each
   question has its own A0 and FOIL contexts; no question-level exception or
   evidence can cancel or enter another row.

## Compatibility rules

- Implement the new path additively as v2 schemas/modules; do not rename or
  reorder persisted v1 enums.
- Keep production and promotion authority default-off and structurally false.
- Keep A0 raw identity and origin through every preserve path.
- Reject unknown fields and operations at every v2 boundary.
- Route evidence and profile-learning evidence use separate types and stores.
- Search snippets are discovery metadata only; admitted retrieval evidence must
  be a fetched, content-addressed passage with exact offsets.
- Every item and stage has exactly one typed outcome and conservation checks.
- No provider call is allowed until compile-all, isolated contract/fault tests,
  the full existing suite, offline replay, and the real CLI preflight all pass.

## Planned verification gates

1. Closed-schema/property tests for all four families and v2 outcomes.
2. Fault injection for timeout, malformed JSON, unknown field, digest mismatch,
   source fetch failure, passage mismatch, stale admission, token overrun, and
   persistence failure.
3. Adversarial normalized-score tests: tuple spacing accepted; short final-answer
   explanation accepted; multiple or contradictory answers rejected.
4. Per-item and aggregate token/tool/outcome conservation.
5. Offline replay of all route kinds, including `COVERAGE_GAP` and failures.
6. Real CLI prepare/check/replay path before any provider call.
7. Sealed-manifest hash verification, then ten independent paired live rows.
8. Scorer-only gold access after prediction freeze, independent report rebuild,
   complete suite rerun, and no production promotion claim.
