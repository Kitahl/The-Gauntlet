# FOIL v5 / Mirror 0.6.0-rc2 validation report

**Date:** 2026-08-24
**Branch:** `codex/foil-v5-full-system`
**v5 base:** `65044e87a150f33383ab670ad06e21bf80194977`
**Release status:** testing candidate; default-off; shadow-only

## Outcome

The RC2 software contract passes its local release gates. The build adds the
adaptive-compute recommendation layer, compiler-bound verifier-route adapter,
default-off observational RouteVector ledger, future formalization/extraction
admission contract, and the sealed three-item development protocol. It also
ports four bounded 0.5.1 robustness repairs without merging branch histories.

FOIL/Mirror, Gauntlet, and Mastermind remain separate. No new RC2 module imports,
controls, installs, trust-promotes, or executes either other system.

## Verification evidence

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | **PASS — 705 tests** |
| Focused adaptive/ledger/pilot suite | **PASS — 39 tests** |
| Pinned Ruff 0.16.3 over changed Python surfaces | **PASS** |
| `python -m compileall -q tools tests benchmarks/harness validation` | **PASS** |
| `git diff --check` | **PASS** |
| `uv run --with playwright==1.62.0 python validation/validate_showcase.py` | **PASS — 33/33 checks**, desktop and 390px mobile |
| Showcase payload | **50,837 bytes**, under the 90,000-byte budget |
| Terra control/reconciliation review | P1 pair-splitting flag interaction found, fixed, regression added |
| Terra controller/ledger review | Forged provenance, permissive receipt schema, raw-field, pooling, mutability, and vacuous stand-down findings fixed |
| Terra pilot review | Pre-call, resume, prediction, raw-stream, source, tool-boundary, privacy, and exact-inventory findings fixed |

The full suite emits one expected negative-control warning while proving that a
missing candidate policy cannot be silently replaced by the reference policy.
The suite still exits successfully.

## Key negative controls

- A caller-fabricated `HostVerifierRoute` cannot recommend VERIFY/FULL.
- Missing actual `CompiledTaskSpec` provenance retains A0.
- Stand-down rejects zero evidence and endpoint thresholds.
- A self-rehashed receipt with an unknown/raw field is rejected.
- A disabled ledger cannot carry records; a sealed ledger cannot append.
- Provider identifiers are digest-only; eligibility reasons are closed.
- A completed benchmark receipt cannot resume under a different
  model/effort/prompt/commit/CLI/kind/call binding.
- Prediction answers must equal the validated receipt and ignored raw output.
- Unknown Codex JSONL event/item shapes stop the pilot.
- Gold cannot open without an exact committed 42-model-execution inventory.

## Evidence boundary

These results establish implementation behavior for the tested deterministic
contracts. They do not establish natural-error recall, semantic correctness,
formalization fidelity, extraction recall, calibrated EV inputs, causal route
effects, personalization value, general superiority, cost savings, or safe
default activation.

## Three-item development pilot

The sealed pilot completed exactly 42 model executions: six positive controls
and 36 scored calls, yielding 18 matched BASE/FOIL pairs across three GPQA items
and six model/effort configurations. There were no retries, substitutions,
timeouts, invalid answers, unknown event shapes, or tool events.

- BASE accuracy: **13/18 (72.2%)**
- FOIL accuracy: **12/18 (66.7%)**
- Paired difference: **-1/18 (-5.6 percentage points)**
- Discordant pairs: **1 FOIL-only correction; 2 BASE-only reversals**
- Exact McNemar and item-cluster sign-flip tests: **p = 1.0**
- Mean wall time: **33.17 s BASE; 43.46 s FOIL**
- Mean input tokens: **17,631 BASE; 24,651 FOIL**
- Mean output tokens: **1,408 BASE; 1,985 FOIL**

This is `OBSERVED_IN_THIS_PILOT`: the small run did not demonstrate an overall
benefit and observed higher FOIL time/token use. It remains development evidence
forever and cannot promote, certify, calibrate, or activate RC2. The first
preparation attempt stopped before writing artifacts because the source uses
long canonical difficulty labels; the corrected filter was regression-tested
and committed before every model call and frozen run artifact.
