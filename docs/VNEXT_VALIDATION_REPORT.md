# The Gauntlet vNext typed-runtime validation report

Baseline: `Kitahl/The-Gauntlet` `v0.5.0`, commit `ba03be52588a81356540611c792726db3f0e874d`, tree `0b9ecde6df507efc35a4f8c44b91261f755c81d9`.

## Scope

This report covers the **pre-benchmark vNext candidate overlay** that turns Soul, Gauntlet, Meditate, Council, Mind, Space, Reality, Power, and Time into a common typed runtime. FOIL remains the existing adaptive-routing/profile subsystem and is connected through a narrow typed bridge. Mastermind remains external and is not imported, hooked, stored, or required by this repository runtime.

The candidate is not a claim of behavioral efficacy. It establishes implementation mechanics and falsifiable boundaries so later empirical ablations can be preregistered against a frozen mechanism.

## Frozen shared contract

Every component exposes:

1. `SPEC` — owned epistemic obligation.
2. `STATE` — typed machine-readable task/decision/review/verification state.
3. `ACTION/TOOL` — actual evidence-producing operation.
4. `RECEIPT` — content-addressed record of inputs, outputs/hashes, evidence, verifier/tool, scope and unresolved state.
5. `VERDICT` — scoped `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE`.

Generic hooks do not persist raw prompts or generic raw tool output.

## Mechanical validation completed

### Typed runtime unit suite

Command:

```bash
PYTHONPATH=tools python -m unittest tests/test_egrt_runtime.py -v
```

Result: **39/39 PASS**.

Coverage includes:

- private state and receipt integrity/tamper rejection;
- configured-state-directory support;
- Soul module ownership, latest-valid-receipt semantics and release blocking;
- privacy-preserving hook aliases and Stop gating;
- Meditate trigger/VOC/ordinal boundaries;
- Council skeptic, commit/reveal integrity, cross-critique, artifact/budget-matched DIRECT control;
- all ten Gauntlet operations and partial-observability semantics;
- Mind exact arithmetic/resource limits and missing SMT encoding behavior;
- Space deduplication/saturation and retrieval-vs-source-assessment separation;
- Reality requirement for stored cleared Space assessment evidence;
- Power no-shell execution, defect-class coverage and custom-command opt-in;
- Time paired inference plus strict exclusion/contamination handling;
- evidence-ledger typed-receipt integrity.

### Candidate structural/integration validator

Command:

```bash
python validation/validate_vnext_runtime.py
```

Result: **27/27 PASS**.

It verifies runtime/spec presence, schema/privacy configuration, hook wiring, `SKILL.md`-only skill directories, runtime traceability from specifications, absence of Mastermind runtime/control imports, five-layer contract, four verdicts, integrity-vs-entailment boundary, stable portability gate, and key Space/Council/Meditate/Power/Time/FOIL constraints.

### Syntax/bytecode validation

Command:

```bash
python -m compileall -q tools tests validation
```

Result: **PASS**.

### Patch application validation

The final 54-file patch was applied with `git apply --check` and `git apply` to a fresh copy of the exact v0.5.0 modified-file baseline set. The applied result then reran the typed runtime unit suite (**39/39 PASS**), candidate structural validator (**27/27 PASS**), and `compileall` (**PASS**). This verifies that the delivered patch itself contains the new files and reproduces the validated overlay.

## Validation not claimed locally

The local candidate is an overlay, not a complete checkout of every unchanged v0.5.0 file. Therefore the existing whole-repository suite, CodeQL, full-history Gitleaks, pip-audit/lock regeneration, and Linux/Windows/macOS GitHub Actions matrix have **not** been re-certified on this candidate yet.

`ruff` was not installed in the local execution environment, so the Ruff gate is also **not locally claimed**.

The correct next release-engineering step is: apply this patch to a branch created from the exact baseline, run the repository's full CI/security/portability gates, inspect failures, then merge only if the exact candidate commit passes. No behavioral benchmark should be used to tune the mechanism before that implementation freeze.

## Soundness boundaries preserved

- A receipt hash proves integrity, not semantic entailment.
- Space retrieval results alone never clear a factual discovery obligation; source assessment is separate.
- A solver receipt proves only the supplied formal encoding unless English-to-formal correspondence is separately verified.
- Council completion does not prove Council is better than DIRECT; later matched-budget empirical comparison is required.
- Council overlap metrics diagnose common causes; they do not prove statistical independence.
- Meditate numeric VOC is used only with a common supplied current decision utility and complete outcome/cost models; otherwise the method is explicitly heuristic/unknown.
- Power never invokes a shell and records hashes rather than generic raw output.
- Time's initial inference path is fixed-n and explicitly not anytime-valid under repeated peeking.
- FOIL can clear only an `ADAPTATION` routing obligation through the typed bridge; it cannot create factual warrant for other obligation classes.
- Mastermind is not a runtime dependency or control path.

## GitHub/ruleset wiring change

`Runtime portability` no longer uses workflow-level path filters. The Linux/Windows/macOS matrix runs on every PR/push to `main`, followed by one stable `Runtime portability gate` job. This is intended to be the required ruleset check, avoiding GitHub's skipped-path/required-check deadlock class.
