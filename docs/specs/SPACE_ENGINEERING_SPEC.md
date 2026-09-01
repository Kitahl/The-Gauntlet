# Farfield / Space — Research Discovery Array specification

## Obligation

Find and verify reusable prior art/current evidence before novelty or absence claims, with an auditable search scope and explicit stopping state.

## Current workflow

Specification is multi-stage and provenance-aware; executable helper is a bounded OpenAlex lookup.

## vNext state

`SearchPlan(question, ordered queries, sources, inclusion, exclusion, max_results_per_query, max_queries, saturation_queries)` plus per-query result/provenance/error state. Exact repeated queries are not used as fake “new rounds.”

## vNext workflow

Retrieval is deliberately separated from factual warrant: `multi-index-retrieval` remains `UNKNOWN` even when candidates are found. A second `source-assessment` receipt can clear the DISCOVERY obligation only after one or more source artifacts are inspected, content-hashed, scoped, and classified as `SUPPORTS` or `REFUTES`.


1. Translate question into mechanism/capability queries.
2. Freeze query/source budget.
3. Search OpenAlex + Crossref initially; adapters are explicit/feature-detected.
4. Deduplicate primarily by DOI/OpenAlex ID, then normalized title.
5. Record only hashes/minimal metadata in generic state; preserve selected source artifacts separately when needed.
6. Track novel-result yield by round.
7. Stop on registered budget/saturation, not arbitrary model confidence.
8. Return `SEARCH_COMPLETED_WITH_RESULTS`, `NOT_FOUND_WITHIN_SCOPE`, or `SEARCH_UNAVAILABLE`.
9. Never convert `NOT_FOUND_WITHIN_SCOPE` to proof of nonexistence.
10. Future adapters: OpenCitations/citation chasing, ASReview-style screening, author/cluster expansion.

## Runtime

`tools/space_runtime.py`

## Mechanical tests

- dedup stable across source IDs;
- unavailable adapter explicit;
- all-source failure -> UNAVAILABLE;
- zero results within completed scope -> UNKNOWN + absence boundary;
- saturation state recorded.
