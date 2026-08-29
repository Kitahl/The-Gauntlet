# Math Foundry post-benchmark hardening candidate 2

Authority: `ENGINEERING_ZERO_CREDIT`.

This candidate is a descendant of `math-foundry-formal-plane-candidate.1`. It is **not** the package under the running blind benchmark and does not alter that benchmark arm.

Changes:

1. `math_foundry_isolated_qualification_runner.py` enforces a fresh copied source root for every suite when `suite_isolation_required=true`. Generated qualification artifacts are excluded from the source copy and may cross suite boundaries only through explicit `produces` / `requires_artifacts` declarations with SHA-256 binding and producer-suite provenance.
2. `MATH_FOUNDRY_POSTBENCH_CANDIDATE_2_QUALIFICATION_MANIFEST.json` declares the previously implicit dependencies used by method-realization red-team and method-loop scoring suites, eliminating hidden shared-root ordering assumptions.
3. `math_foundry_v301_representation_tribunal_postbench_selftest.py` retains the original representation-tribunal cases and acceptance criteria but raises only the outer test execution budget for the exact-small LP route from 5 to 20 seconds. This avoids a load-sensitive ~0.31-second internal subprocess slice without changing production search semantics.
4. `math_foundry_exec/trusted_base_minimality.py` can verify exhaustive global minimality **only within an explicit finite trusted dependency universe**, under an independently registered dependency-checker receipt. Missing subset coverage or any `UNKNOWN` result blocks the bounded-global-minimum claim.
5. `math_foundry_postbench_hardening_selftest.py` provides direct negative controls for incomplete search, smaller proving bases, self-verification, qualification-root contamination, forged source-root generated artifacts, and hash-bound explicit artifact staging.

Non-claims:

- no automatic semantic-equivalence oracle;
- no unbounded/global minimal proof-basis theorem;
- no external Lean/MathForm/Pantograph runtime qualification;
- no release or Supernova promotion.
