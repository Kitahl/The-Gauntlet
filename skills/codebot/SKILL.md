---
name: codebot
description: Verify — engineering verification module for Strong Inference. Trigger: /power, /codebot, implement, debug, integrate, test, benchmark software behavior, review architecture, or verify an executable claim. Converts software claims into runnable checks and preservation obligations.
---

# Verify

Executable claims should be executed.

## Workflow

1. Inspect the actual repository/artifacts before proposing edits.
2. State requirements, interfaces, invariants, failure model, and compatibility constraints.
3. Map each edit to an obligation.
4. Implement the smallest complete change.
5. Run targeted tests plus relevant regressions.
6. Exercise the real entrypoint, not only internal functions.
7. Check environment/integration failure classes outside unit-test scope.
8. Report what was and was not executed.

## Correctness obligations

Depending on the system, inspect:

- state ownership/lifetime;
- notification/reactivity semantics;
- atomicity/idempotency/retry behavior;
- concurrency and ordering;
- persistence/recovery;
- authorization and least privilege;
- input validation and output encoding;
- resource ceilings and timeouts;
- backward compatibility and migration.

## Verification boundary

A green unit suite certifies only those tests. Before "fixed" or "verified", name at least one plausible relevant failure class outside the gate set or justify why the scope is exhaustive.

Use linters/type checkers/static analysis/fuzzing/security scans/formal tools where they are diagnostic of the claim, not for badge collection.

## Typed runtime contract

`tools/power_runtime.py` executes explicit verification plans with `shell=False`, timeouts, mandatory/optional checks, output hashes and named defect-class coverage. A green plan is scoped to the checks/coverage represented in its receipt. Missing mandatory tooling is `UNAVAILABLE`. See `docs/specs/POWER_ENGINEERING_SPEC.md`.

## Compatibility

Public product name: **Verify**. Stable technical identity: `codebot`; stable commands include `/power` and `/codebot`. **Engineering Verification** is the legacy public label retained in historical documentation and receipts.
