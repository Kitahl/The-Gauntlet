# FOIL v5 / Mirror 0.6.0-rc3 validation report

Date: 2026-08-24<br>
Status: **software-contract upgrade complete; external efficacy gates unrun**

## Completed software boundary

RC3 adds the missing host-owned final selection boundary after FOIL's existing
shadow path. FOIL itself remains default-off, non-executing, and unable to
autonomously mutate A0. A candidate reaches final selection only through:

1. registered answer-surface defect authority;
2. an externally supplied, content-addressed candidate;
3. complete structural/predicate and independently represented semantic
   certificates bound to the same A0, candidate, scope, and obligation set;
4. distinct structural and semantic provenance groups;
5. COMMITTABLE admission;
6. qualifying Gate 1/2/3 receipts and explicit host activation;
7. a current, matching, one-use ACTIVE authority token;
8. a digest-only `HostActionRequest`;
9. exact A0, candidate, artifact, request, and explicit host-approval bindings.

Any ordinary missing or mismatched finalization prerequisite returns the exact
original A0 object. The finalization trace contains digests and typed reasons,
not raw answer content. The finalizer has no model, tool, network, process,
filesystem, candidate-generation, or persistence surface.

## Verification results

| Check | Result | Scope |
|---|---:|---|
| Focused admission/repair/bridge/finalizer tests | **44 passed** | certificate independence, one-use request, exact A0 preservation, approved selection |
| Full Python contract suite | **711 passed** | repository-wide `unittest` discovery |
| New Python syntax compilation | **passed** | finalizer, benchmark harness, finalizer tests |
| New-file deterministic line-length scan | **passed** | no line over 100 characters |
| Staged Git whitespace check before frozen commit | **passed** | implementation + preregistration |
| Safe-finalization small pilot | **7/7 passed** | 3 rescues + 4 preservation/rejection cases |
| Independently recomputed raw-row totals | **7 passed, 0 unauthorized changes** | did not trust report summary fields |

The active interpreter did not provide `pytest` or Ruff modules. Their failed
module lookups were not counted as test results. The dependency-free unittest
suite, `py_compile`, Git checks, and deterministic formatting scan were used.

## Frozen small pilot

- Pre-result commit: `334993a`
- Preregistration Git blob: `d9d8337d19f1536d0cbd56f703663e7e3cb05107`
- Runner Git blob: `a957b3819be7d567cbc30bd0519007093d187e45`
- Executions/retries/replacements: **1 / 0 / 0**
- `results.json` SHA-256: `4cdb3d78ab23a51beca897552e9051fe17626ee223b51c600eaa729ae6f4cca1`
- `report.md` SHA-256: `4d3d646cea1863248dcfd19d101a81bd6ffa7ab92bdbc369d9077989999b9d3f`

| Case | Outcome | Selected state |
|---|---|---|
| arithmetic-rescue | PASS | CANDIDATE_SELECTED |
| json-rescue | PASS | CANDIDATE_SELECTED |
| tolerance-rescue | PASS | CANDIDATE_SELECTED |
| correct-clear-stand-down | PASS | BASE_PRESERVED |
| semantic-route-stand-down | PASS | BASE_PRESERVED |
| same-provenance-rejection | PASS | BASE_PRESERVED |
| tampered-candidate-rejection | PASS | BASE_PRESERVED |

The candidates and Gate 1/2/3 receipts are frozen host fixtures. This pilot
tests deterministic routing, binding, admission, replay, explicit approval, and
selection safety. It does not test candidate discovery or external promotion.

## Claims deliberately not made

- No natural-language-to-obligation generator exists in the runtime.
- Formalization fidelity and extraction recall remain a future admission gate.
- The adaptive controller remains default-off and uncalibrated outside this
  deterministic contract pilot.
- RouteVector history remains observational; it does not learn or select.
- Gate 1B/1C/2/3, RQ-26, the model-strength ladder, prospective partitions,
  profile efficacy, and human-complementarity studies remain unrun.
- The earlier three-item prompt benchmark did not exercise this A0-preserving
  runtime and remains a separate negative/mixed development result.
- The 7/7 result is not evidence of general answer-quality improvement.

## Repository state

The work is on local branch `codex/foil-v5-full-system`. It has not been merged
or pushed. The pre-existing untracked `graphify-out/` and
`tools/graphify-out/` directories remain excluded and untouched.
