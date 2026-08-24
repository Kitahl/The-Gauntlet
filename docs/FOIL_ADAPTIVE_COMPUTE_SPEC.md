# FOIL Adaptive Compute v4 — implemented shadow controller

Status: **implemented software contract; default-off; behavioral value unmeasured**

This document replaces the earlier v3 design where it conflicts with FOIL v5.
V5 freezes an externally generated answer A0 before residual analysis. Therefore:

- `DIRECT` means retain frozen A0;
- `VERIFY` means recommend one named, host-declared deterministic check;
- `FULL` means recommend the bounded full complement path to the host;
- no route executes work, replaces A0, changes authority, or writes a profile.

The controller is implemented in `tools/foil_adaptive_route.py`. The observational
RouteVector ledger is implemented in `tools/foil_shadow_route_ledger.py`.

## 1. Economic rule

For route `r` and base-correctness estimate `q`:

    EV(r) = (1-q) rescue_r U_rescue
            - q damage_r U_damage
            - lambda cost_r

All probabilities are frozen integer parts-per-million. Utilities and cost
penalties use one caller-declared micro-utility unit. The implementation compares
the exact integer numerator with denominator `10^12`; it does not use floating
point or collapse heterogeneous raw cost receipts into a fabricated total.

`DIRECT` has zero incremental EV. `VERIFY` or `FULL` is recommended only when its
frozen EV is strictly positive and its declared incremental cost fits the supplied
remaining budget. Missing estimates, unknown routes, mismatched bindings, and
ties retain A0.

The estimator is external to the controller. Normal route history never rewrites
the frozen EV model.

## 2. Routing law

| Observed state | Advisory result |
|---|---|
| Controller disabled | `DIRECT` |
| No concrete risk | final `DIRECT` |
| Borderline, no named defect, positive frozen probe value | non-final `DIRECT` plus exactly two requested resamples |
| One concrete falsifiable host-declared obligation | eligible for `VERIFY` |
| Multiple declared obligations or contradictory risks | eligible for `FULL` |
| Exact closed verifier reports a matching `FAIL` | eligible for `FULL` |
| `PASS`, `UNKNOWN`, wrong verifier/version/input, generated obligation | `DIRECT` |

The two-resample result is only a request to the host. The controller has no model
handle and cannot perform the samples. Agreement is not correctness and no SPRT
is applied to correlated same-model resamples.

The DIRECT answer remains the incumbent. A route recommendation never authorizes
replacement. Even an exact verifier `FAIL` produces only a host-facing shadow
recommendation; existing certificate, admission, candidate-state, and one-use
host-bridge contracts remain separate and unchanged.

## 3. Host-declared decidable route

`make_host_verifier_route()` accepts a real `CompiledTaskSpec` and selects only an
applicable deterministic `ObligationBundle` with a compiler-created case. At
decision time the controller requires that same `CompiledTaskSpec`, rederives
the closed route set, and compares the complete selected route. A caller-created
object that merely claims `HOST_DECLARED` provenance is ineligible. The route
binds:

- A0/task/spec/compiler/config digests;
- claim and obligation IDs;
- closed verifier ID and version;
- verifier-input digest;
- compilation and compiler digests.

It accepts no prose, arbitrary callback, provider, dynamic registry entry, or
model-generated obligation. The current compiler still **never extracts checks
from prose**. This adapter connects the existing host-supplied declarative
universe to adaptive compute; it does not create a transformation layer.

## 4. Posterior stand-down

Optional stand-down uses posterior mass, not a point estimate. It activates only
when all of the following are supplied explicitly:

- stand-down accuracy threshold;
- required posterior mass;
- a strictly interior accuracy threshold and required posterior mass;
- a positive minimum observation count;
- a fresh count-backed posterior;
- exact model, contract, and task-regime fingerprints.

Item-specific falsifiable risk outranks the prior. A stale, undersized, or
mismatched posterior cannot stand down the controller. Stand-down retains A0 and
spends nothing.

## 5. Shadow RouteVector ledger

The default-off ledger stores exact vectors:

    RouteVector(compute_mode, provider_fingerprints_sha256,
                verifier_id, verifier_version, retry_count)

Provider identity is digest-only, verifier identity/version must resolve in the
closed registry, and eligibility reasons are a closed enum. Every observation is
keyed by the exact eligibility digest and full route. Sealed ledgers are
immutable; receipt verification reconstructs every typed record, rejects
unknown or missing fields even after self-consistent rehashing, and rejects
records under a disabled ledger. It may record whether assignment was
observational, matched, or randomized, but its normal summary is always
descriptive and sets:

- `causal_claim_authorized = false`;
- `controller_update_authorized = false`;
- `component_credit_allocated = false`.

It exposes no selector, ranker, fitter, policy updater, executor, or persistence
side effect. Provider, compute, verifier, and retry effects require a separately
frozen matched or randomized study; normal selected-route outcomes cannot assign
credit among components.

## 6. Authority and runtime isolation

The controller and ledger import no Gauntlet or Mastermind runtime. They do not
alter `foil_policy.RuntimePolicyV2`, `foil_interventions`, candidate state,
authority decisions, the post-solve monitor, the scanner, or the host bridge.
Existing activation remains event-driven, opt-in, and zero-token. No polling or
background repair path is introduced.

Every decision is digest-only, control-only, shadow-only, host-action-required,
A0-preserving, and `execution_authorized = false`.

## 7. Evidence and release status

Unit tests establish only the named deterministic contracts and negative
controls. They do not show that the risk signal discriminates errors, that the EV
inputs are calibrated, that two resamples help, that the controller saves cost,
or that FOIL beats DIRECT.

The final development pilot uses three frozen items. It is intentionally too
small for calibration, certification, promotion, a fitted interaction model, or
safe default activation. Its permitted labels are `unsafe`, `inconclusive`, or
`observed-in-this-pilot`.
