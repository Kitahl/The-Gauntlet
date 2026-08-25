# FOIL R1.6 architecture addendum

Status: **implemented, default off, generated route unadmitted**

This addendum supersedes earlier statements that FOIL ships no generator at all.
FOIL ships narrow execution-class generator families. R1.6's
`gsm8k.annotated-arithmetic.v1` is frozen for reproducibility. R1.7 adds the
separately versioned `gsm8k.annotated-arithmetic.v2`, whose provenance records
cover exact fractions, percentages, bounded lexical ratios, identity/unit
multipliers, and mechanically rederived one-step relations. Neither route is a
general natural-language formalizer, and neither has production calibration or
admission evidence.

The later `math.certified-arithmetic-rule-bank.v1` route moves the P0.5 parser
into production code without widening frozen `certified-v2`. It adds three
separate rules: bounded numeric powers, complete undelimited numeric-equality
lines, and same-line joint affine trace constraints. Trace inconsistency names
the joint obligations only; it does not identify a faulty step or authorize a
repair. Semantic unit/domain rules remain unbuilt because they require
host-typed meaning rather than lexical guessing.

```text
task text + immutable A0 + content digests
                    |
                    v
       closed, default-off discovery request
                    |
                    v
 FOUND / PARTIAL / ABSTAIN / UNSUPPORTED
                    |
                    v
   GENERATED_UNADMITTED task-spec envelope
          |                         |
          | benchmark only          | production
          v                         v
 direct compile + scan       formalization admission
 (no route/action)           receipt required, fail closed
                                    |
                                    v
                            admitted generated route
```

The discovery module parses bounded GSM8K-style `<<expression=result>>`
annotations and one final `A:` field. It emits exact-arithmetic obligations,
operand-provenance obligations using canonical rationals, and final-result
consistency. The verifier registry remains closed and pure.

The request contains exactly `task_text`, `a0_text`, `task_digest`, and
`a0_digest`. Benchmark gold and correctness labels cannot enter this boundary.
The returned envelope preserves the same A0 object and digest, records
`GENERATED_UNADMITTED`, and fixes provider calls, profile writes, execution,
actions, and answer mutation at zero.

`foil_obligation_discovery_admission.py` is the sole intended production bridge.
It accepts only the closed v1/v2/rule-bank envelope set, a `FOUND` result, an
existing independent `FormalizationAdmissionReceipt`, and the exact
`FormalizationRouteBinding`. The receipt, route name, generator configuration,
complete input digest, generated-spec digest, and target schema must all agree.
The bridge cannot create evidence or grant authority. R1.6, R1.7, P0.5, and the
small rule-bank pilot evaluate unadmitted envelopes only in named benchmark
paths.

This architecture deliberately leaves two problems unsolved: discovering
unannotated load-bearing prose claims, and calibrating extraction fidelity/recall
for production. Neither may be inferred from R1.6 smoke results.
