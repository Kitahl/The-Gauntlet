# BASTION-01 common runtime engineering contract

## Purpose

Provide one machine-readable protocol across the research software without pretending that different epistemic obligations are interchangeable.

## Required layers per component

| Layer | Requirement |
|---|---|
| SPEC | Exact obligation, scope, entry/exit conditions, authority boundary |
| STATE | Typed state sufficient for the mechanical part of the method |
| ACTION | Actual evidence-producing computation/search/test/review |
| RECEIPT | Content-addressed record of action, inputs, outputs, verifier, provenance, limits |
| VERDICT | Scoped `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE` |

## Receipt invariants

A receipt must not claim more than the verifier observed. Receipt `content_hash` establishes byte/schema integrity only; it is never semantic entailment. It should contain hashes rather than raw generic content where hashes are sufficient. When the evidence itself is a file/proof/log, the receipt references its artifact and content hash.

## Independence

Independence is represented by provenance, source lineage, verifier identity, model/tool identity, and evidence overlap. No boolean `independent=true` field is sufficient on its own.

## Monitorability

Every automated Aegis check (technical route: Gauntlet) declares which typed
events/state it requires. If an operation is triggered but the typed state
needed to discriminate it is absent, the monitor returns `UNKNOWN` or
`UNAVAILABLE`; absence of the trigger itself is a scoped `UNKNOWN` result whose
reason begins `not-applicable:` — nothing was checked, so nothing is cleared. It
must not silently convert missing observability into a negative finding.

## Versioning

Schema identifier: `egrt.runtime.v1`. Breaking changes require a new schema identifier and migration note.
