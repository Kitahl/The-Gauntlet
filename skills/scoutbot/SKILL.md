---
name: scoutbot
description: Research Discovery module. Trigger: /space, /scoutbot, prior art, literature search, current facts, existing tools, repositories, standards, or "has this been done?". Finds and verifies reusable work before new design.
---

# Research Discovery

Search before novelty and before absence claims.

## Discovery protocol

1. Bind the work to the current dependency-ready `DISCOVERY` obligation.
2. Translate the request into mechanisms/capabilities, not only project vocabulary.
3. Freeze base queries, adapters, scope, budgets, and any query hypotheses before outcomes.
4. Search primary/official sources first when possible.
5. Expand through synonyms, representations, neighboring fields, authors/projects,
   citations, repositories, implementation terms, versions, and standards.
6. Inspect the source passage or repository, not only search snippets.
7. Record license, version/date, guarantee class, provenance, fidelity limits, and transport
   constraints.
8. Keep retrieval, source assessment, novelty, proof, engineering, and evaluation as
   separate obligations.

## Typed retrieval diagnosis

The runtime can register these query classes:

- `TERMINOLOGY_MISMATCH`
- `REPRESENTATION_MISMATCH`
- `SOURCE_ADAPTER_GAP`
- `QUERY_TOO_NARROW`
- `QUERY_TOO_BROAD`
- `NEIGHBOR_FIELD_MISSED`
- `CITATION_CHAIN_NOT_TRAVERSED`
- `DERIVATIVE_SOURCE_COLLISION`
- `STALE_SOURCE`
- `TRUE_NOT_FOUND_WITHIN_REGISTERED_SCOPE`

After load-bearing zero yield, Space automatically attempts at most one frozen,
non-redundant mechanism-level reframe in challenge `shadow`/`enforced` mode. The round
records task, obligation, plan, parent query hash, challenge ID, query class, scope hash,
adapter status, and novel yield. An exact normalized repeat is rejected and cannot count as
a new round. Saturation is evaluated after the reframe.

Challenge mode `OFF` preserves baseline frozen search without executing the
challenge-derived reframe.

## Source hierarchy and independence

Prefer:

1. official specifications, primary papers, and original repositories;
2. maintained documentation and archival/version records;
3. high-quality secondary synthesis;
4. community discussion for experience signals, clearly labeled.

A source count is not independence. Content-identical artifacts and artifacts sharing a
provenance group form one independence group. Derivative/mirrored copies remain visible but
do not add independent support. Support/refutation conflicts, claim-scope splits, and
provenance/derivative collisions create neutral `SOURCE_CONFLICT` challenges.

## Absence and novelty boundary

`NOT_FOUND_WITHIN_SCOPE` means the registered search scope found nothing. Even after one
successful non-redundant reframe, it remains `UNKNOWN` for global nonexistence.

Before novelty credit, provide:

- registered search scope and adapter availability;
- nearest established class;
- concrete differentiator;
- whether the delta is mechanism, assumption, interface, guarantee, or merely
  packaging/renaming;
- inspected, content-addressed source-assessment receipts.

Retrieval candidates alone do not clear a factual claim. A separate `source-assessment`
receipt is required, and that receipt authorizes only the recorded scoped support/refutation.

## Automaticity and authority

Soul may automatically route Space when a `DISCOVERY` obligation is dependency-ready.
Space remains `DISCOVERY_ONLY`: it cannot clear another module's obligation, and a challenge
proposal/resolution never substitutes for target-domain evidence. Model/reviewer agreement
is advisory, not factual authority.

## Typed runtime contract

`tools/space_runtime.py` implements typed multi-index retrieval, query-hypothesis lineage,
one bounded automatic reframe, explicit adapter failure, DOI/identity deduplication,
source-conflict challenges, and provenance-aware independence grouping. OpenAlex and
Crossref are initial adapters. `tools/scout.py` remains an optional keyless OpenAlex helper.

See `docs/specs/SPACE_ENGINEERING_SPEC.md`.
