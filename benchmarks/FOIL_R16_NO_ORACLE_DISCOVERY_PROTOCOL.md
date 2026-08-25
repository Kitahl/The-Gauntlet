# FOIL R1.6 — no-oracle discovery pilot protocol

Status: **PREREGISTERED; UNRUN**

This protocol asks whether one narrow execution-class route can discover useful
arithmetic obligations without receiving benchmark gold, and whether its
per-operator mutation behavior is associated with detection of independently
labelled historical natural misses. It is a smoke experiment, not calibration,
promotion evidence, frontier-model recall, or general prose formalization.

## Frozen implementation boundary

- Base commit: `a584602c0bb976429b3c8fe309bfeeeb604a9090`.
- Route: `gsm8k.annotated-arithmetic.v1`.
- Default policy: disabled.
- Request fields, exactly: `task_text`, `a0_text`, `task_digest`, `a0_digest`.
- Enablement is a separate typed policy, never an input field.
- Unknown request fields are rejected, including gold, correctness labels,
  expected outputs, and answer-bearing benchmark metadata.
- The route emits `FOUND`, `PARTIAL`, `ABSTAIN`, or `UNSUPPORTED` in a
  content-addressed `GENERATED_UNADMITTED` envelope.
- It may emit exact-arithmetic, numeric-provenance, and final-consistency
  obligations. It does not call a model/provider/network, mutate A0, write a
  profile, execute an action, or change promotion state.
- The only production bridge is `compile_admitted_discovery`, which requires the
  existing independent `FormalizationAdmissionReceipt`. R1.6 has no such receipt.
- Benchmark evaluation is explicitly `UNADMITTED_DISCOVERY_BENCHMARK_ONLY` and
  cannot route, repair, execute, or promote.

Changing scorer-side gold while question and A0 remain fixed must not change the
envelope. Changing A0 must change the bound envelope digest. A0 identity and
digest must be preserved on every evaluation.

## Pinned public source

- Repository: `openai/grade-school-math`.
- Commit: `3101c7d5072418e28b9008a6636bde82a006892c`.
- File: `grade_school_math/data/example_model_solutions.jsonl`.
- File SHA-256:
  `4bc62db838f8418365d51c627bd66294cbdca9fb7f01519cb13f0dce8c51580b`.
- Selection seed: `20260824`.

The source has four historical model responses for each of 1,319 questions. The
runner accepts the exact closed source schema and digest only. Raw question,
response, and gold text are not committed or retained in the final report.

## Frozen seven-operator mutation set

Eight distinct hash-ordered gold solutions with at least three parseable
annotations and support for every operator are selected before scanning. Every
row attempts every operator; the runner aborts rather than backfilling after an
outcome is observed.

| Operator | Class | Transformation |
|---|---|---|
| `M1_RESULT` | `RESULT` | Corrupt the first declared calculation result while preserving its expression. |
| `M2_FINAL` | `FINAL` | Corrupt only the final `A:` value. |
| `M3_OPERAND` | `OPERAND` | Corrupt the first eligible literal operand while preserving its declared result. |
| `M4_DROPSTEP` | `DROPSTEP` | Remove a contributing step, bypass its result with its first input, and recompute downstream annotations/final. |
| `M5_SWAPOP` | `SWAPOP` | Swap the first eligible binary operator while preserving its declared result. |
| `M7_CONSISTENT` | `CONSISTENT_LOCAL` | Rewrite the final eligible operation and recompute its result/final consistently. |
| `M9_CONSISTENT_BIG` | `CONSISTENT_GLOBAL` | Replace a prompt-derived root with another prompt quantity and recompute the chain. |

Each attempt is exactly one of `EXECUTED`, `EQUIVALENT`, `INVALID`, or
`UNSUPPORTED`. Attempted must equal the sum of those statuses globally and per
operator. Only `EXECUTED` rows enter kill-rate denominators. Up to 56 mutants may
therefore execute.

## Frozen natural-miss curation

Wrong official responses are distinct-question and ordered by
`SHA256(seed, question_digest, model_variant, response_digest)`. Before any
scanner execution, an independent reviewer labels the first causal divergence:

- `RESULT`, `FINAL`, `OPERAND`, `DROPSTEP`, `SWAPOP`,
  `CONSISTENT_LOCAL`, or `CONSISTENT_GLOBAL`;
- `UNMAPPED` for ambiguous, compound, unsupported, or unsafe-to-force cases.

The target is two distinct-question misses per mapped class (maximum 14). Review
stops after the first 60 hash-ordered candidates or when all quotas are filled.
No case is replaced based on scanner output. Fourteen distinct correct controls,
balanced across the four source variants to within one, are selected with no
question overlap.

FOIL receives only question and response text. Gold, `is_correct`, and primary
class remain scorer-side until all predictions are frozen.

## Frozen analysis

Every class rate reports its numerator, denominator, estimate, and named
two-sided Wilson 95% interval. The association uses only classes with natural and
valid-mutant support.

Primary: Spearman correlation with an exact two-sided permutation p-value.
Descriptive sensitivity: Pearson correlation. Both are reported only if at least
three common classes exist and both rate vectors have non-zero variance.
Otherwise the typed result is `NOT_IDENTIFIABLE` with explicit reason codes.
An estimable result remains `ESTIMABLE_SMOKE_ONLY`.

## Freeze, score, verify

1. Commit this protocol, scanner, verifier, admission bridge, seven operators,
   runner, and tests before scoring.
2. Record that exact commit as `protocol_commit`.
3. Download and digest-check the public source once.
4. Materialize the 60-row curation pack and freeze labels before scanner use.
5. Freeze scanner predictions, then join scorer-only labels.
6. Persist hash-only raw rows, rederive all rates and association independently,
   and bind the report by digest.
7. Run focused tests, compile-all, the complete suite, lint, and parser security
   checks before delivery.

Runtime/provider/model/external-bot calls, token spend, FOIL answer mutations,
profile writes, execution authorizations, and promotion changes are all fixed at
zero. The single allowed network operation is the pinned source download.
