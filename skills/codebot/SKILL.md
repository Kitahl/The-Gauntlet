---
name: codebot
description: Engineering Verification module. Trigger: /power, /codebot, implement, debug, integrate, test, benchmark software behavior, review architecture, or verify an executable claim. Converts software claims into runnable checks and preservation obligations.
---

# Engineering Verification

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
