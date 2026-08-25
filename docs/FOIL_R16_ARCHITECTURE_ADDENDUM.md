# FOIL R1.6 architecture addendum

Status: **implemented, default off, generated route unadmitted**

This addendum supersedes earlier statements that FOIL ships no generator at all.
FOIL ships one narrow execution-class generator family. R1.6's
`gsm8k.annotated-arithmetic.v1` is frozen for reproducibility. R1.7 adds the
separately versioned `gsm8k.annotated-arithmetic.v2`, whose provenance records
cover exact fractions, percentages, bounded lexical ratios, identity/unit
multipliers, and mechanically rederived one-step relations. Neither route is a
general natural-language formalizer, and neither has production calibration or
admission evidence.

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
It accepts only a `FOUND` envelope and an existing independent
`FormalizationAdmissionReceipt`; it cannot create evidence or grant authority.
R1.6 and R1.7 evaluate unadmitted envelopes only in their named benchmark paths.

This architecture deliberately leaves two problems unsolved: discovering
unannotated load-bearing prose claims, and calibrating extraction fidelity/recall
for production. Neither may be inferred from R1.6 smoke results.
