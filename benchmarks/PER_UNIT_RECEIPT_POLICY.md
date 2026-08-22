# Per-unit execution receipt isolation

Status: prospective protocol amendment for the paired BrowseComp-40 and diversity suite.

## Purpose

Each `(benchmark, item, condition)` execution must be writable without reading any sibling-condition output. A shared append-only predictions file is therefore not used during solving sessions.

## Storage rule

Every solving session writes exactly one new receipt to a path that is unique to that execution unit:

`benchmark_runs/2026-08-22/paired_unit_receipts/<benchmark>/<condition>/<item_id>.json`

The solving session must create its own path directly. It must not list, read, fetch, merge, or append any sibling-condition receipt or aggregate prediction file.

A per-unit receipt contains one prediction object and the execution trace required by `benchmarks/EXECUTION_MATRIX_SCHEMA.json`.

## Aggregation rule

Aggregation and scoring occur only in a separate non-solving context after the expected execution matrix is complete. The aggregator may read all per-unit receipts, validate unique isolation session IDs and budgets, construct the aggregate prediction matrix, and then run benchmark scoring.

Partial execution matrices remain unscored. Missing receipts are reported as progress only.

## Historical first-unit exception

The first BrowseComp-40 BASE execution was recorded before this storage amendment in the original aggregate prediction file. That receipt remains frozen and valid. Future solving sessions must not open that aggregate file. At final aggregation, the non-solving aggregator may import that single pre-amendment receipt alongside the per-unit receipts.

## Isolation boundary

This amendment changes receipt storage only. It does not alter the benchmark sample, question text, condition procedures, tool budgets, frozen profiles, answer, or scoring rule for any execution unit.
