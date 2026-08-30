# TOKEN-700 Implementation and Qualification Report

**Date:** 2026-08-30
**Protocol:** `gauntlet.token700-qualification.v3`
**Disposition:** `FAIL_LOCAL_EFFICACY_OR_SAFETY_GATE`
**Release authority:** none

## Outcome

The retrofit is behaviorally noninferior on the complete frozen local suite, but it does not meet
the preregistered overall efficiency targets. Promotion is not authorized.

- Baseline correctness: **30/30**
- Candidate correctness: **30/30**
- Candidate regressions: **0**
- Candidate false-clear events: **0**
- Candidate cross-task leaks: **0**
- Candidate auxiliary LLM calls: **0** (baseline: 20 measured title calls)
- Canonical task/obligation parity: **100%**

The candidate succeeds on long-session continuity and eliminates automatic title-model calls, but
its lean capsule and larger compiled Gauntlet surface add about 21–23% conversation-input overhead
to seven short or capability-absence workload classes. That makes the overall finite-suite median
negative even though long sessions improve materially.

## Frozen gate result

| Gate | Threshold | Observed | Result |
|---|---:|---:|---|
| Finite-suite quality noninferiority | zero regressions; candidate >= baseline | 0 regressions; 30 = 30 | PASS |
| Route capsule maximum | <= 512 tokens | 113 | PASS |
| Compact status maximum | <= 1,024 tokens | 262 | PASS |
| Candidate extra LLM calls | 0 | 0 | PASS |
| Canonical task/obligation parity | 100% | 100% | PASS |
| Candidate false-clear events | 0 | 0 | PASS |
| Candidate cross-task leaks | 0 | 0 | PASS |
| Overall median conversation-input reduction | >= 40% | **-21.37%** | **FAIL** |
| Median complete-token reduction | >= 25% | **10.44%** | **FAIL** |

All 105 conversation calls per arm and all three tool calls per arm reconciled to persisted
TOKEN-000 records. The baseline made 20 separately measured auxiliary title calls; the candidate
made none. The one localhost connection-reset log during v3 did not produce a measurement drop,
unknown request, retry, fallback, case failure, or reconciliation failure.

## Workload-level paired medians

| Workload | Conversation input | Complete token units | Interpretation |
|---|---:|---:|---|
| W01 no-tool one-shot | -22.04% | -21.97% | short-turn overhead |
| W02 one status call | -23.29% | -5.33% | overhead partly offset by removed title call |
| W03 web capability-absence | -20.92% | +10.88% | title-call removal dominates complete cost |
| W04 coding capability-absence | -22.17% | -22.07% | short-turn overhead |
| W05 browser capability-absence | -20.98% | -20.88% | short-turn overhead |
| W06 small MCP capability-absence | -21.79% | +10.45% | title-call removal dominates complete cost |
| W07 large MCP capability-absence | -21.76% | +10.44% | no external catalog under Gauntlet-only scope |
| W08 ten-turn chat | +35.98% | +37.00% | material continuity win |
| W09 resumed long session | +43.81% | +44.38% | passes the 40% target locally |
| W10 mixed four-obligation task | +19.21% | +23.38% | bounded multi-turn win |

The frozen continuity-stratum median (`W08`–`W10`) is **+35.98%**. The capability-absence-control
median (`W03`–`W07`) is **-21.76%**. External MCP/tool-heavy, real-model, cache, monetary, and
production performance remain unestablished by design.

## Exact evidence identities

- Baseline runtime: `4e455e4dcddc329a6d2455676fdfc78a17338523`, tree
  `17225910e1962b18b652e922c01e897f707f5eb1`
- Candidate runtime: `bd621d64876ff2434ebef46c2115603e072bd247`, tree
  `1b7a2d47540aef0a0fb68707bd2e1cf5a3ed9667`
- V3 preregistration: `8457ff8660051bdf24840ef9ed88658a722fd5f8`
- V3 evaluator: `a8961c9fed5510037fcd2304d0ad1c39c9ebab61`, tree
  `a6703bf6192a51c47ab5fbcda5276e48e782f839`
- Pinned Hermes: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`)
- V3 manifest SHA256: `4a95d8e3d54afc26a5d198df43257ac3e58731b3fcd1cf0049cb82b867297947`
- Valid qualification JSON SHA256:
  `f95cd6cd62a2fb53c123d627b2a173a4059e02935a4f0255733545c6b7a91a2e`

The JSON persists privacy-safe numeric projections and keyed/component digests, not raw provider
requests, responses, tool outputs, or secrets.

## Invalid-run audit trail

Two predecessor runs are retained explicitly as invalid evidence and are not combined with v3:

| Artifact | Disposition | Reason | SHA256 |
|---|---|---|---|
| `TOKEN_700_V1_INVALID_2026-08-30.json` | `INVALID_BASELINE` | auxiliary requests were treated as conversations; route metrics were read from the wrong level | `716b8cf33fd64551c8ba4770edf8d0e321feaf1ebb31742c08a80ec54d9498e6` |
| `TOKEN_700_V2_INVALID_2026-08-30.json` | `INVALID_BASELINE` | missing W10 first-template fallback emitted `"None"`; baseline title policy was T01-only | `85b86b3ae7582b16aca0c4c4fae5a2cd31d74b9955544b13b3bcd3f3f7c55a0c` |

V3 added fail-closed classification/reconciliation, nested metric access, invalid-quality efficacy
suppression, exact 102-turn marker preflight, W10 template fallback, and a session-level baseline
title bound before the valid run.

## Decision and next engineering discriminator

The correct decision is **do not promote the complete retrofit as an overall token-efficiency win**.
The quality/safety mechanisms and long-session savings are retained as valid component evidence, but
the candidate needs a new prospectively evaluated optimization that bypasses or materially shrinks
the lean capsule and compiled tool surface for short/capability-absence turns while preserving the
W08–W10 continuity gains.

Any such implementation changes the candidate runtime and requires a new preregistered protocol;
v3 thresholds and results must not be edited or rerun to rescue the disposition.

**PROCESS ASSURANCE:** `derive`, `self`, `refresh`, `boundary`, and `oob` were fired. The first two
runs were rejected rather than rationalized, all exposed outcomes were version-bounded, and the
valid all-green quality result was still denied promotion because both frozen efficacy gates failed.
