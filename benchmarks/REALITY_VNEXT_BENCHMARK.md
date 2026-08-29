# Reality vNext mechanical benchmark

## Scope

This benchmark measures the mechanical Reality / Method Synthesis runtime only. It is
an offline deterministic benchmark of admission correctness and runtime cost. It does
not measure global novelty, scientific efficacy, causal mechanism validity, downstream
engineering correctness, downstream benchmark improvement, or search-network latency.

## Executable harness

`benchmarks/harness/bench_reality_runtime.py`

The harness replaces Space network adapters with a deterministic local adapter and then
uses the real Soul task store, Space retrieval/source-assessment receipts, Reality
challenge lifecycle, candidate attack bundle, discriminator selection, and admission
receipt path.

## Correctness matrix

The executable benchmark contains eight cases:

1. supported candidate-bound prior-art non-match -> `CLEARED` for SYNTHESIS-only admission;
2. refuted candidate-bound prior-art non-match -> `ISSUE`;
3. context-only prior-art assessment -> `UNKNOWN`;
4. retrieval without source assessment -> `UNKNOWN`;
5. newer candidate-bound refutation outranks stale caller-selected support -> `ISSUE`;
6. named competing mechanism with explicit A-vs-B discriminator -> `CLEARED` when all other gates pass;
7. named competing mechanism without explicit discriminator -> `UNKNOWN`;
8. missing live-vNext invariants/dependencies -> `UNKNOWN`.

A benchmark run is mechanically successful only when all eight expected verdicts match.

## Runtime metrics

The harness reports milliseconds for:

- `record_candidate_cold`: Reality admission after task and Space evidence setup, including
  Reality-owned state/challenge writes;
- `evaluate_admission_hot`: repeated read-only re-evaluation of an existing admitted
  candidate/bundle;
- `mechanism_signature`: normalized structural mechanism signature calculation.

For each metric it reports sample count, mean, median, p95, minimum and maximum. Signature
calculation also reports operations/second derived from its mean latency.

No performance threshold is a correctness gate. Runtime values are descriptive and may
vary by operating system and GitHub Actions runner load.

## CI execution

`tests/test_reality_benchmark.py` executes the benchmark during normal unittest discovery
and prints one machine-readable line prefixed with `REALITY_BENCHMARK_JSON=`. Therefore
the same benchmark is exercised by the repository validation suite and portability jobs.

## Evidence boundary

A mechanically passing benchmark establishes only that the specified cases behave as
expected on the exercised code and that the measured runtime costs were observed on the
reported runner. It must not be cited as evidence that a synthesized mechanism is novel,
correct, effective, causally valid, or superior to another method.
