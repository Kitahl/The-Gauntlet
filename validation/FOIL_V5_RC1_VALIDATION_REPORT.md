# FOIL v5 RC1 Validation Report

Date: 2026-08-24
Candidate: **0.6.0-rc1** on **codex/foil-v5-decidable-coverage**
Base: GitHub main at **4f088d688fa9e25b4608f44000a5d9812efa45f9**

Status: **software candidate verified locally; behavioral promotion gates unrun**

## Verified implementation boundary

The candidate implements the complete default-off/shadow software path described
by the reconciled FOIL v5 plan:

- strict structured-spec obligation compilation after immutable A0;
- typed decidable coverage, residuals, certificates, and no-answer states;
- a closed deterministic verifier registry and calibrated shadow scanner;
- sealed G0 protocol/run-ledger bindings and candidate state/token controls;
- shadow repair admission, a closed READY Ditto resolver, and a one-use host
  bridge, all non-executing and host-action-required;
- bounded event-driven pre-/post-solve monitoring with no polling, provider,
  model, tool, network, or subprocess path;
- provider-neutral offline P0 and Gate-1 structural harnesses;
- default-off P1 planning and P2 transfer/refinement foundations;
- no FOIL runtime dependency on Gauntlet or Mastermind.

This report does not promote FOIL, a scanner, P0, P1, P2, Ditto, repair, history,
or a model ladder. Tiny fixtures are structural smoke data, not efficacy
evidence.

## Local verification

| Check | Result |
|---|---|
| ruff check validation tools tests benchmarks/harness | PASS |
| python -m unittest discover -s tests -q | PASS — 661 tests in 44.897 s |
| python -m compileall -q validation tools tests benchmarks/harness | PASS |
| git diff --check | PASS |
| python validation/validate_soul_gauntlet_public.py | PASS — 8 public/separation invariants |
| python validation/validate_vnext_runtime.py | PASS — 31/31 checks |
| Structured-spec compiler example CLI | PASS — digest-only receipt |
| One-claim v5 runtime example CLI | PASS — A0 preserved, no repair, execution denied |
| Gate-1 development and lock fixture CLIs | PASS — explicitly structural-only |
| Offline P0 fixture CLI | PASS — P0_NOT_PROMOTED |
| Showcase validator | LOCAL ENVIRONMENT BLOCKED — Playwright is absent; hash-locked CI gate required |

The repository test run intentionally exercises failure-path subprocesses. Their
expected warning about a nonexistent candidate module and expected refusal to
treat the reference policy as the real candidate were followed by an overall
661-test PASS.

## Monitor cost check

A local microbenchmark over event construction plus monitor handling measured:

- disabled path mean: 12.625 microseconds/event;
- observe path after a long stream: 237.64 microseconds/event;
- retained deduplication window: 256 payload digests;
- model calls, tool calls, network calls, and tokens: 0.

These are local implementation-cost observations, not production latency or
behavioral-benefit evidence. The bounded window prevents unbounded monitor
memory growth.

## Gate ledger

| Gate | State |
|---|---|
| G0 contract lock software | Implemented and tested |
| Historical profile P0 | P0_NOT_PROMOTED; offline reproducer only |
| Gate 1A implementation contracts | Implemented and tested |
| Gate 1B blind lock evaluation | UNRUN |
| Gate 1C prospective confirmation | UNRUN |
| Gate 2 repair safety/effectiveness | UNRUN |
| Gate 3 Ditto behavior/effectiveness | Resolver implemented; external study UNRUN |
| RQ-26 adaptive complement selection | UNRUN |
| Scoped model-strength ladder | UNRUN |
| Evidence-conditioned history | UNRUN |

Until the external gates pass, the candidate remains a testing RC: it may
compile, scan, describe, propose, resolve, and request host review, but it may
not autonomously mutate A0, execute a repair/provider, claim efficacy, or claim
promotion.