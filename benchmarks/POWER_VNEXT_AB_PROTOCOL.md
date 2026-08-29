# Power vNext A/B Benchmark Protocol

## Purpose

Compare the exact pre-upgrade Power runtime from the validated Space base against the
final Power vNext runtime on a frozen deterministic mechanism-conformance and
adversarial-discrimination suite.

This is not a general software-correctness or repair-efficacy benchmark.

## Pinned revisions

- OLD revision: `01c07faf1848284bda3c13d1c1eec972629be9c4`
- OLD `tools/power_runtime.py` Git blob: `5b2c0e6f06df99bac77973f70485cd3c465729e4`
- NEW revision: `b8e6557253a642ccc85d27a22c79241256eb3f9b`
- NEW `tools/power_runtime.py` Git blob: `99f5b955b782b61ccaa5fa481ecd347963c3a35a`

The harness recomputes Git blob identities before running. Drift aborts the benchmark.

## Frozen cases

### Shared controls — 10

1. clean compile clears;
2. syntax failure issues;
3. custom command remains disabled without outer opt-in;
4. dangerous Python module flag is refused;
5. arbitrary Python module execution is refused;
6. missing mandatory tool is unavailable;
7. untrusted executable is refused;
8. timeout remains unknown with hashed partial output;
9. issue outranks unavailable;
10. unavailable outranks unknown.

The tenth case is a shared-behavior regression: the pre-upgrade implementation orders
`UNKNOWN` ahead of `UNAVAILABLE`; vNext must preserve the stronger capability failure.

### vNext discriminators — 12

1. duplicate semantic failure hypotheses are rejected;
2. task/scope binding fails closed;
3. substantial-change minimum cannot silently omit regression verification;
4. a killed mutation is positive discriminator evidence;
5. a surviving mutation blocks “fixed”;
6. a real in-repository Python entrypoint executes;
7. a Python entrypoint resolving outside the repository root is refused and not run;
8. metamorphic failure is relation-scoped;
9. task-artifact and agent-harness origins remain distinct diagnostic candidates;
10. oracle changes change check evidence identity;
11. repair self-certification is rejected;
12. independent dual verification can become committable without granting execution.

Unsupported old-version mechanisms do not receive synthetic passes.

## Score

The report contains separate shared, vNext, and total pass counts for OLD and NEW,
plus per-case observed values. The benchmark succeeds only when NEW passes every frozen
case.

## Run

```bash
python benchmarks/harness/bench_power_vnext_ab.py
python -m unittest tests/test_power_vnext_ab_benchmark.py -v
```

## Claim boundary

A higher score demonstrates stronger behavior only on these frozen mechanical cases.
It does not establish exhaustive correctness, benchmark efficacy, real-world repair
success, or production reliability.
