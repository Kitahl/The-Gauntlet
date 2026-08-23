# Power / Engineering Verification — engineering specification

## Obligation

Convert software claims into an explicit verification plan and executable checks with named failure-class coverage.

## Current workflow

Specification requires actual repository inspection, minimal complete edit, targeted/regression checks, real entrypoint execution and out-of-gate failure-class accounting.

## vNext state

`VerificationPlan(system_boundary, claim, invariants, checks[])`.

Each check specifies command argv, kind, expected exit, timeout, mandatory flag and defect classes.

## vNext workflow

1. Define claim/system boundary/invariants/failure model.
2. Select checks because they observe named failure classes.
3. Feature-detect tools; absent mandatory tool -> UNAVAILABLE.
4. Validate a known verifier command shape, then execute with `shell=False` and timeout. Arbitrary `custom` commands are disabled unless the outer environment explicitly sets `EGR_POWER_ALLOW_CUSTOM_COMMANDS=1`.
5. Persist exit/timing/stdout-hash/stderr-hash, not generic raw output.
6. Mandatory failure -> ISSUE.
7. All mandatory checks clear -> CLEARED only for named check/coverage scope.
8. Report coverage matrix and one plausible outside-gate class.
9. Add property-based, mutation, static/security and formal checks when diagnostic, not for badges.

## Initial tool leads

Existing tests/Ruff/CodeQL plus optional Hypothesis, mutmut and Semgrep when installed/configured.

## Runtime

`tools/power_runtime.py`
