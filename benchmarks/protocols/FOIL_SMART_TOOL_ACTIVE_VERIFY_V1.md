# FOIL Smart-Tool Active VERIFY v1

**Frozen:** 2026-08-28
**Status:** IMPLEMENTED / BENCHMARK-ONLY / UNPROMOTED
**Scope:** FOIL standalone. No Gauntlet or Mastermind merge or control path.

## Question

Can FOIL actively run one bounded, task-relevant tool after a question-only
applicability probe, account for its complete prelaunch cost, and improve a
frozen answer without granting unsupported evidence production authority?

## Frozen mechanism

1. The route opportunity probe reads only the task identifier and question.
2. The active v1 controller exposes three families: exact computation,
   restricted numeric execution, and read-only retrieval.
3. A family-specific applicability probe must accept the task.
4. A Jeffreys-Beta value gate uses counted route evidence when it exists. A
   benchmark may explicitly explore an uncalibrated route; production may not.
5. The caller supplies the token budget. Every token-consuming call is reserved
   before launch and must have a provider-enforced cap.
6. Exactly one tool may run. There are no retries or tool bundles in v1.
7. Mechanical output is `BENCHMARK_CORRECTIVE_UNADMITTED`. It may change a
   benchmark prediction only with explicit harness opt-in. Retrieval remains
   `SUPPORT_ONLY` and cannot replace A0.
8. The shared benchmark finalizer preserves A0 on invalid evidence, accounting
   failure, tool error, timeout, over-budget work, or absent benchmark opt-in.

## Implemented tests

- Closed ToolContract, ToolCost, ToolReceipt, and EvidenceEnvelope schemas.
- Cost and digest conservation; one-tool and zero-retry bounds.
- Question-only routing independence from A0 and hidden gold.
- Exact arithmetic and restricted Python-output parsing.
- Retrieval source and token receipts, with support-only admission.
- Jeffreys-Beta lower/upper bounds, freshness, minimum evidence, difficulty
  separation, non-positive value, and caller-budget decline.
- Active VERIFY execution (`shadow_only=false`), safe default stand-down, A0
  preservation, and report hashing.

## Sealed diagnostic artifacts

`smart_tool_integration_v1` is synthetic integration data. It contains 12
mechanically traceable fixtures, four per family. Frozen predictions scored
9/12 versus a 3/12 supplied A0 baseline, with six rescues, zero damages, 12
single-tool calls, and 60 fixture provider-token units. This proves wiring and
authority behavior only; it is not an HLE or generalized-efficacy result.

`smart_tool_hle_replay` is a zero-provider historical development replay. Of 60
source rows, 59 contain a usable A0 and one is explicitly omitted. It preserved
11/59 correct answers, made zero rescues and zero damages, and actively ran the
exact-computation route on 3/59 rows at zero tokens. Repeated configurations are
not independent questions, retrieval was unavailable, and this is not a new
holdout.

## Promotion and non-claims

This mechanism is default-safe, benchmark-only, and unpromoted. It does not
establish that route evidence transfers to unseen traffic, that retrieval
improves HLE, that tool bundles are useful, or that the 22/60 engineering target
is achievable. A matched new holdout with a real bounded retrieval provider is
required before any efficacy or production claim.
